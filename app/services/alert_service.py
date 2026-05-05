"""
services/alert_service.py
--------------------------
Alert dispatcher.

Currently writes to stdout (mock). In production, swap
send_alert() internals with SendGrid / Twilio / PagerDuty etc.
"""

import logging
from datetime import datetime, timedelta

from app.config.settings import Config
from app.extensions import db
from app.models.alert_history import AlertHistory
from app.models.incident import Incident
from app.services.incident_service import (
    open_incident_with_rca,
    update_incident_timeline,
    resolve_incident_with_timeline,
)
from app.services.teams_service import send_teams_alert
from app.utils.time import now_utc

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
                f"Time:    {now_utc().isoformat()}"
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
                f"Time:          {now_utc().isoformat()}"
            ),
        )


def check_ssl_alerts(site, is_valid: bool,
                     days_remaining: int | None, expiry_date, checked_at: datetime) -> None:
    """Fire alert when SSL is invalid or expiring within the warning window."""

    if not is_valid:
        _send_alert(
            level="CRITICAL",
            subject=f"[SSL INVALID] {site.url}",
            body=(
                f"Website: {site.url}\n"
                f"Issue:   SSL certificate is invalid or could not be retrieved.\n"
                f"Time:    {checked_at.isoformat()}"
            ),
        )
        _notify_site(site, None, "SSL_INVALID", checked_at, error_message="SSL Invalid")
        return

    if days_remaining is not None and days_remaining <= Config.SSL_EXPIRY_WARNING_DAYS:
        event_type = "SSL_EXPIRED" if days_remaining < 0 else "SSL_EXPIRY_WARNING"
        # Both EXPIRED and EXPIRY_WARNING are rate-limited to once per day.
        if _daily_alert_sent(site.id, event_type, checked_at):
            return
        
        if days_remaining < 0:
            _send_alert(
                level="CRITICAL",
                subject=f"[SSL EXPIRED] {site.url} — expired {-days_remaining} days ago",
                body=(
                    f"Website:     {site.url}\n"
                    f"Expiry date: {expiry_date}\n"
                    f"Expired:     {-days_remaining} days ago\n"
                    f"Time:        {checked_at.isoformat()}"
                ),
            )
        else:
            _send_alert(
                level="WARNING",
                subject=f"[SSL EXPIRING] {site.url} — {days_remaining} days left",
                body=(
                    f"Website:     {site.url}\n"
                    f"Expiry date: {expiry_date}\n"
                    f"Days left:   {days_remaining}\n"
                    f"Time:        {checked_at.isoformat()}"
                ),
            )
        _notify_site(site, None, event_type, checked_at, days_remaining=days_remaining)


def check_seo_alerts(site, score: int, status: str, checked_at: datetime,
                     old_score: int | None = None) -> None:
    """Notify on SEO regression. Uses old_score passed from the caller to avoid
    comparing the new score against itself after the log has been saved."""
    if old_score is None:
        logger.debug("Skipping SEO regression alert for site %s: no previous score baseline", site.id)
        return

    if score is not None and score < old_score - 5:
        _send_alert(
            level="WARNING",
            subject=f"[SEO REGRESSION] {site.url} dropped from {old_score} to {score}",
            body=f"Website: {site.url}\nPrevious score: {old_score}\nCurrent score: {score}\nStatus: {status}\nTime: {checked_at.isoformat()}",
        )
        _notify_site(site, None, "SEO_REGRESSION", checked_at, seo_score=score)


def check_dns_alerts(site, result: dict, checked_at: datetime) -> None:
    if result.get("hijack_suspected"):
        _notify_site(
            site,
            None,
            "DNS_HIJACK",
            checked_at,
            expected_ips=result.get("expected_ips") or [],
            new_ips=result.get("new_ips") or [],
        )

    if result.get("ns_changed"):
        _notify_site(
            site,
            None,
            "DNS_NS_CHANGE",
            checked_at,
            added_ns=result.get("added_ns") or [],
            removed_ns=result.get("removed_ns") or [],
        )


def handle_uptime_transition(site, previous_status: str | None, current_status: str,
                             status_code: int | None, response_time: float | None,
                             error_message: str | None, checked_at: datetime) -> None:
    previous_status = previous_status or "PENDING"

    if current_status == "DOWN" and previous_status != "DOWN":
        # Fresh DOWN transition — open incident and alert
        incident = _open_incident(site, status_code, response_time, error_message, checked_at)
        _notify_site(site, incident, "DOWN", checked_at, status_code, response_time, error_message)
        return

    # Mid-incident: site still DOWN — append timeline event
    # Also re-open incident if it was lost (e.g. worker restart with no open incident)
    if previous_status == "DOWN" and current_status == "DOWN":
        incident = (
            Incident.query
            .filter_by(site_id=site.id, status="OPEN")
            .order_by(Incident.opened_at.desc())
            .first()
        )
        if incident is None:
            # No open incident found — worker restarted or incident was lost.
            # Re-open and re-alert so Teams gets notified.
            incident = _open_incident(site, status_code, response_time, error_message, checked_at)
            _notify_site(site, incident, "DOWN", checked_at, status_code, response_time, error_message)
        else:
            # Incident exists — check if an alert was ever sent for it.
            # If not (e.g. incident predates Teams integration), send one now.
            db.session.flush()  # ensure incident.id is set
            alert_ever_sent = (
                AlertHistory.query
                .filter_by(site_id=site.id, incident_id=incident.id, event_type="DOWN")
                .first()
            )
            if alert_ever_sent is None:
                logger.info(
                    "[ALERT] site_id=%s incident_id=%s has no prior DOWN alert — sending now",
                    site.id, incident.id,
                )
                _notify_site(site, incident, "DOWN", checked_at, status_code, response_time, error_message)
            else:
                update_incident_timeline(incident, current_status, status_code, response_time, error_message, checked_at)
        return

    if previous_status == "DOWN" and current_status != "DOWN":
        incident = _resolve_incident(site, status_code, response_time, error_message, checked_at)
        _notify_site(site, incident, "RECOVERY", checked_at, status_code, response_time, error_message)


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
        open_incident_with_rca(incident, status_code, response_time, error_message, checked_at)

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
        resolve_incident_with_timeline(incident, status_code, response_time, error_message, checked_at)

    site.incident_opened_at = None
    site.last_incident_resolved_at = checked_at
    return incident


