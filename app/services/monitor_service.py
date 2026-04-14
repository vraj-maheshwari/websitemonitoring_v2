"""
services/monitor_service.py
----------------------------
Uptime (HTTP) monitoring logic.
All DB writes and alert triggers live here — routes stay thin.
"""

import logging
from datetime import datetime

from app.config.settings import Config
from app.extensions import db
from app.models.site       import Site
from app.models.uptime_log import UptimeLog
from app.services          import alert_service
from app.services.monitoring_service import CHECK_UPTIME, STATUS_DEGRADED, STATUS_DOWN, STATUS_UP, schedule_next_run
from app.utils.http        import fetch_url

logger = logging.getLogger(__name__)


def run_uptime_check(site_id: int) -> UptimeLog | None:
    """
    Perform an HTTP uptime check for *site_id*.

    Steps:
      1. Load site from DB.
      2. Fetch the URL.
      3. Persist result as UptimeLog.
      4. Trigger alerts if thresholds are breached.

    Returns the saved UptimeLog or None if site not found.
    """
    site: Site | None = db.session.get(Site, site_id)
    if site is None:
        logger.warning("run_uptime_check: Site %s not found.", site_id)
        return None

    logger.info("Checking uptime for %s", site.url)
    previous_status = site.current_status
    checked_at = datetime.utcnow()
    result = fetch_url(site.url)

    if not result["is_up"]:
        current_status = STATUS_DOWN
    elif (result["response_time"] or 0.0) > Config.RESPONSE_TIME_THRESHOLD:
        current_status = STATUS_DEGRADED
    else:
        current_status = STATUS_UP

    log = UptimeLog(
        site_id=site.id,
        status_code=result["status_code"],
        response_time=result["response_time"],
        is_up=result["is_up"],
        error_message=result["error"],
        checked_at=checked_at,
    )
    site.current_status = current_status
    site.last_status_code = result["status_code"]
    site.last_response_time = result["response_time"]
    site.last_error_message = result["error"]
    schedule_next_run(site, CHECK_UPTIME, checked_at)
    db.session.add(log)

    # ── Alert evaluation ───────────────────────────────────────────────────
    alert_service.handle_uptime_transition(
        site=site,
        previous_status=previous_status,
        current_status=current_status,
        status_code=result["status_code"],
        response_time=result["response_time"],
        error_message=result["error"],
        checked_at=checked_at,
    )
    db.session.commit()

    logger.info(
        "Uptime check done — %s | status=%s | %.3fs | up=%s",
        site.url, result["status_code"], result["response_time"] or 0, result["is_up"]
    )
    return log


def get_uptime_logs(site_id: int, limit: int = 50) -> list[dict]:
    """Return the most recent *limit* uptime logs for a site."""
    logs = (
        UptimeLog.query
        .filter_by(site_id=site_id)
        .order_by(UptimeLog.checked_at.desc())
        .limit(limit)
        .all()
    )
    return [log.to_dict() for log in logs]
