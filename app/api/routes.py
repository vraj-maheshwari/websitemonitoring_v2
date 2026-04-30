import re
from collections import Counter
from statistics import mean

from datetime import timedelta

import json
import logging
from io import BytesIO

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for, send_file
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.daily_uptime_summary import DailyUptimeSummary
from app.models.seo_log import SEOLog
from app.models.site import Site
from app.models.site_notification import SiteNotification
from app.models.ssl_log import SSLLog
from app.models.uptime_log import UptimeLog
from app.models.user import User
from app.services.monitor_service import run_uptime_check
from app.services.monitoring_service import prepare_site
from app.services.report_service import generate_site_report
from app.services.seo_service import should_skip_seo_for_cooldown, run_seo_check
from app.services.ssl_service import run_ssl_check
from app.utils.time import normalize, now_utc
from app.utils.urls import normalize_url
from app.workers.tasks import run_seo_check_task, run_ssl_check_task, run_uptime_check_task

api_bp = Blueprint("api", __name__)
web_bp = Blueprint("web", __name__)
logger = logging.getLogger(__name__)

# Exempt the JSON API blueprint from CSRF — it uses session auth, not form tokens.
# Web form routes (web_bp) remain CSRF-protected.
from app import csrf
csrf.exempt(api_bp)


@api_bp.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 409
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session["user_id"] = user.id
    return jsonify({"message": "Registered", "user": user.to_dict()}), 201


@api_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    user = User.query.filter_by(email=(data.get("email") or "").strip().lower()).first()
    if user is None or not user.check_password(data.get("password") or ""):
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user.id
    return jsonify({"message": "Logged in", "user": user.to_dict()})


