from datetime import datetime, timezone
import os
from zoneinfo import ZoneInfo

def now_utc() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

def get_local_timezone():
    """Get the configured local timezone."""
    tz_name = os.getenv("TIMEZONE", "UTC")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc

def now_local() -> datetime:
    """Return current datetime in local timezone."""
    return datetime.now(get_local_timezone())

def to_local(dt: datetime | None) -> datetime | None:
    """Convert UTC datetime to local timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(get_local_timezone())

def normalize(dt: datetime | None) -> datetime | None:
    """Ensure every datetime has tzinfo=UTC. Convert naive -> aware safely."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def assert_utc(dt: datetime | None) -> None:
    """Guard: Raise error if naive datetime is detected in debug mode."""
    if dt and dt.tzinfo is None:
        raise ValueError("Naive datetime detected - must be UTC aware")
