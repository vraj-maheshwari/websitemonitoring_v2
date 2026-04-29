from datetime import datetime, timedelta

from app.config.settings import Config
from app.extensions import db
from app.models.alert_history import AlertHistory
from app.models.incident import Incident
from app.models.seo_log import SEOLog
from app.models.ssl_log import SSLLog
from app.models.uptime_log import UptimeLog
from app.utils.time import now_utc


def run_retention_cycle() -> dict:
    cutoff = now_utc() - timedelta(days=Config.LOG_RETENTION_DAYS)

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
        "deleted_ssl":    deleted_ssl,
        "deleted_seo":    deleted_seo,
        "deleted_incidents": deleted_incidents,
        "deleted_alerts": deleted_alerts,
    }
