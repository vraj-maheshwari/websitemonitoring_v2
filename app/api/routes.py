from collections import Counter
from statistics import mean

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.seo_log import SEOLog
from app.models.site import Site
from app.models.site_notification import SiteNotification
from app.models.ssl_log import SSLLog
from app.models.uptime_log import UptimeLog
from app.services.monitor_service import run_uptime_check
from app.services.monitoring_service import prepare_site
from app.services.seo_service import run_seo_check
from app.services.ssl_service import run_ssl_check
from app.utils.urls import normalize_url
from app.workers.runtime_tasks import run_seo_check_task, run_ssl_check_task, run_uptime_check_task

api_bp = Blueprint("api", __name__)
web_bp = Blueprint("web", __name__)

# ➕ Add site
@api_bp.route("/sites", methods=["POST"])
def add_site():
    data = request.get_json() or {}

    url = data.get("url")
    name = (data.get("name") or "").strip() or None
    interval = data.get("check_interval", 60)
    emails = data.get("emails") or []

    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        canonical_url, normalized_url = normalize_url(url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    site = Site(name=name, url=canonical_url, normalized_url=normalized_url, check_interval=interval)
    prepare_site(site)
    db.session.add(site)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Site already exists"}), 409

    for email in emails:
        recipient = (email or "").strip()
        if recipient:
            db.session.add(SiteNotification(site_id=site.id, email=recipient, is_active=True))
    db.session.commit()

    return jsonify({"message": "Site added", "id": site.id})


# 📃 List sites
@api_bp.route("/sites", methods=["GET"])
def list_sites():
    sites = Site.query.order_by(Site.created_at.desc()).all()
    return jsonify([site.to_dict() for site in sites])


# ▶️ Trigger check manually
@api_bp.route("/check/<int:site_id>", methods=["GET"])
def check_site(site_id):
    task = run_uptime_check_task.delay(site_id)
    return jsonify({"message": "Uptime check started", "task_id": task.id})


@api_bp.route("/check-seo/<int:site_id>", methods=["GET"])
def check_site_seo(site_id):
    task = run_seo_check_task.delay(site_id)
    return jsonify({"message": "SEO check started", "task_id": task.id})


@api_bp.route("/check-ssl/<int:site_id>", methods=["GET"])
def check_site_ssl(site_id):
    task = run_ssl_check_task.delay(site_id)
    return jsonify({"message": "SSL check started", "task_id": task.id})


@api_bp.route("/logs/<int:site_id>", methods=["GET"])
def get_logs(site_id):
    logs = UptimeLog.query.filter_by(site_id=site_id)\
        .order_by(UptimeLog.id.desc())\
        .limit(10)\
        .all()

    return jsonify([log.to_dict() for log in logs])


@api_bp.route("/seo-logs/<int:site_id>", methods=["GET"])
def get_seo_logs(site_id):
    logs = (
        SEOLog.query.filter_by(site_id=site_id)
        .order_by(SEOLog.checked_at.desc())
        .limit(10)
        .all()
    )
    return jsonify([log.to_dict() for log in logs])


@web_bp.route("/", methods=["GET"])
def dashboard():
    sites = Site.query.order_by(Site.created_at.desc()).all()
    recent_uptime_logs = UptimeLog.query.order_by(UptimeLog.checked_at.desc()).limit(12).all()
    recent_ssl_logs = SSLLog.query.order_by(SSLLog.checked_at.desc()).limit(8).all()
    recent_seo_logs = SEOLog.query.order_by(SEOLog.checked_at.desc()).limit(8).all()
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
    site = db.session.get(Site, site_id)
    if site is None:
        abort(404)

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

    return render_template(
        "site_detail.html",
        site=site,
        summary=site,
        uptime_logs=uptime_logs,
        ssl_logs=ssl_logs,
        seo_logs=seo_logs,
        uptime_breakdown=Counter("Up" if log.is_up else "Down" for log in uptime_logs),
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

    site = Site(name=name, url=canonical_url, normalized_url=normalized_url, check_interval=max(interval, 30))
    prepare_site(site)
    db.session.add(site)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("That website is already being monitored.", "error")
        return redirect(url_for("web.dashboard"))

    for recipient in _parse_notification_emails(emails_raw):
        db.session.add(SiteNotification(site_id=site.id, email=recipient, is_active=True))
    db.session.commit()

    flash("Website added to the monitoring dashboard.", "success")
    return redirect(url_for("web.site_detail", site_id=site.id))


@web_bp.route("/site/<int:site_id>/run/<check_type>", methods=["POST"])
def run_check(site_id, check_type):
    site = db.session.get(Site, site_id)
    if site is None:
        abort(404)

    if check_type == "uptime":
        run_uptime_check_task.delay(site_id)
        message = f"Uptime check queued for {site.url}."
    elif check_type == "ssl":
        run_ssl_check_task.delay(site_id)
        message = f"SSL certificate check queued for {site.url}."
    elif check_type == "seo":
        run_seo_check_task.delay(site_id)
        message = f"SEO audit queued for {site.url}."
    elif check_type == "all":
        run_uptime_check_task.delay(site_id)
        run_ssl_check_task.delay(site_id)
        run_seo_check_task.delay(site_id)
        message = f"Full monitoring suite queued for {site.url}."
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
