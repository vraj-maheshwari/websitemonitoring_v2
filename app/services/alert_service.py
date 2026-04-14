"""
services/alert_service.py
--------------------------
Alert dispatcher.

Currently writes to stdout (mock). In production, swap
send_alert() internals with SendGrid / Twilio / PagerDuty etc.
"""

import logging
from datetime import datetime
from app.config.settings import Config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────────────────

def check_uptime_alerts(site_url: str, status_code: int | None,
                        response_time: float, is_up: bool) -> None:
    """Evaluate uptime result and fire alerts when thresholds are breached."""

    if not is_up:
        _send_alert(
            level="CRITICAL",
            subject=f"[DOWN] {site_url} is unreachable",
            body=(
                f"Website: {site_url}\n"
                f"Status:  {'No response' if status_code is None else status_code}\n"
                f"Time:    {datetime.utcnow().isoformat()}"
            ),
        )
        return

    if response_time > Config.RESPONSE_TIME_THRESHOLD:
        _send_alert(
            level="WARNING",
            subject=f"[SLOW] {site_url} responded in {response_time:.2f}s",
            body=(
                f"Website:       {site_url}\n"
                f"Response time: {response_time:.2f}s "
                f"(threshold: {Config.RESPONSE_TIME_THRESHOLD}s)\n"
                f"Status code:   {status_code}\n"
                f"Time:          {datetime.utcnow().isoformat()}"
            ),
        )


