"""
services/analytics_service.py
-------------------------------
Converts stored logs and daily summaries into trend data for the analytics API.
All queries are read-only and designed to stay under 200ms.
"""

import logging
from datetime import timedelta
from statistics import median

from sqlalchemy import func

from app.extensions import db
from app.models.daily_seo_summary import DailySEOSummary
from app.models.daily_uptime_summary import DailyUptimeSummary
from app.models.seo_log import SEOLog
from app.models.uptime_log import UptimeLog
from app.utils.lighthouse_runner import compute_cwv_rating
from app.utils.time import now_utc

logger = logging.getLogger(__name__)

# Latency buckets (seconds)
_FAST_THRESHOLD   = 1.0
_MEDIUM_THRESHOLD = 3.0


def get_site_analytics(site_id: int, days: int = 30) -> dict:
    """
    Return analytics data for a single site over the last `days` days.

    Shape:
    {
      "uptime_trend":          [{"date": "YYYY-MM-DD", "uptime_pct": float}, ...],
      "seo_trend":             [{"date": "YYYY-MM-DD", "avg_score": float}, ...],
      "latency_distribution":  {"fast": int, "medium": int, "slow": int},
      "avg_response_time_ms":  float | None,
      "total_incidents":       int,
      "period_days":           int,
    }
    """
    days = max(1, min(days, 90))
    cutoff = now_utc() - timedelta(days=days)
    cutoff_date = cutoff.date()

    uptime_trend = _uptime_trend(site_id, cutoff_date)
    uptime_summary = _daily_uptime_summary_aggregate(site_id, cutoff_date)
    seo_summary = _daily_seo_summary_aggregate(site_id, cutoff_date)
    ssl_info = _latest_ssl_info(site_id)
    lighthouse_data = _latest_lighthouse_data(site_id)
    min_rt, max_rt, median_rt = _response_time_stats(site_id, cutoff)

    return {
        "uptime_trend":         uptime_trend,
        "seo_trend":            _seo_trend(site_id, cutoff_date),
        "latency_distribution": _latency_distribution(site_id, cutoff),
        "avg_response_time_ms": _avg_response_ms(site_id, cutoff),
        "min_response_time_ms": min_rt,
        "max_response_time_ms": max_rt,
        "median_response_time_ms": median_rt,
        "total_checks":         uptime_summary["total_checks"],
        "uptime_checks":        uptime_summary["up_checks"],
        "downtime_checks":      uptime_summary["down_checks"],
        "uptime_percentage":    uptime_summary["uptime_percentage"],
        "incidents":            _incident_list(site_id, cutoff),
        "total_incidents":      _incident_count(site_id, cutoff),
        "ssl_expiry_days":      ssl_info["expiry_days"],
        "ssl_issuer":           ssl_info["issuer"],
        "ssl_expiry_date":      ssl_info["expiry_date"],
        "seo_score_avg":        seo_summary["avg_score"],
        "seo_checks_count":     seo_summary["total_checks"],
        "seo_score_min":        seo_summary["min_score"],
        "seo_score_max":        seo_summary["max_score"],
        "lighthouse_data":      lighthouse_data,
        "period_days":          days,
    }


# ── Private helpers ────────────────────────────────────────────────────────

def _uptime_trend(site_id: int, cutoff_date) -> list[dict]:
    rows = (
        DailyUptimeSummary.query
        .filter(
            DailyUptimeSummary.site_id == site_id,
            DailyUptimeSummary.summary_date >= cutoff_date,
        )
        .order_by(DailyUptimeSummary.summary_date.asc())
        .all()
    )
    return [
        {"date": r.summary_date.isoformat(), "uptime_pct": r.uptime_percentage}
        for r in rows
    ]


