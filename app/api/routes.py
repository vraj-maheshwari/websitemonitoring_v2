from collections import Counter
from functools import wraps
import re
from statistics import mean

from datetime import timedelta

import json
import logging
import csv
from io import BytesIO, StringIO

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for, send_file
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.daily_uptime_summary import DailyUptimeSummary
from app.models.dns_log import DNSLog
from app.models.seo_log import SEOLog
from app.models.site import Site
from app.models.ssl_log import SSLLog
from app.models.uptime_log import UptimeLog
from app.models.user import User
from app.services.monitor_service import run_uptime_check
from app.services.monitoring_service import prepare_site
from app.services.report_service import generate_site_report
from app.services.seo_service import should_skip_seo_for_cooldown, run_seo_check
from app.services.ssl_service import run_ssl_check
from app.utils.lighthouse_runner import compute_cwv_rating
from app.utils.time import normalize, now_utc
from app.utils.urls import normalize_url
from app.workers.tasks import run_dns_check_task, run_full_audit_task, run_security_check_task, run_seo_check_task, run_ssl_check_task, run_uptime_check_task

api_bp = Blueprint("api", __name__)
web_bp = Blueprint("web", __name__)
logger = logging.getLogger(__name__)

# CSRF exemption for the API blueprint is handled in create_app()


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@api_bp.route("/ping")
def api_ping():
    return jsonify({"pong": True})


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("web.login"))
        return f(*args, **kwargs)
    return decorated


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _serialize_user(user: User, include_created_at: bool = False) -> dict:
    payload = {"id": user.id, "email": user.email}
    if include_created_at:
        payload["created_at"] = user.created_at.isoformat() + "Z" if user.created_at else None
    return payload


def _register_user(email: str | None, password: str | None) -> tuple[User | None, str | None, int]:
    email = _normalize_email(email)
    password = password or ""
    if not EMAIL_RE.match(email):
        return None, "Invalid email format", 400
    if len(password) < 8:
        return None, "Password must be at least 8 characters", 400
    if User.query.filter_by(email=email).first():
        return None, "An account with this email already exists", 409

    user = User(email=email, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session.permanent = True
    session["user_id"] = user.id
    session["user_email"] = user.email
    return user, None, 201


def _login_user(email: str | None, password: str | None) -> tuple[User | None, str | None, int]:
    email = _normalize_email(email)
    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password or ""):
        return None, "Invalid email or password", 401
    if not user.is_active:
        return None, "This account has been deactivated", 403
    session.permanent = True
    session["user_id"] = user.id
    session["user_email"] = user.email
    return user, None, 200