def check_ssl_alerts(site_url: str, is_valid: bool,
                     days_remaining: int | None, expiry_date) -> None:
    """Fire alert when SSL is invalid or expiring within the warning window."""

    if not is_valid:
        _send_alert(
            level="CRITICAL",
            subject=f"[SSL INVALID] {site_url}",
            body=(
                f"Website: {site_url}\n"
                f"Issue:   SSL certificate is invalid or could not be retrieved.\n"
                f"Time:    {datetime.utcnow().isoformat()}"
            ),
        )
        return

    if days_remaining is not None and days_remaining <= Config.SSL_EXPIRY_WARNING_DAYS:
        _send_alert(
            level="WARNING",
            subject=f"[SSL EXPIRING] {site_url} — {days_remaining} days left",
            body=(
                f"Website:     {site_url}\n"
                f"Expiry date: {expiry_date}\n"
                f"Days left:   {days_remaining}\n"
                f"Time:        {datetime.utcnow().isoformat()}"
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _send_alert(level: str, subject: str, body: str) -> None:
    """
    Mock alert dispatcher — replace with real transport as needed.

    Production options:
        - Email:   smtplib / SendGrid
        - Slack:   Incoming Webhooks
        - PagerDuty / OpsGenie: HTTP APIs
    """
    separator = "─" * 60
    message = (
        f"\n{separator}\n"
        f"🚨  ALERT [{level}]  |  {subject}\n"
        f"{separator}\n"
        f"{body}\n"
        f"{separator}\n"
    )
    logger.warning("ALERT [%s] %s", level, subject)


from datetime import timedelta

from app.extensions import db
from app.models.alert_history import AlertHistory
from app.models.incident import Incident
from app.models.site_notification import SiteNotification
from app.services.email_service import send_email


def handle_uptime_transition(site, previous_status: str | None, current_status: str,
                             status_code: int | None, response_time: float | None,
                             error_message: str | None, checked_at: datetime) -> None:
    previous_status = previous_status or "PENDING"

    if current_status == "DOWN" and previous_status != "DOWN":
        incident = _open_incident(site, status_code, response_time, error_message, checked_at)
        _notify_site(site, incident, "DOWN", checked_at, status_code, response_time, error_message)
        return

    if previous_status == "DOWN" and current_status != "DOWN":
        incident = _resolve_incident(site, status_code, response_time, error_message, checked_at)
        _notify_site(site, incident, "RECOVERY", checked_at, status_code, response_time, error_message)


def check_uptime_alerts(site_url: str, status_code: int | None,
                        response_time: float, is_up: bool) -> None:
    logger.debug(
        "Legacy check_uptime_alerts call for %s | status=%s | response_time=%s | is_up=%s",
        site_url, status_code, response_time, is_up,
    )


def check_ssl_alerts(site_url: str, is_valid: bool,
                     days_remaining: int | None, expiry_date) -> None:
    logger.debug(
        "Legacy check_ssl_alerts call for %s | is_valid=%s | days_remaining=%s | expiry=%s",
        site_url, is_valid, days_remaining, expiry_date,
    )


def _open_incident(site, status_code, response_time, error_message, checked_at):
    incident = (
        Incident.query
        .filter_by(site_id=site.id, status="OPEN")
        .order_by(Incident.opened_at.desc())
        .first()
    )
    if incident is None:
        incident = Incident(
            site_id=site.id,
            status="OPEN",
            opened_at=checked_at,
            opened_status_code=status_code,
            opened_response_time=response_time,
            opened_error_message=error_message,
        )
        db.session.add(incident)

    site.incident_opened_at = checked_at
    return incident


def _resolve_incident(site, status_code, response_time, error_message, checked_at):
    incident = (
        Incident.query
        .filter_by(site_id=site.id, status="OPEN")
        .order_by(Incident.opened_at.desc())
        .first()
    )
    if incident:
        incident.status = "RESOLVED"
        incident.resolved_at = checked_at
        incident.resolved_status_code = status_code
        incident.resolved_response_time = response_time
        incident.resolved_error_message = error_message

    site.incident_opened_at = None
    site.last_incident_resolved_at = checked_at
    return incident


def _notify_site(site, incident, event_type: str, checked_at: datetime,
                 status_code: int | None, response_time: float | None,
                 error_message: str | None) -> None:
    recipients = [
        notification.email
        for notification in SiteNotification.query
        .filter_by(site_id=site.id, is_active=True)
        .all()
    ]
    if not recipients:
        logger.info("No active recipients configured for site %s", site.id)
        return

    if incident is not None and incident.id is None:
        db.session.flush()
    incident_id = incident.id if incident and incident.id else None
    if _cooldown_active(site.id, incident_id, event_type, checked_at):
        logger.info("Skipping %s alert for site %s due to cooldown", event_type, site.id)
        return

    subject = _build_subject(site.display_name(), event_type)
    body = _build_body(site, event_type, checked_at, status_code, response_time, error_message)

    for recipient in recipients:
        history = AlertHistory(
            site_id=site.id,
            incident_id=incident_id,
            event_type=event_type,
            recipient=recipient,
            subject=subject,
            body=body,
            delivery_status="PENDING",
            sent_at=checked_at,
        )
        db.session.add(history)
        db.session.flush()

        try:
            send_email(recipient, subject, body)
            history.delivery_status = "SENT"
        except Exception as exc:  # noqa: BLE001
            history.delivery_status = "FAILED"
            history.error_message = str(exc)
            logger.exception("Failed to send %s alert for site %s", event_type, site.id)


def _cooldown_active(site_id: int, incident_id: int | None, event_type: str, checked_at: datetime) -> bool:
    cooldown_threshold = checked_at - timedelta(minutes=Config.ALERT_COOLDOWN_MINUTES)
    recent_alert = (
        AlertHistory.query
        .filter(AlertHistory.site_id == site_id)
        .filter(AlertHistory.event_type == event_type)
        .filter(AlertHistory.sent_at >= cooldown_threshold)
        .filter(AlertHistory.incident_id == incident_id)
        .order_by(AlertHistory.sent_at.desc())
        .first()
    )
    return recent_alert is not None


def _build_subject(site_name: str, event_type: str) -> str:
    if event_type == "DOWN":
        return f"[DOWN] {site_name} is unreachable"
    return f"[RECOVERY] {site_name} is back online"


def _build_body(site, event_type: str, checked_at: datetime, status_code: int | None,
                response_time: float | None, error_message: str | None) -> str:
    status_label = "DOWN" if event_type == "DOWN" else "UP"
    response_label = f"{response_time:.2f}s" if response_time is not None else "N/A"
    return (
        f"Site name: {site.display_name()}\n"
        f"URL: {site.url}\n"
        f"Status: {status_label}\n"
        f"Status code: {status_code if status_code is not None else 'N/A'}\n"
        f"Response time: {response_label}\n"
        f"Timestamp: {checked_at.isoformat()}\n"
        f"Error message: {error_message or 'N/A'}\n"
    )
