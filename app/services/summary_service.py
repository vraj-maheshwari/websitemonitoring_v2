from datetime import datetime, time, timedelta, timezone

from sqlalchemy import case, func

from app.extensions import db
from app.models.daily_uptime_summary import DailyUptimeSummary
from app.models.site import Site
from app.models.uptime_log import UptimeLog
from app.utils.time import now_utc


def run_daily_summary(target_date=None) -> dict:
    if target_date is None:
        target_date = (now_utc() - timedelta(days=1)).date()

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

    db.session.commit()
    return {"date": target_date.isoformat(), "processed_sites": processed}
