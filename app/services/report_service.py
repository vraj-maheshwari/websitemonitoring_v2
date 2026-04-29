"""
services/report_service.py
--------------------------
Report generation for site monitoring data.
"""

import json
from datetime import datetime
from app.models.site import Site
from app.models.uptime_log import UptimeLog
from app.models.ssl_log import SSLLog
from app.models.seo_log import SEOLog


def generate_site_report(site_id: int) -> dict:
    """
    Generate a comprehensive report for a site including all monitoring data.
    """
    site = Site.query.get(site_id)
    if not site:
        return None

    # Latest logs
    latest_uptime = UptimeLog.query.filter_by(site_id=site_id).order_by(UptimeLog.checked_at.desc()).first()
    latest_ssl = SSLLog.query.filter_by(site_id=site_id).order_by(SSLLog.checked_at.desc()).first()
    latest_seo = SEOLog.query.filter_by(site_id=site_id).order_by(SEOLog.checked_at.desc()).first()

    # Recent history (last 10 records)
    uptime_history = [log.to_dict() for log in UptimeLog.query.filter_by(site_id=site_id).order_by(UptimeLog.checked_at.desc()).limit(10).all()]
    ssl_history = [log.to_dict() for log in SSLLog.query.filter_by(site_id=site_id).order_by(SSLLog.checked_at.desc()).limit(10).all()]
    seo_history = [log.to_dict() for log in SEOLog.query.filter_by(site_id=site_id).order_by(SEOLog.checked_at.desc()).limit(5).all()]

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "site": {
            "id": site.id,
            "name": site.display_name(),
            "url": site.url,
            "created_at": site.created_at.isoformat() if site.created_at else None,
        },
        "current_status": {
            "app_status": site.app_status,
            "uptime_status": site.uptime_status,
            "ssl_status": site.ssl_status,
            "seo_status": site.seo_status,
        },
        "uptime": {
            "current_status": site.current_status,
            "last_response_time": site.last_response_time,
            "last_status_code": site.last_status_code,
            "last_ttfb": site.last_ttfb,
            "last_error_message": site.last_error_message,
            "last_check_at": site.last_uptime_check_at.isoformat() if site.last_uptime_check_at else None,
            "latest_log": latest_uptime.to_dict() if latest_uptime else None,
            "recent_history": uptime_history,
        },
        "ssl": {
            "state": site.ssl_state,
            "issuer": site.ssl_issuer,
            "expiry_date": site.ssl_expiry_date.isoformat() if site.ssl_expiry_date else None,
            "days_remaining": site.ssl_days_remaining,
            "last_error": site.ssl_last_error,
            "last_check_at": site.last_ssl_check_at.isoformat() if site.last_ssl_check_at else None,
            "latest_log": latest_ssl.to_dict() if latest_ssl else None,
            "recent_history": ssl_history,
        },
        "seo": {
            "score": site.seo_score,
            "state": site.seo_state,
            "last_error": site.seo_last_error,
            "last_check_at": site.last_seo_check_at.isoformat() if site.last_seo_check_at else None,
            "latest_log": _seo_log_to_dict(latest_seo) if latest_seo else None,
            "recent_history": [_seo_log_to_dict(log) for log in SEOLog.query.filter_by(site_id=site_id).order_by(SEOLog.checked_at.desc()).limit(5).all()],
        },
        "configuration": {
            "uptime_check_interval": site.uptime_check_interval,
            "ssl_check_interval": site.ssl_check_interval,
            "seo_check_interval": site.seo_check_interval,
            "next_uptime_check_at": site.next_uptime_check_at.isoformat() if site.next_uptime_check_at else None,
            "next_ssl_check_at": site.next_ssl_check_at.isoformat() if site.next_ssl_check_at else None,
            "next_seo_check_at": site.next_seo_check_at.isoformat() if site.next_seo_check_at else None,
        },
    }

    return report


def _seo_log_to_dict(log) -> dict:
    """Convert SEOLog to dictionary, handling JSON fields safely."""
    if not log:
        return None

    return {
        "id": log.id,
        "site_id": log.site_id,
        "score": log.score,
        "status": log.status,
        "checked_at": log.checked_at.isoformat() if log.checked_at else None,
        "on_page": {
            "title": log.title,
            "title_length": log.title_length,
            "meta_description": log.meta_description,
            "meta_length": log.meta_length,
            "h1_count": log.h1_count,
            "h2_count": log.h2_count,
            "h3_count": log.h3_count,
            "word_count": log.word_count,
        },
        "technical": {
            "has_robots": log.has_robots,
            "has_sitemap": log.has_sitemap,
            "canonical": log.canonical,
            "has_favicon": log.has_favicon,
            "has_hreflang": log.has_hreflang,
            "robots_meta": log.robots_meta,
            "html_lang": log.html_lang,
        },
        "content": {
            "image_count": log.image_count,
            "missing_alt_count": log.missing_alt_count,
            "internal_link_count": log.internal_link_count,
            "external_link_count": log.external_link_count,
        },
        "performance": {
            "page_size_kb": log.page_size_kb,
            "js_blocking_count": log.js_blocking_count,
            "css_blocking_count": log.css_blocking_count,
            "ttfb": log.ttfb,
        },
        "mobile_and_security": {
            "has_viewport": log.has_viewport,
            "mobile_friendly": log.mobile_friendly,
            "https_redirect": log.https_redirect,
            "mixed_content_count": log.mixed_content_count,
        },
        "score_breakdown": log.score_breakdown,
        "issues": log.issues,
        "recommendations": log.recommendations,
        "error_message": log.error_message,
    }
