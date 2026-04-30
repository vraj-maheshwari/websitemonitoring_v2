from datetime import datetime, time, timedelta, timezone

from sqlalchemy import case, func

from app.extensions import db
from app.models.daily_seo_summary import DailySEOSummary
from app.models.daily_ssl_summary import DailySSLSummary
from app.models.daily_uptime_summary import DailyUptimeSummary
from app.models.seo_log import SEOLog
from app.models.ssl_log import SSLLog
from app.models.site import Site
from app.models.uptime_log import UptimeLog
from app.utils.time import now_utc


def run_daily_summary(target_date=None) -> dict:
    if target_date is None:
        target_date = (now_utc() - timedelta(days=1)).date()

    uptime = _populate_daily_uptime_summary(target_date)
    ssl = _populate_daily_ssl_summary(target_date)
    seo = _populate_daily_seo_summary(target_date)
    db.session.commit()
    return {
        "date": target_date.isoformat(),
        "processed_sites": uptime,
        "ssl_sites": ssl,
        "seo_sites": seo,
    }


def _populate_daily_uptime_summary(target_date) -> int:
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    processed = 0

    for site_id in [row.id for row in Site.query.with_entities(Site.id).all()]:
        row = (
            db.session.query(
                func.count(UptimeLog.id).label("total_checks"),
                func.sum(case((UptimeLog.status == "UP", 1), else_=0)).label("up_checks"),
                func.sum(case((UptimeLog.status == "DOWN", 1), else_=0)).label("down_checks"),
                func.sum(case((UptimeLog.status == "DEGRADED", 1), else_=0)).label("degraded_checks"),
                func.avg(UptimeLog.response_time).label("avg_response_time"),
                func.avg(UptimeLog.ttfb).label("avg_ttfb"),
            )
            .filter(UptimeLog.site_id == site_id)
            .filter(UptimeLog.checked_at >= start)
            .filter(UptimeLog.checked_at < end)
            .one()
        )

        total = int(row.total_checks or 0)
        up_checks = int(row.up_checks or 0)
        summary = DailyUptimeSummary.query.filter_by(site_id=site_id, summary_date=target_date).first()
        if summary is None:
            summary = DailyUptimeSummary(site_id=site_id, summary_date=target_date)
            db.session.add(summary)

        summary.total_checks = total
        summary.up_checks = up_checks
        summary.down_checks = int(row.down_checks or 0)
        summary.degraded_checks = int(row.degraded_checks or 0)
        summary.outage_count = summary.down_checks
        summary.uptime_percentage = round((up_checks / total) * 100, 2) if total else 0.0
        summary.avg_response_time = round(float(row.avg_response_time), 4) if row.avg_response_time is not None else None
        summary.avg_ttfb = round(float(row.avg_ttfb), 4) if row.avg_ttfb is not None else None
        processed += 1

    return processed


def _populate_daily_ssl_summary(target_date) -> int:
    """Aggregate SSLLog rows for target_date into DailySSLSummary."""
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    processed = 0

    for site_id in [row.id for row in Site.query.with_entities(Site.id).all()]:
        row = (
            db.session.query(
                func.count(SSLLog.id).label("total_checks"),
                func.sum(case((SSLLog.is_valid == True, 1), else_=0)).label("valid_count"),  # noqa: E712
                func.avg(SSLLog.days_remaining).label("avg_days_remaining"),
            )
            .filter(SSLLog.site_id == site_id)
            .filter(SSLLog.checked_at >= start)
            .filter(SSLLog.checked_at < end)
            .one()
        )

        total = int(row.total_checks or 0)
        if total == 0:
            continue

        summary = DailySSLSummary.query.filter_by(site_id=site_id, summary_date=target_date).first()
        if summary is None:
            summary = DailySSLSummary(site_id=site_id, summary_date=target_date)
            db.session.add(summary)

        summary.total_checks = total
        summary.valid_count = int(row.valid_count or 0)
        summary.avg_days_remaining = round(float(row.avg_days_remaining), 1) if row.avg_days_remaining is not None else None
        processed += 1

    return processed


def _populate_daily_seo_summary(target_date) -> int:
    """Aggregate SEOLog rows for target_date into DailySEOSummary."""
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    processed = 0

    for site_id in [row.id for row in Site.query.with_entities(Site.id).all()]:
        row = (
            db.session.query(
                func.count(SEOLog.id).label("total_checks"),
                func.avg(SEOLog.score).label("avg_score"),
                func.min(SEOLog.score).label("min_score"),
                func.max(SEOLog.score).label("max_score"),
            )
            .filter(SEOLog.site_id == site_id)
            .filter(SEOLog.checked_at >= start)
            .filter(SEOLog.checked_at < end)
            .filter(SEOLog.fetch_valid == True)  # noqa: E712 — only score valid fetches
            .one()
        )

        total = int(row.total_checks or 0)
        if total == 0:
            continue

        summary = DailySEOSummary.query.filter_by(site_id=site_id, summary_date=target_date).first()
        if summary is None:
            summary = DailySEOSummary(site_id=site_id, summary_date=target_date)
            db.session.add(summary)

        summary.total_checks = total
        summary.avg_score = round(float(row.avg_score), 2) if row.avg_score is not None else 0.0
        summary.min_score = int(row.min_score) if row.min_score is not None else None
        summary.max_score = int(row.max_score) if row.max_score is not None else None
        processed += 1

    return processed
