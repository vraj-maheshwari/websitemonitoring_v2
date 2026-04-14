from datetime import datetime, timedelta

from sqlalchemy import case, func

from app.config.settings import Config
from app.extensions import db
from app.models.daily_uptime_summary import DailyUptimeSummary
from app.models.seo_log import SEOLog
from app.models.ssl_log import SSLLog
from app.models.uptime_log import UptimeLog


def run_retention_cycle() -> dict:
    cutoff = datetime.utcnow() - timedelta(days=Config.LOG_RETENTION_DAYS)
    _aggregate_uptime_logs(cutoff)

    deleted_uptime = UptimeLog.query.filter(UptimeLog.checked_at < cutoff).delete(synchronize_session=False)
    deleted_ssl = SSLLog.query.filter(SSLLog.checked_at < cutoff).delete(synchronize_session=False)
    deleted_seo = SEOLog.query.filter(SEOLog.checked_at < cutoff).delete(synchronize_session=False)
    db.session.commit()

    return {
        "deleted_uptime": deleted_uptime,
        "deleted_ssl": deleted_ssl,
        "deleted_seo": deleted_seo,
    }


def _aggregate_uptime_logs(cutoff: datetime) -> None:
    grouped_rows = (
        db.session.query(
            UptimeLog.site_id,
            func.date(UptimeLog.checked_at).label("summary_date"),
            func.count(UptimeLog.id).label("total_checks"),
            func.avg(case((UptimeLog.is_up.is_(True), 1.0), else_=0.0)).label("uptime_ratio"),
            func.avg(UptimeLog.response_time).label("avg_response_time"),
            func.sum(case((UptimeLog.is_up.is_(False), 1), else_=0)).label("outage_count"),
        )
        .filter(UptimeLog.checked_at < cutoff)
        .group_by(UptimeLog.site_id, func.date(UptimeLog.checked_at))
        .all()
    )

    for row in grouped_rows:
        summary_date = row.summary_date
        if isinstance(summary_date, str):
            summary_date = datetime.strptime(summary_date, "%Y-%m-%d").date()
        summary = (
            DailyUptimeSummary.query
            .filter_by(site_id=row.site_id, summary_date=summary_date)
            .first()
        )
        if summary is None:
            summary = DailyUptimeSummary(site_id=row.site_id, summary_date=summary_date)
            db.session.add(summary)

        summary.total_checks = int(row.total_checks or 0)
        summary.uptime_percentage = round((row.uptime_ratio or 0.0) * 100, 2)
        summary.avg_response_time = round(row.avg_response_time, 4) if row.avg_response_time is not None else None
        summary.outage_count = int(row.outage_count or 0)

    db.session.commit()