@api_bp.route("/auth/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    user, error, status = _register_user(data.get("email"), data.get("password"))
    if error:
        return jsonify({"error": error}), status
    return jsonify({"success": True, "user": _serialize_user(user, include_created_at=True)}), 201


@api_bp.route("/auth/login", methods=["POST"])
def api_login():
    try:
        data = request.get_json() or {}
        user, error, status = _login_user(data.get("email"), data.get("password"))
        if error:
            return jsonify({"error": error}), status
        return jsonify({"success": True, "user": _serialize_user(user)})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.exception("Login failed with internal error")
        return jsonify({"error": str(e), "traceback": error_details}), 500


@api_bp.route("/auth/logout", methods=["POST"])
@login_required
def api_logout():
    session.clear()
    return jsonify({"success": True})


@api_bp.route("/dashboard/metrics", methods=["GET"])
@login_required
def dashboard_metrics():
    sites = _owned_sites_query().all()
    response_samples = [s.last_response_time for s in sites if s.last_response_time is not None]
    
    # Calculate DNS health
    dns_issue_count = 0
    for s in sites:
        if s.dns_status == 'failed' or s.dns_hijack_suspected or s.dns_ns_changed:
            dns_issue_count += 1
            
    # Calculate SSL warnings
    ssl_critical = 0
    sites_with_ssl = 0
    for s in sites:
        if s.ssl_state == 'VALID':
            sites_with_ssl += 1
        if s.ssl_days_remaining is not None and s.ssl_days_remaining < 14:
            ssl_critical += 1

    metrics = _build_dashboard_metrics(sites, response_samples)
    metrics.update({
        "dns_issue_count": dns_issue_count,
        "ssl_critical_count": ssl_critical,
        "sites_with_ssl": sites_with_ssl,
        "dns_checked_count": sum(1 for s in sites if s.last_dns_check_at is not None)
    })
    return jsonify(metrics)


@api_bp.route("/dashboard/activity", methods=["GET"])
@login_required
def dashboard_activity():
    sites = _owned_sites_query().all()
    site_ids = [s.id for s in sites]
    if not site_ids:
        return jsonify([])
        
    # Get recent anomalies (DOWN sites)
    anomalies = UptimeLog.query.filter(
        UptimeLog.site_id.in_(site_ids),
        UptimeLog.is_up == False
    ).order_by(UptimeLog.checked_at.desc()).limit(10).all()
    
    return jsonify([{
        "id": log.id,
        "site_id": log.site_id,
        "site_name": log.site.display_name(),
        "error_message": log.error_message or "Service unavailable",
        "checked_at": log.checked_at.isoformat() + "Z",
        "status_code": log.status_code
    } for log in anomalies])

# ➕ Add site
@api_bp.route("/sites", methods=["POST"])
@login_required
def add_site():
    data = request.get_json() or {}

    url = data.get("url")
    name = (data.get("name") or "").strip() or None
    try:
        interval = _parse_interval(data.get("check_interval", 60), default=60, minimum=30)
        uptime_interval = _parse_interval(data.get("uptime_check_interval", interval), default=interval, minimum=30)
        ssl_interval = _parse_interval(data.get("ssl_check_interval", 86400), default=86400, minimum=3600)
        seo_interval = _parse_interval(data.get("seo_check_interval", 604800), default=604800, minimum=3600)
        dns_interval = _parse_interval(data.get("dns_check_interval", 3600), default=3600, minimum=300)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
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
        dns_check_interval=dns_interval,
    )
    prepare_site(site)
    db.session.add(site)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Site already exists"}), 409

    # SaaS State Initialization
    site.app_status = "checking"
    site.uptime_status = "pending"
    site.ssl_status = "pending"
    site.seo_status = "pending"
    site.security_status = "pending"
    site.dns_status = "pending"
    db.session.commit()
    
    dispatch = {
        "uptime": _safe_delay(run_uptime_check_task, site.id),
        "ssl": _safe_delay(run_ssl_check_task, site.id),
        "seo": _safe_delay(run_seo_check_task, site.id),
        "security": _safe_delay(run_security_check_task, site.id),
        "dns": _safe_delay(run_dns_check_task, site.id),
    }

    return jsonify({"message": "Site added", "id": site.id, "dispatch": dispatch}), 201


# 📃 List sites
@api_bp.route("/dashboard/analytics", methods=["GET"])
@login_required
def get_fleet_analytics_api():
    """Return aggregated fleet analytics for the user."""
    from app.services.analytics_service import get_fleet_analytics
    days = request.args.get("days", 7, type=int)
    return jsonify(get_fleet_analytics(_effective_user_id(), days=days))


@api_bp.route("/incidents", methods=["GET"])
@login_required
def get_all_incidents():
    """Return recent incidents across all sites for global visibility."""
    limit = request.args.get("limit", 20, type=int)
    from app.models.incident import Incident
    from app.models.site import Site
    
    # Join with Site to get names and ensure ownership
    incidents = (
        Incident.query
        .join(Site)
        .filter(Site.user_id == _effective_user_id())
        .order_by(Incident.opened_at.desc())
        .limit(limit)
        .all()
    )
    
    return jsonify([{
        "id": inc.id,
        "site_id": inc.site_id,
        "site_name": inc.site.display_name(),
        "site_url": inc.site.url,
        "status": inc.status,
        "opened_at": inc.opened_at.isoformat() + "Z",
        "resolved_at": inc.resolved_at.isoformat() + "Z" if inc.resolved_at else None,
        "duration": str(inc.resolved_at - inc.opened_at) if inc.resolved_at else None,
        "error_message": inc.opened_error_message or "Unknown failure",
    } for inc in incidents])


@api_bp.route("/sites", methods=["GET"])
@login_required
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