def _notify_site(site, incident, event_type: str, checked_at: datetime,
                 status_code: int | None = None, response_time: float | None = None,
                 error_message: str | None = None, days_remaining: int | None = None,
                 seo_score: int | None = None, expected_ips: list[str] | None = None,
                 new_ips: list[str] | None = None, added_ns: list[str] | None = None,
                 removed_ns: list[str] | None = None) -> None:
    if incident is not None and incident.id is None:
        db.session.flush()
    incident_id = incident.id if incident and incident.id else None
    if _cooldown_active(site.id, incident_id, event_type, checked_at):
        logger.info(
            "[TEAMS] Cooldown active — skipping %s alert for site_id=%s incident_id=%s",
            event_type, site.id, incident_id,
        )
        return

    subject = _build_subject(site.display_name(), event_type)
    body = _build_body(
        site,
        event_type,
        checked_at,
        status_code,
        response_time,
        error_message,
        days_remaining,
        seo_score,
        expected_ips,
        new_ips,
        added_ns,
        removed_ns,
    )

    history = AlertHistory(
        site_id=site.id,
        incident_id=incident_id,
        event_type=event_type,
        recipient="Microsoft Teams",
        subject=subject,
        body=body,
        delivery_status="PENDING",
        sent_at=checked_at,
    )
    db.session.add(history)
    db.session.flush()

    try:
        send_teams_alert(subject, body)
        history.delivery_status = "SENT"
        logger.info(
            "[TEAMS] Alert SENT site_id=%s event=%s incident_id=%s",
            site.id, event_type, incident_id,
        )
    except Exception as exc:  # noqa: BLE001
        history.delivery_status = "FAILED"
        history.error_message = str(exc)
        logger.error(
            "[TEAMS] Alert FAILED site_id=%s event=%s error=%s",
            site.id, event_type, exc,
        )


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


def _daily_alert_sent(site_id: int, event_type: str, checked_at: datetime) -> bool:
    start_of_day = checked_at.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        AlertHistory.query
        .filter(AlertHistory.site_id == site_id)
        .filter(AlertHistory.event_type == event_type)
        .filter(AlertHistory.sent_at >= start_of_day)
        .first()
        is not None
    )


def _build_subject(site_name: str, event_type: str) -> str:
    if event_type == "DOWN":
        return f"[DOWN] {site_name} is unreachable"
    if event_type == "RECOVERY":
        return f"[RECOVERY] {site_name} is back online"
    if event_type == "SSL_INVALID":
        return f"[SSL INVALID] {site_name}"
    if event_type in {"SSL_EXPIRING", "SSL_EXPIRY_WARNING"}:
        return f"[SSL EXPIRING] {site_name}"
    if event_type == "SSL_EXPIRED":
        return f"[SSL EXPIRED] {site_name}"
    if event_type == "SEO_REGRESSION":
        return f"[SEO REGRESSION] {site_name}"
    if event_type == "SEO_CRITICAL":
        return f"[SEO CRITICAL] {site_name}"
    if event_type == "SEO_WARNING":
        return f"[SEO WARNING] {site_name}"
    if event_type == "DNS_HIJACK":
        return f"[DNS HIJACK SUSPECTED] {site_name}"
    if event_type == "DNS_NS_CHANGE":
        return f"[DNS NS CHANGE] {site_name}"
    return f"[ALERT] {site_name}: {event_type}"


def _build_body(site, event_type: str, checked_at: datetime, status_code: int | None,
                response_time: float | None, error_message: str | None,
                days_remaining: int | None = None, seo_score: int | None = None,
                expected_ips: list[str] | None = None, new_ips: list[str] | None = None,
                added_ns: list[str] | None = None, removed_ns: list[str] | None = None) -> str:
    body = (
        f"Site name: {site.display_name()}\n"
        f"URL: {site.url}\n"
        f"Event: {event_type}\n"
        f"Timestamp: {checked_at.isoformat()}\n"
    )

    if event_type in ["DOWN", "RECOVERY"]:
        body += f"Status code: {status_code if status_code is not None else 'N/A'}\n"
        body += f"Response time: {f'{response_time:.2f}s' if response_time is not None else 'N/A'}\n"

    if event_type in ["SSL_EXPIRING", "SSL_EXPIRY_WARNING", "SSL_EXPIRED"]:
        body += f"Days remaining: {days_remaining}\n"

    if event_type in ["SEO_CRITICAL", "SEO_WARNING", "SEO_REGRESSION"]:
        body += f"SEO Score: {seo_score}\n"

    if event_type == "DNS_HIJACK":
        body += f"Previous IPs: {', '.join(expected_ips or []) or 'N/A'}\n"
        body += f"New unexpected IPs: {', '.join(new_ips or []) or 'N/A'}\n"

    if event_type == "DNS_NS_CHANGE":
        body += f"Added NS records: {', '.join(added_ns or []) or 'N/A'}\n"
        body += f"Removed NS records: {', '.join(removed_ns or []) or 'N/A'}\n"

    if error_message:
        body += f"Error: {error_message}\n"

    return body
