"""
services/analytics_service.py
-------------------------------
Converts stored logs and daily summaries into trend data for the analytics API.
All queries are read-only and designed to stay under 200ms.
"""

import logging
from datetime import timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.daily_seo_summary import DailySEOSummary
from app.models.daily_uptime_summary import DailyUptimeSummary
from app.models.uptime_log import UptimeLog
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

    return {
        "uptime_trend":         _uptime_trend(site_id, cutoff_date),
        "seo_trend":            _seo_trend(site_id, cutoff_date),
        "latency_distribution": _latency_distribution(site_id, cutoff),
        "avg_response_time_ms": _avg_response_ms(site_id, cutoff),
        "total_incidents":      _incident_count(site_id, cutoff),
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