@web_bp.route("/export/site/<int:site_id>", methods=["GET"])
@login_required
def download_site_report(site_id):
    site = _get_owned_site_or_404(site_id)
    fmt = request.args.get("format", "json").lower()

    from app.services.report_service import generate_site_report, generate_site_pdf_report
    
    if fmt == "pdf":
        pdf_bytes = generate_site_pdf_report(site.id)
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"report_{site.id}_{now_utc().strftime('%Y%m%d')}.pdf"
        )
    elif fmt == "csv":
        report = generate_site_report(site.id)
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["Metric", "Value"])
        cw.writerow(["Site", site.url])
        cw.writerow(["Status", site.current_status])
        cw.writerow(["SEO Score", site.seo_score])
        cw.writerow(["SSL State", site.ssl_state])
        cw.writerow(["DNS Integrity", "Verified" if site.dns_resolved else "Issue"])
        
        output = si.getvalue()
        return send_file(
            BytesIO(output.encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"report_{site.id}.csv"
        )
    else:
        report = generate_site_report(site.id)
        from flask import Response
        import json
        return Response(
            json.dumps(report, indent=2),
            mimetype="application/json",
            headers={"Content-disposition": f"attachment; filename=report_{site.id}.json"}
        )


@api_bp.route("/sites/<int:site_id>", methods=["GET"])
@login_required
def get_site(site_id):
    site = _get_owned_site_or_404(site_id)
    latest_uptime = UptimeLog.query.filter_by(site_id=site.id).order_by(UptimeLog.checked_at.desc()).first()
    latest_ssl = SSLLog.query.filter_by(site_id=site.id).order_by(SSLLog.checked_at.desc()).first()
    latest_seo = SEOLog.query.filter_by(site_id=site.id).order_by(SEOLog.checked_at.desc()).first()
    latest_dns = DNSLog.query.filter_by(site_id=site.id).order_by(DNSLog.checked_at.desc()).first()
    payload = site.to_dict()
    payload.update({
        "latest_uptime": latest_uptime.to_dict() if latest_uptime else None,
        "latest_ssl": latest_ssl.to_dict() if latest_ssl else None,
        "latest_seo": latest_seo.to_dict() if latest_seo else None,
        "latest_dns": latest_dns.to_dict() if latest_dns else None,
        "seo": _serialize_site_seo(site, latest_seo),
        "lighthouse": {
            "performance_score": site.lh_performance_score,
            "lcp_ms": site.lh_lcp_ms,
            "cls": site.lh_cls,
            "has_data": site.lh_performance_score is not None,
        },
    })
    return jsonify(payload)


@api_bp.route("/sites/<int:site_id>", methods=["DELETE"])
@login_required
def delete_site(site_id):
    site = _get_owned_site_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    return jsonify({"message": "Site deleted"})


@api_bp.route("/sites/<int:site_id>", methods=["PUT"])
@login_required
def update_site(site_id):
    site = _get_owned_site_or_404(site_id)
    data = request.get_json() or {}
    
    # Update allowed fields
    if 'name' in data:
        site.name = (data.get('name') or "").strip() or None
    if 'check_interval' in data:
        site.check_interval = _parse_interval(data.get('check_interval'), default=site.check_interval, minimum=30)
    if 'uptime_check_interval' in data:
        site.uptime_check_interval = _parse_interval(data.get('uptime_check_interval'), default=site.uptime_check_interval, minimum=30)
    if 'ssl_check_interval' in data:
        site.ssl_check_interval = _parse_interval(data.get('ssl_check_interval'), default=site.ssl_check_interval, minimum=3600)
    if 'seo_check_interval' in data:
        site.seo_check_interval = _parse_interval(data.get('seo_check_interval'), default=site.seo_check_interval, minimum=3600)
    if 'dns_check_interval' in data:
        site.dns_check_interval = _parse_interval(data.get('dns_check_interval'), default=site.dns_check_interval, minimum=300)
    
    # Prevent URL changes
    if 'url' in data or 'normalized_url' in data:
        return jsonify({"error": "URL cannot be changed"}), 400
    
    from app.services.monitoring_service import refresh_next_check_at
    refresh_next_check_at(site)
    db.session.commit()
    return jsonify(site.to_dict())


@api_bp.route("/sites/<int:site_id>/check", methods=["POST"])
@login_required
def run_all_checks(site_id):
    site = _get_owned_site_or_404(site_id)
    statuses = {}
    should_skip, skip_reason = should_skip_seo_for_cooldown(site)
    for check_type, task in (("uptime", run_uptime_check_task), ("ssl", run_ssl_check_task), ("security", run_security_check_task), ("dns", run_dns_check_task)):
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
@login_required
def uptime_history(site_id):
    site = _get_owned_site_or_404(site_id)
    days = request.args.get("days", 7, type=int)
    cutoff = now_utc() - timedelta(days=max(days, 1))
    logs = UptimeLog.query.filter(UptimeLog.site_id == site.id, UptimeLog.checked_at >= cutoff).order_by(UptimeLog.checked_at.desc()).limit(500).all()
    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/sites/<int:site_id>/history/ssl", methods=["GET"])
@login_required
def ssl_history(site_id):
    site = _get_owned_site_or_404(site_id)
    limit = request.args.get("limit", 10, type=int)
    logs = SSLLog.query.filter_by(site_id=site.id).order_by(SSLLog.checked_at.desc()).limit(min(limit, 100)).all()
    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/sites/<int:site_id>/history/seo", methods=["GET"])
@login_required
def seo_history(site_id):
    site = _get_owned_site_or_404(site_id)
    limit = request.args.get("limit", 5, type=int)
    logs = SEOLog.query.filter_by(site_id=site.id).order_by(SEOLog.checked_at.desc()).limit(min(limit, 100)).all()
    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/sites/<int:site_id>/history/dns", methods=["GET"])
@login_required
def dns_history(site_id):
    site = _get_owned_site_or_404(site_id)
    limit = request.args.get("limit", 10, type=int)
    logs = DNSLog.query.filter_by(site_id=site.id).order_by(DNSLog.checked_at.desc()).limit(min(limit, 100)).all()
    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/sites/<int:site_id>/uptime-summary", methods=["GET"])
@login_required
def uptime_summary(site_id):
    site = _get_owned_site_or_404(site_id)
    days = request.args.get("days", 30, type=int)
    cutoff = (now_utc() - timedelta(days=max(days, 1))).date()
    rows = DailyUptimeSummary.query.filter(DailyUptimeSummary.site_id == site.id, DailyUptimeSummary.summary_date >= cutoff).order_by(DailyUptimeSummary.summary_date.asc()).all()
    return jsonify([row.to_dict() for row in rows])


# ▶️ Trigger check manually
@api_bp.route("/check/<int:site_id>", methods=["GET"])
@login_required
def check_site(site_id):
    site = _get_owned_site_or_404(site_id)
    result = _safe_delay(run_uptime_check_task, site.id)
    return jsonify({"message": "Uptime check requested", "dispatch": result}), 202 if result["status"] == "queued" else 503


@api_bp.route("/check-seo/<int:site_id>", methods=["GET"])
@login_required
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
@login_required
def check_site_ssl(site_id):
    site = _get_owned_site_or_404(site_id)
    result = _safe_delay(run_ssl_check_task, site.id)
    return jsonify({"message": "SSL check requested", "dispatch": result}), 202 if result["status"] == "queued" else 503


@api_bp.route("/check-security/<int:site_id>", methods=["GET"])
@login_required
def check_site_security(site_id):
    site = _get_owned_site_or_404(site_id)
    result = _safe_delay(run_security_check_task, site.id)
    return jsonify({"message": "Security check requested", "dispatch": result}), 202 if result["status"] == "queued" else 503


@api_bp.route("/check-dns/<int:site_id>", methods=["GET"])
@login_required
def check_site_dns(site_id):
    site = _get_owned_site_or_404(site_id)
    result = _safe_delay(run_dns_check_task, site.id)
    return jsonify({"message": "DNS check requested", "dispatch": result}), 202 if result["status"] == "queued" else 503


@api_bp.route("/logs/<int:site_id>", methods=["GET"])
@login_required
def get_logs(site_id):
    site = _get_owned_site_or_404(site_id)
    logs = UptimeLog.query.filter_by(site_id=site.id)\
        .order_by(UptimeLog.id.desc())\
        .limit(10)\
        .all()

    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/seo-logs/<int:site_id>", methods=["GET"])
@login_required
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
@login_required
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
        "checked_at":      log.checked_at.isoformat() + "Z",
        "links_checked":   log.links_checked,
        "broken_link_count": log.broken_link_count,
        "broken_links":    log.broken_links or {},
    })