def _seo_trend(site_id: int, cutoff_date) -> list[dict]:
    rows = (
        DailySEOSummary.query
        .filter(
            DailySEOSummary.site_id == site_id,
            DailySEOSummary.summary_date >= cutoff_date,
        )
        .order_by(DailySEOSummary.summary_date.asc())
        .all()
    )
    return [
        {"date": r.summary_date.isoformat(), "avg_score": r.avg_score}
        for r in rows
    ]


def _daily_uptime_summary_aggregate(site_id: int, cutoff_date) -> dict:
    rows = (
        DailyUptimeSummary.query
        .filter(
            DailyUptimeSummary.site_id == site_id,
            DailyUptimeSummary.summary_date >= cutoff_date,
        )
        .all()
    )
    total_checks = sum(r.total_checks for r in rows)
    up_checks = sum(r.up_checks for r in rows)
    down_checks = sum(r.down_checks for r in rows)
    uptime_percentage = (up_checks / total_checks * 100) if total_checks else 0.0
    return {
        "total_checks": total_checks,
        "up_checks": up_checks,
        "down_checks": down_checks,
        "uptime_percentage": round(uptime_percentage, 1),
    }


def _daily_seo_summary_aggregate(site_id: int, cutoff_date) -> dict:
    rows = (
        DailySEOSummary.query
        .filter(
            DailySEOSummary.site_id == site_id,
            DailySEOSummary.summary_date >= cutoff_date,
        )
        .all()
    )
    total_checks = sum(r.total_checks for r in rows)
    weighted_score = sum((r.avg_score or 0.0) * r.total_checks for r in rows)
    avg_score = round(weighted_score / total_checks, 1) if total_checks else 0.0
    min_score = min((r.min_score for r in rows if r.min_score is not None), default=0)
    max_score = max((r.max_score for r in rows if r.max_score is not None), default=0)
    return {
        "total_checks": total_checks,
        "avg_score": avg_score,
        "min_score": min_score,
        "max_score": max_score,
    }


def _latest_ssl_info(site_id: int) -> dict:
    from app.models.ssl_log import SSLLog

    latest = (
        SSLLog.query
        .filter(SSLLog.site_id == site_id)
        .order_by(SSLLog.checked_at.desc())
        .first()
    )
    if not latest:
        return {"expiry_days": None, "issuer": None, "expiry_date": None}

    expiry_date = latest.expiry_date.isoformat() if latest.expiry_date else None
    return {
        "expiry_days": latest.days_remaining,
        "issuer": latest.issuer,
        "expiry_date": expiry_date,
    }


def _latest_lighthouse_data(site_id: int) -> dict | None:
    latest = (
        db.session.query(SEOLog)
        .filter(SEOLog.site_id == site_id, SEOLog.fetch_valid.is_(True), SEOLog.lh_audited_at.isnot(None))
        .order_by(SEOLog.checked_at.desc())
        .first()
    )
    if not latest:
        return None

    return {
        "lcp_avg": latest.lh_lcp_ms or 0.0,
        "cls_avg": latest.lh_cls or 0.0,
        "performance_avg": latest.lh_performance_score or 0,
        "lcp_rating": compute_cwv_rating("lcp", latest.lh_lcp_ms),
        "cls_rating": compute_cwv_rating("cls", latest.lh_cls),
        "performance_rating": compute_cwv_rating("performance", latest.lh_performance_score),
    }


def _incident_list(site_id: int, cutoff) -> list[dict]:
    from app.models.incident import Incident

    incidents = (
        Incident.query
        .filter(Incident.site_id == site_id, Incident.opened_at >= cutoff)
        .order_by(Incident.opened_at.desc())
        .all()
    )
    return [
        {
            "opened_at": incident.opened_at,
            "duration_minutes": int((incident.resolved_at - incident.opened_at).total_seconds() / 60) if incident.resolved_at else None,
            "root_cause": incident.root_cause,
        }
        for incident in incidents
    ]


