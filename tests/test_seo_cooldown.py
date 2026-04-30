from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.services.seo_service import should_skip_seo_for_cooldown


def test_no_cooldown_if_never_down():
    site = MagicMock()
    site.last_downtime_ended_at = None
    skip, _reason = should_skip_seo_for_cooldown(site)
    assert skip is False


def test_cooldown_active_right_after_recovery():
    site = MagicMock()
    site.last_downtime_ended_at = datetime.now(timezone.utc) - timedelta(seconds=30)
    skip, reason = should_skip_seo_for_cooldown(site)
    assert skip is True
    assert "cooldown" in reason.lower()


def test_cooldown_expired_after_2_minutes():
    site = MagicMock()
    site.last_downtime_ended_at = datetime.now(timezone.utc) - timedelta(seconds=150)
    skip, _reason = should_skip_seo_for_cooldown(site)
    assert skip is False