@api_bp.route("/sites/<int:site_id>/check", methods=["POST"])
@login_required
def trigger_site_check(site_id):
    """Unified endpoint to trigger specific or all checks."""
    site = _get_owned_site_or_404(site_id)
    data = request.get_json() or {}
    check_type = data.get("type", "all")
    
    dispatch = {}
    
    # Mark as running immediately so UI shows scanning state
    if any(getattr(site, f"{t}_status") in ["running", "queued"] for t in ["uptime", "ssl", "seo", "security", "dns"]):
        site.app_status = "checking"
    site.is_processing = True
    
    if check_type == "uptime" or check_type == "all":
        site.uptime_status = "queued"
        dispatch["uptime"] = _safe_delay(run_uptime_check_task, site.id)
    if check_type == "ssl" or check_type == "all":
        site.ssl_status = "queued"
        dispatch["ssl"] = _safe_delay(run_ssl_check_task, site.id)
    if check_type == "seo" or check_type == "all":
        site.seo_status = "queued"
        dispatch["seo"] = _safe_delay(run_seo_check_task, site.id)
    if check_type == "security" or check_type == "all":
        site.security_status = "queued"
        dispatch["security"] = _safe_delay(run_security_check_task, site.id)
    if check_type == "dns" or check_type == "all":
        site.dns_status = "queued"
        dispatch["dns"] = _safe_delay(run_dns_check_task, site.id)
    
    db.session.commit()
    
    return jsonify({"message": f"Checks triggered: {check_type}", "dispatch": dispatch})