@api_bp.route("/auth/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    return jsonify({"message": "Logged out"})

# ➕ Add site
@api_bp.route("/sites", methods=["POST"])
def add_site():
    data = request.get_json() or {}

    url = data.get("url")
    name = (data.get("name") or "").strip() or None
    try:
        interval = _parse_interval(data.get("check_interval", 60), default=60, minimum=30)
        uptime_interval = _parse_interval(data.get("uptime_check_interval", interval), default=interval, minimum=30)
        ssl_interval = _parse_interval(data.get("ssl_check_interval", 86400), default=86400, minimum=3600)
        seo_interval = _parse_interval(data.get("seo_check_interval", 604800), default=604800, minimum=3600)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    emails = data.get("notification_emails") or data.get("emails") or []

    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        canonical_url, normalized_url = normalize_url(url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    site = Site(
        name=name,
        url=canonical_url,
        normalized_url=normalized_url,
        user_id=_effective_user_id(),
        check_interval=interval,
        uptime_check_interval=uptime_interval,
        ssl_check_interval=ssl_interval,
        seo_check_interval=seo_interval,
    )
    prepare_site(site)
    db.session.add(site)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Site already exists"}), 409

    for email in emails:
        recipient = (email or "").strip()
        if recipient and _is_valid_email(recipient):
            db.session.add(SiteNotification(site_id=site.id, email=recipient, is_active=True))
        elif recipient:
            logger.warning("Skipping invalid notification email for site %s: %s", site.id, recipient)
    
    # SaaS State Initialization
    site.app_status = "checking"
    site.uptime_status = "pending"
    site.ssl_status = "pending"
    site.seo_status = "pending"
    db.session.commit()
    
    dispatch = {
        "uptime": _safe_delay(run_uptime_check_task, site.id),
        "ssl": _safe_delay(run_ssl_check_task, site.id),
        "seo": _safe_delay(run_seo_check_task, site.id),
    }

    return jsonify({"message": "Site added", "id": site.id, "dispatch": dispatch}), 201


# 📃 List sites
@api_bp.route("/sites", methods=["GET"])
def list_sites():
    query = _owned_sites_query()
    since = request.args.get("since")
    if since:
        try:
            since_dt = normalize(_parse_iso8601(since))
            query = query.filter(Site.updated_at > since_dt)
        except ValueError:
            return jsonify({"error": "Invalid since datetime"}), 400
    sites = query.order_by(Site.updated_at.desc()).all()
    return jsonify([site.to_dict() for site in sites])


@api_bp.route("/sites/<int:site_id>", methods=["GET"])
def get_site(site_id):
    site = _get_owned_site_or_404(site_id)
    latest_uptime = UptimeLog.query.filter_by(site_id=site.id).order_by(UptimeLog.checked_at.desc()).first()
    latest_ssl = SSLLog.query.filter_by(site_id=site.id).order_by(SSLLog.checked_at.desc()).first()
    latest_seo = SEOLog.query.filter_by(site_id=site.id).order_by(SEOLog.checked_at.desc()).first()
    payload = site.to_dict()
    payload.update({
        "latest_uptime": latest_uptime.to_dict() if latest_uptime else None,
        "latest_ssl": latest_ssl.to_dict() if latest_ssl else None,
        "latest_seo": latest_seo.to_dict() if latest_seo else None,
        "seo": _serialize_site_seo(site, latest_seo),
    })
    return jsonify(payload)


@api_bp.route("/sites/<int:site_id>", methods=["DELETE"])
def delete_site(site_id):
    site = _get_owned_site_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    return jsonify({"message": "Site deleted"})


@api_bp.route("/sites/<int:site_id>/check", methods=["POST"])
def run_all_checks(site_id):
    site = _get_owned_site_or_404(site_id)
    statuses = {}
    should_skip, skip_reason = should_skip_seo_for_cooldown(site)
    for check_type, task in (("uptime", run_uptime_check_task), ("ssl", run_ssl_check_task)):
        if getattr(site, f"{check_type}_status") == "running":
            statuses[check_type] = "skipped (already running)"
        else:
            statuses[check_type] = _safe_delay(task, site.id)
    if site.seo_status == "running":
        seo_dispatch_status = "skipped (already running)"
    elif should_skip:
        seo_dispatch_status = f"skipped (cooldown active)"
    else:
        seo_dispatch_status = _safe_delay(run_seo_check_task, site.id)
    statuses.update({
        "message": "Check triggered",
        "seo": seo_dispatch_status,
        "cooldown_active": should_skip,
        "cooldown_reason": skip_reason if should_skip else None,
    })
    return jsonify(statuses)


@api_bp.route("/sites/<int:site_id>/history/uptime", methods=["GET"])
def uptime_history(site_id):
    site = _get_owned_site_or_404(site_id)
    days = request.args.get("days", 7, type=int)
    cutoff = now_utc() - timedelta(days=max(days, 1))
    logs = UptimeLog.query.filter(UptimeLog.site_id == site.id, UptimeLog.checked_at >= cutoff).order_by(UptimeLog.checked_at.desc()).limit(500).all()
    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/sites/<int:site_id>/history/ssl", methods=["GET"])
def ssl_history(site_id):
    site = _get_owned_site_or_404(site_id)
    limit = request.args.get("limit", 10, type=int)
    logs = SSLLog.query.filter_by(site_id=site.id).order_by(SSLLog.checked_at.desc()).limit(min(limit, 100)).all()
    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/sites/<int:site_id>/history/seo", methods=["GET"])
def seo_history(site_id):
    site = _get_owned_site_or_404(site_id)
    limit = request.args.get("limit", 5, type=int)
    logs = SEOLog.query.filter_by(site_id=site.id).order_by(SEOLog.checked_at.desc()).limit(min(limit, 100)).all()
    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/sites/<int:site_id>/uptime-summary", methods=["GET"])
def uptime_summary(site_id):
    site = _get_owned_site_or_404(site_id)
    days = request.args.get("days", 30, type=int)
    cutoff = (now_utc() - timedelta(days=max(days, 1))).date()
    rows = DailyUptimeSummary.query.filter(DailyUptimeSummary.site_id == site.id, DailyUptimeSummary.summary_date >= cutoff).order_by(DailyUptimeSummary.summary_date.asc()).all()
    return jsonify([row.to_dict() for row in rows])


# ▶️ Trigger check manually
@api_bp.route("/check/<int:site_id>", methods=["GET"])
def check_site(site_id):
    site = _get_owned_site_or_404(site_id)
    result = _safe_delay(run_uptime_check_task, site.id)
    return jsonify({"message": "Uptime check requested", "dispatch": result}), 202 if result["status"] == "queued" else 503


@api_bp.route("/check-seo/<int:site_id>", methods=["GET"])
def check_site_seo(site_id):
    site = _get_owned_site_or_404(site_id)
    should_skip, skip_reason = should_skip_seo_for_cooldown(site)
    if should_skip:
        return jsonify({
            "message": "SEO check skipped",
            "dispatch": "skipped (cooldown active)",
            "cooldown_active": True,
            "cooldown_reason": skip_reason,
        }), 202
    result = _safe_delay(run_seo_check_task, site.id)
    return jsonify({
        "message": "SEO check requested",
        "dispatch": result,
        "cooldown_active": False,
        "cooldown_reason": None,
    }), 202 if result["status"] == "queued" else 503


@api_bp.route("/check-ssl/<int:site_id>", methods=["GET"])
def check_site_ssl(site_id):
    site = _get_owned_site_or_404(site_id)
    result = _safe_delay(run_ssl_check_task, site.id)
    return jsonify({"message": "SSL check requested", "dispatch": result}), 202 if result["status"] == "queued" else 503


@api_bp.route("/logs/<int:site_id>", methods=["GET"])
def get_logs(site_id):
    site = _get_owned_site_or_404(site_id)
    logs = UptimeLog.query.filter_by(site_id=site.id)\
        .order_by(UptimeLog.id.desc())\
        .limit(10)\
        .all()

    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/seo-logs/<int:site_id>", methods=["GET"])
def get_seo_logs(site_id):
    site = _get_owned_site_or_404(site_id)
    logs = (
        SEOLog.query.filter_by(site_id=site.id)
        .order_by(SEOLog.checked_at.desc())
        .limit(10)
        .all()
    )
    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/sites/<int:site_id>/broken-links", methods=["GET"])
def get_broken_links(site_id):
    """Return broken link data from the most recent valid SEO log."""
    site = _get_owned_site_or_404(site_id)
    log = (
        SEOLog.query.filter_by(site_id=site.id)
        .filter(SEOLog.fetch_valid.is_(True))
        .order_by(SEOLog.checked_at.desc())
        .first()
    )
    if not log:
        return jsonify({"error": "No SEO audit data yet"}), 404
    return jsonify({
        "checked_at":      log.checked_at.isoformat(),
        "links_checked":   log.links_checked,
        "broken_link_count": log.broken_link_count,
        "broken_links":    log.broken_links or {},
    })


@api_bp.route("/sites/<int:site_id>/tech-stack", methods=["GET"])
def get_tech_stack(site_id):
    """Return technology stack from the most recent valid SEO log."""
    site = _get_owned_site_or_404(site_id)
    log = (
        SEOLog.query.filter_by(site_id=site.id)
        .filter(SEOLog.fetch_valid.is_(True))
        .order_by(SEOLog.checked_at.desc())
        .first()
    )
    if not log:
        return jsonify({"error": "No SEO audit data yet"}), 404
    return jsonify({
        "checked_at": log.checked_at.isoformat(),
        "tech_stack": log.tech_stack or {},
        "tech_flat":  log.tech_flat or [],
        "tech_diff":  log.tech_diff or {},
        "server":     (log.signals or {}).get("server", "") if log.signals else "",
    })


@api_bp.route("/sites/<int:site_id>/analytics", methods=["GET"])
def get_analytics(site_id):
    """Return trend analytics for a site. Query: ?days=30"""
    from app.services.analytics_service import get_site_analytics
    site = _get_owned_site_or_404(site_id)
    days = request.args.get("days", 30, type=int)
    return jsonify(get_site_analytics(site.id, days=days))


@api_bp.route("/incidents/<int:incident_id>", methods=["GET"])
def get_incident(incident_id):
    """Return full incident detail including timeline and root cause."""
    from app.models.incident import Incident
    incident = db.session.get(Incident, incident_id)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
    # Ownership check via site
    _get_owned_site_or_404(incident.site_id)
    return jsonify(incident.to_dict())


@api_bp.route("/sites/<int:site_id>/incidents", methods=["GET"])
def list_incidents(site_id):
    """List incidents for a site. Query: ?status=OPEN|RESOLVED&limit=20"""
    from app.models.incident import Incident
    site = _get_owned_site_or_404(site_id)
    status_filter = request.args.get("status")
    limit = request.args.get("limit", 20, type=int)
    q = Incident.query.filter_by(site_id=site.id)
    if status_filter:
        q = q.filter_by(status=status_filter.upper())
    incidents = q.order_by(Incident.opened_at.desc()).limit(min(limit, 100)).all()
    return jsonify([i.to_dict() for i in incidents])


@api_bp.route("/sites/<int:site_id>/security", methods=["GET"])
def get_security(site_id):
    """Return security audit from the most recent valid SEO log."""
    site = _get_owned_site_or_404(site_id)
    log = (
        SEOLog.query.filter_by(site_id=site.id)
        .filter(SEOLog.fetch_valid.is_(True))
        .order_by(SEOLog.checked_at.desc())
        .first()
    )
    if not log:
        return jsonify({"error": "No SEO audit data yet"}), 404
    return jsonify({
        "checked_at":      log.checked_at.isoformat(),
        "security_score":  log.security_score,
        "security_headers": log.security_headers or {},
        "security_issues": log.security_issues or [],
        "malware_flags":   log.malware_flags or [],
    })


@api_bp.route("/site/<int:site_id>/status", methods=["GET"])
def get_site_status(site_id):
    site = _get_owned_site_or_404(site_id)
    
    # SaaS: If logs exist but status is stuck, force ready (Truth logic)
    if site.app_status == "pending" and site.last_uptime_check_at:
        site.refresh_app_status()
        db.session.commit()

    return jsonify(site.to_dict())


@web_bp.route("/", methods=["GET"])
def dashboard():
    sites = _owned_sites_query().order_by(Site.created_at.desc()).all()
    site_ids = [site.id for site in sites]
    recent_uptime_logs = UptimeLog.query.filter(UptimeLog.site_id.in_(site_ids)).order_by(UptimeLog.checked_at.desc()).limit(12).all() if site_ids else []
    recent_ssl_logs = SSLLog.query.filter(SSLLog.site_id.in_(site_ids)).order_by(SSLLog.checked_at.desc()).limit(8).all() if site_ids else []
    recent_seo_logs = SEOLog.query.filter(SEOLog.site_id.in_(site_ids)).order_by(SEOLog.checked_at.desc()).limit(8).all() if site_ids else []
    response_samples = [site.last_response_time for site in sites if site.last_response_time is not None]

    return render_template(
        "dashboard.html",
        metrics=_build_dashboard_metrics(sites, response_samples),
        site_cards=sites,
        recent_uptime_logs=recent_uptime_logs,
        recent_ssl_logs=recent_ssl_logs,
        recent_seo_logs=recent_seo_logs,
    )


@web_bp.route("/site/<int:site_id>", methods=["GET"])
def site_detail(site_id):
    site = _get_owned_site_or_404(site_id)
    from app.models.incident import Incident
    from app.services.analytics_service import get_site_analytics

    uptime_logs = (
        UptimeLog.query.filter_by(site_id=site_id)
        .order_by(UptimeLog.checked_at.desc())
        .limit(20)
        .all()
    )
    ssl_logs = (
        SSLLog.query.filter_by(site_id=site_id)
        .order_by(SSLLog.checked_at.desc())
        .limit(10)
        .all()
    )
    seo_logs = (
        SEOLog.query.filter_by(site_id=site_id)
        .order_by(SEOLog.checked_at.desc())
        .limit(10)
        .all()
    )
    recent_incidents = (
        Incident.query.filter_by(site_id=site_id)
        .order_by(Incident.opened_at.desc())
        .limit(10)
        .all()
    )
    analytics = get_site_analytics(site_id, days=30)

    return render_template(
        "site_detail.html",
        site=site,
        uptime_logs=uptime_logs,
        ssl_logs=ssl_logs,
        seo_logs=seo_logs,
        uptime_breakdown=Counter("Up" if log.is_up else "Down" for log in uptime_logs),
        recent_incidents=recent_incidents,
        analytics=analytics,
    )


@web_bp.route("/site/<int:site_id>/download-report", methods=["GET"])
def download_report(site_id):
    """Download site monitoring report as JSON."""
    site = _get_owned_site_or_404(site_id)
    
    report = generate_site_report(site_id)
    if not report:
        flash("Report could not be generated.", "error")
        return redirect(url_for("web.site_detail", site_id=site_id))
    
    # Create JSON file
    report_json = json.dumps(report, indent=2, default=str)
    report_bytes = BytesIO(report_json.encode('utf-8'))
    
    filename = f"site_report_{site.id}_{site.display_name().replace(' ', '_').replace('/', '_')}.json"
    
    return send_file(
        report_bytes,
        mimetype="application/json",
        as_attachment=True,
        download_name=filename
    )


@web_bp.route("/sites/new", methods=["POST"])
def create_site():
    name = (request.form.get("name") or "").strip() or None
    url = (request.form.get("url") or "").strip()
    interval = request.form.get("check_interval", type=int) or 60
    emails_raw = request.form.get("notification_emails", "")

    if not url:
        flash("Website URL is required.", "error")
        return redirect(url_for("web.dashboard"))

    try:
        canonical_url, normalized_url = normalize_url(url)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("web.dashboard"))

    site = Site(
        name=name,
        url=canonical_url,
        normalized_url=normalized_url,
        user_id=_effective_user_id(),
        check_interval=max(interval, 30),
        uptime_check_interval=max(interval, 30),
    )
    prepare_site(site)
    db.session.add(site)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("That website is already being monitored.", "error")
        return redirect(url_for("web.dashboard"))

    for recipient in _parse_notification_emails(emails_raw):
        if _is_valid_email(recipient):
            db.session.add(SiteNotification(site_id=site.id, email=recipient, is_active=True))
        else:
            logger.warning("Skipping invalid notification email for site %s: %s", site.id, recipient)
    
    # SaaS Initialization
    site.app_status = "checking"
    site.uptime_status = "pending"
    site.ssl_status = "pending"
    site.seo_status = "pending"
    db.session.commit()
 
    dispatch = [
        _safe_delay(run_uptime_check_task, site.id),
        _safe_delay(run_ssl_check_task, site.id),
        _safe_delay(run_seo_check_task, site.id),
    ]

    if all(item["status"] == "queued" for item in dispatch):
        flash("Website added and SaaS analysis started.", "success")
    else:
        flash("Website added, but background checks could not be queued. Start Redis/Celery and run checks manually.", "error")
    return redirect(url_for("web.site_detail", site_id=site.id))


@web_bp.route("/site/<int:site_id>/run/<check_type>", methods=["POST"])
def run_check(site_id, check_type):
    site = _get_owned_site_or_404(site_id)

    if check_type == "uptime":
        _safe_delay(run_uptime_check_task, site_id)
        message = f"Uptime check queued for {site.url}."
    elif check_type == "ssl":
        _safe_delay(run_ssl_check_task, site_id)
        message = f"SSL certificate check queued for {site.url}."
    elif check_type == "seo":
        _safe_delay(run_seo_check_task, site_id)
        message = f"SEO audit queued for {site.url}."
    elif check_type == "all":
        _safe_delay(run_uptime_check_task, site_id)
        _safe_delay(run_ssl_check_task, site_id)
        _safe_delay(run_seo_check_task, site_id)
        message = f"Full SaaS monitoring suite queued for {site.url}."
    else:
        abort(404)

    flash(message, "success")
    next_url = request.form.get("next") or url_for("web.site_detail", site_id=site_id)
    return redirect(next_url)


def _build_dashboard_metrics(sites, response_samples):
    monitored_sites = len(sites)
    sites_up = sum(1 for site in sites if site.current_status == "UP")
    sites_down = sum(1 for site in sites if site.current_status == "DOWN")
    avg_response = mean(response_samples) if response_samples else None
    health_score = round((sites_up / monitored_sites) * 100) if monitored_sites else 0

    return {
        "monitored_sites": monitored_sites,
        "sites_up": sites_up,
        "sites_down": sites_down,
        "avg_response": avg_response,
        "health_score": health_score,
    }


def _parse_notification_emails(raw_value: str) -> list[str]:
    emails = []
    for value in (raw_value or "").replace(";", ",").split(","):
        email = value.strip()
        if email:
            emails.append(email)
    return emails


def _serialize_site_seo(site: Site, latest_log: SEOLog | None) -> dict:
    last_fetch_valid = site.last_seo_fetch_valid
    warning = None
    if last_fetch_valid is False:
        warning = (
            "Last SEO check fetched an invalid/placeholder page. Score may be inaccurate. "
            "Trigger a manual re-check when the site is fully online."
        )
    return {
        "score": site.seo_score,
        "state": site.seo_state,
        "last_fetch_valid": last_fetch_valid,
        "last_check_at": site.last_seo_check_at.isoformat() if site.last_seo_check_at else None,
        "warning": warning,
        "latest_log": latest_log.to_dict() if latest_log else None,
    }


def _owned_sites_query():
    query = Site.query
    return query.filter(Site.user_id == _effective_user_id())


def _get_owned_site_or_404(site_id: int) -> Site:
    site = _owned_sites_query().filter(Site.id == site_id).first()
    if site is None:
        abort(404)
    return site


def _parse_iso8601(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _effective_user_id() -> int:
    user_id = session.get("user_id")
    if user_id:
        return int(user_id)
    return _local_user_id()


def _local_user_id() -> int:
    from flask import current_app
    if not current_app.debug:
        abort(401)
    user = User.query.filter_by(email="local@website-monitor.internal").first()
    if user is None:
        user = User(email="local@website-monitor.internal", password_hash="local-development-user")
        db.session.add(user)
        db.session.commit()
    return user.id


_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.fullmatch(email.strip()))


def _parse_interval(value, default: int, minimum: int) -> int:
    if value in (None, ""):
        value = default
    try:
        interval = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Check intervals must be integers") from exc
    if interval < minimum:
        return minimum
    return interval


def _safe_delay(task, site_id: int) -> dict:
    try:
        async_result = task.apply_async(args=(site_id,), retry=False, ignore_result=True)
        return {"status": "queued", "task_id": async_result.id}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to queue %s for site %s: %s", getattr(task, "name", task), site_id, exc)
        return {"status": "queue_failed", "error": str(exc)}
