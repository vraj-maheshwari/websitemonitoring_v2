from datetime import datetime, timezone

def now_utc() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

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