@api_bp.route("/sites/<int:site_id>/report", methods=["GET"])
@login_required
def download_site_report(site_id):
    """Generate and return site report in requested format."""
    site = _get_owned_site_or_404(site_id)
    fmt = request.args.get("format", "json").lower()
    
    from app.services.report_service import generate_site_report
    report_data = generate_site_report(site.id)
    
    if not report_data:
        return jsonify({"error": "Failed to generate report"}), 500
        
    if fmt == "pdf":
        from app.services.report_service import generate_site_pdf_report
        pdf_data = generate_site_pdf_report(site.id)
        return Response(
            pdf_data,
            mimetype="application/pdf",
            headers={"Content-disposition": f"attachment; filename=report_{site.id}.pdf"}
        )
        
    if fmt == "csv":
        import io, csv
        from flask import Response
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Category", "Metric", "Value", "Checked At"])
        
        # Uptime
        writer.writerow(["Uptime", "Status", report_data["uptime"]["current_status"], report_data["uptime"]["last_check_at"]])
        writer.writerow(["Uptime", "Latency (ms)", int(report_data["uptime"]["last_response_time"]*1000) if report_data["uptime"]["last_response_time"] else "N/A", ""])
        
        # SSL
        writer.writerow(["SSL", "Issuer", report_data["ssl"]["issuer"], report_data["ssl"]["last_check_at"]])
        writer.writerow(["SSL", "Days Remaining", report_data["ssl"]["days_remaining"], ""])
        
        # SEO
        writer.writerow(["SEO", "Score", report_data["seo"]["score"], report_data["seo"]["last_check_at"]])
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=report_{site.id}.csv"}
        )
    
    # Default to JSON
    from flask import Response
    import json
    return Response(
        json.dumps(report_data, indent=2),
        mimetype="application/json",
        headers={"Content-disposition": f"attachment; filename=report_{site.id}.json"}
    )


@api_bp.route("/sites/<int:site_id>/tech-stack", methods=["GET"])
@login_required
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
        "checked_at": log.checked_at.isoformat() + "Z",
        "tech_stack": log.tech_stack or {},
        "tech_flat":  log.tech_flat or [],
        "tech_diff":  log.tech_diff or {},
        "server":     (log.signals or {}).get("server", "") if log.signals else "",
    })


@api_bp.route("/sites/<int:site_id>/lighthouse", methods=["GET"])
@login_required
def get_lighthouse_data(site_id: int):
    """
    Return Lighthouse CWV data from the most recent valid SEO scan.

    Returns 404 if no Lighthouse audit has been run yet for this site.
    """
    site = _get_owned_site_or_404(site_id)

    log = (
        SEOLog.query
        .filter_by(site_id=site.id, fetch_valid=True)
        .filter(SEOLog.lh_audited_at.isnot(None))
        .order_by(SEOLog.checked_at.desc())
        .first()
    )

    if log is None:
        return jsonify({
            "error": (
                "No Lighthouse audit available yet. "
                "Audits run automatically during SEO checks."
            ),
            "site_id": site_id,
        }), 404

    return jsonify({
        "performance_score": log.lh_performance_score,
        "audit_method": log.lh_audit_method or "playwright_perf",
        "audited_at": log.lh_audited_at.isoformat() + "Z" if log.lh_audited_at else None,
        "error": log.lh_error,
        "metrics": {
            "lcp": {
                "value_ms": log.lh_lcp_ms,
                "rating": log.lh_lcp_rating or compute_cwv_rating("lcp", log.lh_lcp_ms),
            },
            "fcp": {
                "value_ms": log.lh_fcp_ms,
                "rating": log.lh_fcp_rating or compute_cwv_rating("fcp", log.lh_fcp_ms),
            },
            "tbt": {
                "value_ms": log.lh_tbt_ms,
                "rating": log.lh_tbt_rating or compute_cwv_rating("tbt", log.lh_tbt_ms),
            },
            "cls": {
                "value": log.lh_cls,
                "rating": log.lh_cls_rating or compute_cwv_rating("cls", log.lh_cls),
            },
            "ttfb": {
                "value_ms": log.lh_ttfb_ms,
                "rating": log.lh_ttfb_rating or compute_cwv_rating("ttfb", log.lh_ttfb_ms),
            },
            "tti": {
                "value_ms": log.lh_tti_ms,
                "rating": "n/a",
            },
            "si": {
                "value_ms": log.lh_si_ms,
                "rating": "n/a",
            },
        },
        "page_load_ms": log.lh_page_load_ms,
    })


