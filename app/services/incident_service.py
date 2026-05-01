"""
services/incident_service.py
-----------------------------
Incident lifecycle management with timeline tracking and root cause analysis.
"""

import logging
from app.utils.time import now_utc

logger = logging.getLogger(__name__)

# ── Root cause categories ──────────────────────────────────────────────────

def detect_root_cause(error_message: str | None, status_code: int | None) -> str:
    """
    Classify the root cause of a downtime event.

    Returns one of: TIMEOUT | DNS | SERVER | CLIENT | UNKNOWN
    """
    err = (error_message or "").lower()
    if "timeout" in err or "timed out" in err or "time out" in err:
        return "TIMEOUT"
    if "dns" in err or "name resolution" in err or "nodename" in err or "getaddrinfo" in err:
        return "DNS"
    if status_code is not None and status_code >= 500:
        return "SERVER"
    if status_code is not None and status_code >= 400:
        return "CLIENT"
    if "connection refused" in err or "connect error" in err:
        return "CONNECTION"
    return "UNKNOWN"


# ── Timeline helpers ───────────────────────────────────────────────────────

def make_timeline_event(
    status: str,
    checked_at,
    response_time: float | None,
    status_code: int | None,
    error: str | None,
) -> dict:
    return {
        "status":        status,
        "time":          checked_at.isoformat(),
        "response_time": round(response_time, 3) if response_time is not None else None,
        "status_code":   status_code,
        "error":         error,
    }


def append_timeline_event(incident, event: dict) -> None:
    """Append one event to incident.timeline in-place (mutates the JSON column)."""
    current = list(incident.timeline or [])
    current.append(event)
    incident.timeline = current


def open_incident_with_rca(incident, status_code, response_time, error_message, checked_at):
    """
    Initialise a new incident: set root_cause and seed the timeline.
    Call this immediately after creating the Incident row.
    """
    incident.root_cause = detect_root_cause(error_message, status_code)
    incident.timeline = [
        make_timeline_event("DOWN", checked_at, response_time, status_code, error_message)
    ]
    logger.info(
        "[INCIDENT] site_id=%s opened — root_cause=%s",
        incident.site_id, incident.root_cause,
    )


def update_incident_timeline(incident, current_status, status_code, response_time, error, checked_at):
    """
    Append a mid-incident check event (DEGRADED or still DOWN).
    Only call when an incident is OPEN.
    """
    append_timeline_event(
        incident,
        make_timeline_event(current_status, checked_at, response_time, status_code, error),
    )


def resolve_incident_with_timeline(incident, status_code, response_time, error, checked_at):
    """
    Close the incident and append the final RECOVERY event.
    """
    append_timeline_event(
        incident,
        make_timeline_event("UP", checked_at, response_time, status_code, error),
    )
    incident.status = "RESOLVED"
    incident.resolved_at = checked_at
    incident.resolved_status_code = status_code
    incident.resolved_response_time = response_time
    incident.resolved_error_message = error

    # Normalize both datetimes to UTC-aware before subtraction
    from datetime import timezone as _tz
    opened = incident.opened_at
    if opened is not None and opened.tzinfo is None:
        opened = opened.replace(tzinfo=_tz.utc)
    closed = checked_at
    if closed is not None and closed.tzinfo is None:
        closed = closed.replace(tzinfo=_tz.utc)

    duration = str(closed - opened) if opened and closed else "unknown"
    logger.info(
        "[INCIDENT] site_id=%s resolved — duration=%s events=%d",
        incident.site_id,
        duration,
        len(incident.timeline or []),
    )