def _response_time_stats(site_id: int, cutoff) -> tuple[float | None, float | None, float | None]:
    rows = (
        UptimeLog.query
        .filter(
            UptimeLog.site_id == site_id,
            UptimeLog.checked_at >= cutoff,
            UptimeLog.response_time.isnot(None),
        )
        .with_entities(UptimeLog.response_time)
        .all()
    )
    values = [round(rt * 1000, 1) for (rt,) in rows if rt is not None]
    if not values:
        return None, None, None
    return (
        min(values),
        max(values),
        round(median(values), 1),
    )


def _latency_distribution(site_id: int, cutoff) -> dict:
    logs = (
        UptimeLog.query
        .filter(
            UptimeLog.site_id == site_id,
            UptimeLog.checked_at >= cutoff,
            UptimeLog.response_time.isnot(None),
        )
        .with_entities(UptimeLog.response_time)
        .all()
    )
    fast = medium = slow = 0
    for (rt,) in logs:
        if rt < _FAST_THRESHOLD:
            fast += 1
        elif rt < _MEDIUM_THRESHOLD:
            medium += 1
        else:
            slow += 1
    return {"fast": fast, "medium": medium, "slow": slow}


def _avg_response_ms(site_id: int, cutoff) -> float | None:
    row = (
        db.session.query(func.avg(UptimeLog.response_time))
        .filter(
            UptimeLog.site_id == site_id,
            UptimeLog.checked_at >= cutoff,
            UptimeLog.response_time.isnot(None),
        )
        .scalar()
    )
    return round(row * 1000, 1) if row is not None else None


def _incident_count(site_id: int, cutoff) -> int:
    from app.models.incident import Incident
    return (
        Incident.query
        .filter(Incident.site_id == site_id, Incident.opened_at >= cutoff)
        .count()
    )


def get_fleet_analytics(user_id: int, days: int = 7) -> dict:
    """Aggregate analytics for all sites owned by a user."""
    from app.models.site import Site
    sites = Site.query.filter_by(user_id=user_id).all()
    site_ids = [s.id for s in sites]
    
    if not site_ids:
        return {
            "uptime_trend": [],
            "avg_latency": 0,
            "total_incidents": 0,
            "sites_count": 0
        }

    cutoff = now_utc() - timedelta(days=days)
    cutoff_date = cutoff.date()

    # Aggregate Uptime Trend (Fleet Avg)
    # Group by date and calculate avg uptime % across all sites
    trend_rows = (
        db.session.query(
            DailyUptimeSummary.summary_date,
            func.avg(DailyUptimeSummary.uptime_percentage)
        )
        .filter(
            DailyUptimeSummary.site_id.in_(site_ids),
            DailyUptimeSummary.summary_date >= cutoff_date
        )
        .group_by(DailyUptimeSummary.summary_date)
        .order_by(DailyUptimeSummary.summary_date.asc())
        .all()
    )
    
    uptime_trend = [
        {"date": r[0].strftime("%d %b"), "up": round(r[1], 1)} 
        for r in trend_rows
    ]

    # Avg Fleet Latency
    avg_latency_s = (
        db.session.query(func.avg(UptimeLog.response_time))
        .filter(UptimeLog.site_id.in_(site_ids), UptimeLog.checked_at >= cutoff)
        .scalar()
    ) or 0.0

    # Avg SSL Life
    from app.models.ssl_log import SSLLog
    avg_ssl_life = (
        db.session.query(func.avg(SSLLog.days_remaining))
        .filter(SSLLog.site_id.in_(site_ids), SSLLog.days_remaining > 0)
        .scalar()
    ) or 0

    # Total Incidents
    from app.models.incident import Incident
    total_incidents = (
        Incident.query
        .filter(Incident.site_id.in_(site_ids), Incident.opened_at >= cutoff)
        .count()
    )

    return {
        "uptime_trend": uptime_trend,
        "avg_latency": round(avg_latency_s * 1000),
        "avg_ssl_life": round(avg_ssl_life),
        "total_incidents": total_incidents,
        "sites_count": len(site_ids)
    }