@api_bp.route("/sites/<int:site_id>/analytics", methods=["GET"])
@login_required
def get_analytics(site_id):
    """Return trend analytics for a site. Query: ?days=30"""
    from app.services.analytics_service import get_site_analytics
    site = _get_owned_site_or_404(site_id)
    days = request.args.get("days", 30, type=int)
    return jsonify(get_site_analytics(site.id, days=days))


@api_bp.route("/incidents/<int:incident_id>", methods=["GET"])
@login_required
def get_incident(incident_id):
    """Return full incident detail including timeline and root cause."""
    from app.models.incident import Incident
    incident = (
        Incident.query
        .join(Site, Site.id == Incident.site_id)
        .filter(Incident.id == incident_id, Site.user_id == _effective_user_id())
        .first()
    )
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
    return jsonify(incident.to_dict())


@api_bp.route("/sites/<int:site_id>/incidents", methods=["GET"])
@login_required
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
@login_required
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
        "checked_at":        log.checked_at.isoformat(),
        # New fields
        "security_score":    log.security_score,
        "grade":             log.security_grade,
        "categories":        log.security_categories or {},
        "cors_issues":       log.cors_issues or [],
        "csp_issues":        log.csp_issues or [],
        "mixed_content_detail": log.mixed_content_detail or {},
        # Backward-compatible flat fields
        "security_headers":  log.security_headers or {},
        "security_issues":   log.security_issues or [],
        "malware_flags":     log.malware_flags or [],
    })


@api_bp.route("/sites/<int:site_id>/dns", methods=["GET"])
@login_required
def get_dns(site_id):
    site = _get_owned_site_or_404(site_id)
    log = DNSLog.query.filter_by(site_id=site.id).order_by(DNSLog.checked_at.desc()).first()
    if not log:
        return jsonify({"error": "No DNS check data yet"}), 404
    return jsonify(log.to_dict())


@api_bp.route("/site/<int:site_id>/status", methods=["GET"])
@login_required
def get_site_status(site_id):
    site = _get_owned_site_or_404(site_id)
    
    # SaaS: If logs exist but status is stuck, force ready (Truth logic)
    if site.app_status == "pending" and site.last_uptime_check_at:
        site.refresh_app_status()
        db.session.commit()

    return jsonify(site.to_dict())


@web_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("register.html"), 400
        user, error, status = _register_user(request.form.get("email"), password)
        if error:
            flash(error, "error")
            return render_template("register.html"), status
        flash("Account created successfully.", "success")
        return redirect(url_for("web.dashboard"))
    return render_template("register.html")


@web_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user, error, status = _login_user(request.form.get("email"), request.form.get("password"))
        if error:
            flash(error, "error")
            return render_template("login.html"), status
        return redirect(url_for("web.dashboard"))
    return render_template("login.html")


@web_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("web.login"))


@web_bp.route("/", methods=["GET"])
@login_required
def dashboard():
    sites = _owned_sites_query().order_by(Site.created_at.desc()).all()
    from app.services.monitoring_service import ensure_dns_monitoring_defaults
    if ensure_dns_monitoring_defaults(sites):
        sites = _owned_sites_query().order_by(Site.created_at.desc()).all()
    site_ids = [site.id for site in sites]
    recent_uptime_logs = UptimeLog.query.filter(UptimeLog.site_id.in_(site_ids)).order_by(UptimeLog.checked_at.desc()).limit(12).all() if site_ids else []
    recent_ssl_logs = SSLLog.query.filter(SSLLog.site_id.in_(site_ids)).order_by(SSLLog.checked_at.desc()).limit(8).all() if site_ids else []
    recent_seo_logs = SEOLog.query.filter(SEOLog.site_id.in_(site_ids)).order_by(SEOLog.checked_at.desc()).limit(8).all() if site_ids else []
    recent_dns_logs = DNSLog.query.filter(DNSLog.site_id.in_(site_ids)).order_by(DNSLog.checked_at.desc()).limit(8).all() if site_ids else []
    response_samples = [site.last_response_time for site in sites if site.last_response_time is not None]

    return render_template(
        "dashboard.html",
        metrics=_build_dashboard_metrics(sites, response_samples),
        site_cards=sites,
        recent_uptime_logs=recent_uptime_logs,
        recent_ssl_logs=recent_ssl_logs,
        recent_seo_logs=recent_seo_logs,
        recent_dns_logs=recent_dns_logs,
    )


