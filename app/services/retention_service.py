from datetime import date, datetime, timedelta

from app.config.settings import Config
from app.extensions import db
from app.models.alert_history import AlertHistory
from app.models.incident import Incident
from app.models.seo_log import SEOLog
from app.models.ssl_log import SSLLog
from app.models.uptime_log import UptimeLog
from app.services.summary_service import (
    _populate_daily_seo_summary,
    _populate_daily_ssl_summary,
    _populate_daily_uptime_summary,
)
from app.utils.time import now_utc


def run_retention_cycle() -> dict:
    cutoff = now_utc() - timedelta(days=Config.LOG_RETENTION_DAYS)
    cutoff_date = cutoff.date()

    # Aggregate SSL and SEO logs into daily summaries before deleting them,
    # mirroring the existing uptime aggregation pattern.
    _backfill_summaries_before_cutoff(cutoff_date)

    deleted_uptime = UptimeLog.query.filter(UptimeLog.checked_at < cutoff).delete(synchronize_session=False)
    deleted_ssl = SSLLog.query.filter(SSLLog.checked_at < cutoff).delete(synchronize_session=False)
    deleted_seo = SEOLog.query.filter(SEOLog.checked_at < cutoff).delete(synchronize_session=False)
    deleted_incidents = (
        Incident.query
        .filter(Incident.status != "OPEN")
        .filter(Incident.opened_at < cutoff)
        .delete(synchronize_session=False)
    )
    deleted_alerts = AlertHistory.query.filter(AlertHistory.sent_at < cutoff).delete(synchronize_session=False)
    db.session.commit()

    return {
        "deleted_uptime": deleted_uptime,
        "deleted_ssl": deleted_ssl,
        "deleted_seo": deleted_seo,
        "deleted_incidents": deleted_incidents,
        "deleted_alerts": deleted_alerts,
    }


def _backfill_summaries_before_cutoff(cutoff_date: date) -> None:
    """Ensure daily summaries exist for every day that is about to be deleted.

    We only need to backfill the single day at the cutoff boundary — older days
    were already summarised by previous retention runs or the nightly summary task.
    """
    target = cutoff_date
    _populate_daily_uptime_summary(target)
    _populate_daily_ssl_summary(target)
    _populate_daily_seo_summary(target)
    db.session.commit()