@web_bp.route("/site/<int:site_id>", methods=["GET"])
@login_required
def site_detail(site_id):
    site = _get_owned_site_or_404(site_id)
    from app.models.incident import Incident
    from app.services.analytics_service import get_site_analytics

    uptime_logs = (
        UptimeLog.query.filter_by(site_id=site.id)
        .order_by(UptimeLog.checked_at.desc())
        .limit(20)
        .all()
    )
    ssl_logs = (
        SSLLog.query.filter_by(site_id=site.id)
        .order_by(SSLLog.checked_at.desc())
        .limit(10)
        .all()
    )
    seo_logs = (
        SEOLog.query.filter_by(site_id=site.id)
        .order_by(SEOLog.checked_at.desc())
        .limit(10)
        .all()
    )
    dns_logs = (
        DNSLog.query.filter_by(site_id=site.id)
        .order_by(DNSLog.checked_at.desc())
        .limit(10)
        .all()
    )
    recent_incidents = (
        Incident.query.filter_by(site_id=site.id)
        .order_by(Incident.opened_at.desc())
        .limit(10)
        .all()
    )
    analytics = get_site_analytics(site.id, days=30)

    return render_template(
        "site_detail.html",
        site=site,
        uptime_logs=uptime_logs,
        ssl_logs=ssl_logs,
        seo_logs=seo_logs,
        dns_logs=dns_logs,
        uptime_breakdown=Counter("Up" if log.is_up else "Down" for log in uptime_logs),
        recent_incidents=recent_incidents,
        analytics=analytics,
    )


@web_bp.route("/site/<int:site_id>/download-report", methods=["GET"])
@login_required
def download_report(site_id):
    """Download site monitoring report as JSON, CSV, or PDF."""
    site = _get_owned_site_or_404(site_id)
    
    report = generate_site_report(site.id)
    if not report:
        flash("Report could not be generated.", "error")
        return redirect(url_for("web.site_detail", site_id=site_id))
    
    format_type = request.args.get('format', 'json').lower()
    
    if format_type == 'csv':
        # Generate CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Site info
        writer.writerow(['Section', 'Key', 'Value'])
        writer.writerow(['Site', 'ID', site.id])
        writer.writerow(['Site', 'Name', site.name or ''])
        writer.writerow(['Site', 'URL', site.url])
        writer.writerow(['Site', 'Current Status', site.current_status])
        writer.writerow(['Site', 'Uptime Status', site.uptime_status])
        writer.writerow(['Site', 'SSL Status', site.ssl_status])
        writer.writerow(['Site', 'SEO Status', site.seo_status])
        writer.writerow(['Site', 'SEO Score', site.seo_score])
        writer.writerow(['Site', 'SSL Days Remaining', site.ssl_days_remaining or ''])
        
        # Uptime logs
        for log in report.get('uptime_logs', []):
            writer.writerow(['Uptime', 'Checked At', log.get('checked_at')])
            writer.writerow(['Uptime', 'Status Code', log.get('status_code')])
            writer.writerow(['Uptime', 'Response Time', log.get('response_time')])
            writer.writerow(['Uptime', 'TTFB', log.get('ttfb')])
            writer.writerow(['Uptime', 'Is Up', log.get('is_up')])
            writer.writerow(['Uptime', 'Status', log.get('status')])
            writer.writerow(['Uptime', 'Error', log.get('error_message') or ''])
        
        # SSL logs
        for log in report.get('ssl_logs', []):
            writer.writerow(['SSL', 'Checked At', log.get('checked_at')])
            writer.writerow(['SSL', 'Expiry Date', log.get('expiry_date')])
            writer.writerow(['SSL', 'Days Remaining', log.get('days_remaining')])
            writer.writerow(['SSL', 'Is Valid', log.get('is_valid')])
            writer.writerow(['SSL', 'State', log.get('state')])
            writer.writerow(['SSL', 'Issuer', log.get('issuer') or ''])
            writer.writerow(['SSL', 'Error', log.get('error_message') or ''])
        
        # SEO logs
        for log in report.get('seo_logs', []):
            writer.writerow(['SEO', 'Checked At', log.get('checked_at')])
            writer.writerow(['SEO', 'Score', log.get('score')])
            writer.writerow(['SEO', 'Status', log.get('status')])
            writer.writerow(['SEO', 'Title', log.get('title') or ''])
            writer.writerow(['SEO', 'Meta Description', log.get('meta_description') or ''])
            # Add more fields as needed
        
        csv_content = output.getvalue()
        csv_bytes = BytesIO(csv_content.encode('utf-8'))
        filename = f"site_report_{site.id}_{site.display_name().replace(' ', '_').replace('/', '_')}.csv"
        return send_file(
            csv_bytes,
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename
        )
    
    elif format_type == 'pdf':
        # Generate PDF
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        elements.append(Paragraph(f"Site Report: {site.display_name()}", styles['Title']))
        elements.append(Spacer(1, 12))
        
        # Site info
        elements.append(Paragraph("Site Information", styles['Heading2']))
        data = [
            ['URL', site.url],
            ['Current Status', site.current_status],
            ['Uptime Status', site.uptime_status],
            ['SSL Status', site.ssl_status],
            ['SEO Status', site.seo_status],
            ['SEO Score', str(site.seo_score)],
            ['SSL Days Remaining', str(site.ssl_days_remaining or 'N/A')],
        ]
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))
        
        # Recent Uptime Logs
        elements.append(Paragraph("Recent Uptime Logs", styles['Heading2']))
        uptime_data = [['Checked At', 'Status Code', 'Response Time', 'Status']]
        for log in report.get('uptime_logs', [])[:10]:
            uptime_data.append([
                str(log.get('checked_at')),
                str(log.get('status_code')),
                f"{log.get('response_time', 0) * 1000:.0f}ms",
                log.get('status')
            ])
        uptime_table = Table(uptime_data)
        uptime_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(uptime_table)
        
        doc.build(elements)
        buffer.seek(0)
        filename = f"site_report_{site.id}_{site.display_name().replace(' ', '_').replace('/', '_')}.pdf"
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    
    else:
        # Default JSON
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
@login_required
def create_site():
    name = (request.form.get("name") or "").strip() or None
    url = (request.form.get("url") or "").strip()
    interval = request.form.get("check_interval", type=int) or 60

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

    # SaaS Initialization
    site.app_status = "checking"
    site.uptime_status = "pending"
    site.ssl_status = "pending"
    site.seo_status = "pending"
    site.security_status = "pending"
    site.dns_status = "pending"
    db.session.commit()
 
    dispatch = [
        _safe_delay(run_uptime_check_task, site.id),
        _safe_delay(run_ssl_check_task, site.id),
        _safe_delay(run_seo_check_task, site.id),
        _safe_delay(run_security_check_task, site.id),
        _safe_delay(run_dns_check_task, site.id),
    ]

    if all(item["status"] == "queued" for item in dispatch):
        flash("Website added and SaaS analysis started.", "success")
    else:
        flash("Website added, but background checks could not be queued. Start Redis/Celery and run checks manually.", "error")
    return redirect(url_for("web.site_detail", site_id=site.id))


@web_bp.route("/site/<int:site_id>/run/<check_type>", methods=["POST"])
@login_required
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
    elif check_type == "security":
        _safe_delay(run_security_check_task, site_id)
        message = f"Security audit queued for {site.url}."
    elif check_type == "dns":
        _safe_delay(run_dns_check_task, site_id)
        message = f"DNS check queued for {site.url}."
    elif check_type == "all":
        _safe_delay(run_full_audit_task, site_id)
        message = f"Full SaaS monitoring suite queued for {site.url}."
    else:
        abort(404)

    flash(message, "success")
    next_url = request.form.get("next") or url_for("web.site_detail", site_id=site_id)
    return redirect(next_url)


@web_bp.route("/site/<int:site_id>/analytics", methods=["GET"])
@login_required
def site_analytics(site_id):
    site = _get_owned_site_or_404(site_id)
    from app.services.analytics_service import get_site_analytics

    days = request.args.get("days", 30, type=int)
    analytics = get_site_analytics(site.id, days=days)

    return render_template(
        "site_analytics.html",
        site=site,
        analytics=analytics,
        days=days,
    )


@web_bp.route("/site/<int:site_id>/delete", methods=["POST"])
@login_required
def delete_site_web(site_id):
    site = _get_owned_site_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    flash("Site deleted.", "success")
    return redirect(url_for("web.dashboard"))


def _build_dashboard_metrics(sites, response_samples):
    monitored_sites = len(sites)
    sites_up = sum(1 for site in sites if site.current_status == "UP")
    sites_down = sum(1 for site in sites if site.current_status == "DOWN")
    avg_response = mean(response_samples) if response_samples else None
    health_score = round((sites_up / monitored_sites) * 100) if monitored_sites else 0
    seo_avg = round(sum(s.seo_score for s in sites) / monitored_sites) if monitored_sites else 0

    return {
        "monitored_sites": monitored_sites,
        "sites_up": sites_up,
        "sites_down": sites_down,
        "avg_response": avg_response,
        "health_score": health_score,
        "seo_avg_score": seo_avg,
    }


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
    if not user_id:
        abort(401)
    return int(user_id)


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
