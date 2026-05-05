import logging
from datetime import datetime, timedelta

from app.config.settings import Config
from app.extensions import db
from app.models.site import Site
from app.utils.urls import normalize_url
from app.utils.time import now_utc, normalize

logger = logging.getLogger(__name__)

CHECK_UPTIME = "uptime"
CHECK_SSL = "ssl"
CHECK_SEO = "seo"
CHECK_SECURITY = "security"
CHECK_DNS = "dns"

STATUS_PENDING = "PENDING"
STATUS_UP = "UP"
STATUS_DOWN = "DOWN"
STATUS_DEGRADED = "DEGRADED"


def prepare_site(site: Site) -> Site:
    canonical_url, normalized_url = normalize_url(site.url)
    site.url = canonical_url
    site.normalized_url = normalized_url
    if not site.name:
        site.name = canonical_url.split("//", 1)[-1]

    now = now_utc()
    if site.next_uptime_check_at is None:
        site.next_uptime_check_at = now
    if site.next_ssl_check_at is None:
        site.next_ssl_check_at = now
    if site.next_seo_check_at is None:
        site.next_seo_check_at = now
    if site.next_security_check_at is None:
        site.next_security_check_at = now
    if site.next_dns_check_at is None:
        site.next_dns_check_at = now
    refresh_next_check_at(site)
    return site


def ensure_dns_monitoring_defaults(sites: list[Site] | None = None) -> int:
    """
    Seed DNS scheduling fields for sites created before DNS monitoring existed.
    """
    query = Site.query
    if sites is not None:
        site_ids = [site.id for site in sites if site.id is not None]
        if not site_ids:
            return 0
        query = query.filter(Site.id.in_(site_ids))

    stale_sites = (
        query
        .filter((Site.next_dns_check_at.is_(None)) | (Site.dns_status.is_(None)))
        .all()
    )
    if not stale_sites:
        return 0

    now = now_utc()
    for site in stale_sites:
        if site.next_dns_check_at is None:
            site.next_dns_check_at = now
        if site.dns_status is None:
            site.dns_status = "pending"
        refresh_next_check_at(site)

    db.session.commit()
    return len(stale_sites)


def refresh_next_check_at(site: Site) -> None:
    upcoming = [normalize(dt) for dt in [
        site.next_uptime_check_at,
        site.next_ssl_check_at,
        site.next_seo_check_at,
        site.next_security_check_at,
        site.next_dns_check_at,
    ] if dt is not None]
    site.next_check_at = min(upcoming) if upcoming else None


def get_interval_seconds(site: Site, check_type: str) -> int:
    if check_type == CHECK_SSL:
        return max(site.ssl_check_interval or 86400, 3600)
    if check_type == CHECK_SEO:
        return max(site.seo_check_interval or 604800, 3600)
    if check_type == CHECK_SECURITY:
        return max(site.security_check_interval or 86400, 3600)
    if check_type == CHECK_DNS:
        return max(site.dns_check_interval or 3600, 300)
    return max(site.uptime_check_interval or site.check_interval or 60, 30)


def schedule_next_run(site: Site, check_type: str, checked_at: datetime) -> None:
    next_run = checked_at + timedelta(seconds=get_interval_seconds(site, check_type))
    if check_type == CHECK_UPTIME:
        site.last_uptime_check_at = checked_at
        site.next_uptime_check_at = next_run
    elif check_type == CHECK_SSL:
        site.last_ssl_check_at = checked_at
        site.next_ssl_check_at = next_run
    elif check_type == CHECK_SEO:
        site.last_seo_check_at = checked_at
        site.next_seo_check_at = next_run
    elif check_type == CHECK_SECURITY:
        site.last_security_check_at = checked_at
        site.next_security_check_at = next_run
    elif check_type == CHECK_DNS:
        site.last_dns_check_at = checked_at
        site.next_dns_check_at = next_run

    refresh_next_check_at(site)


def get_due_site_ids(check_type: str, now: datetime | None = None, limit: int = 100) -> list[int]:
    now = normalize(now) or now_utc()
    if check_type == CHECK_DNS:
        ensure_dns_monitoring_defaults()
    field = _get_due_field(check_type)
    query = (
        Site.query
        .filter(field.isnot(None))
        .filter(field <= now)
        .order_by(field.asc())
        .limit(limit)
    )
    return [site.id for site in query.all()]


def _get_due_field(check_type: str):
    if check_type == CHECK_SSL:
        return Site.next_ssl_check_at
    if check_type == CHECK_SEO:
        return Site.next_seo_check_at
    if check_type == CHECK_SECURITY:
        return Site.next_security_check_at
    if check_type == CHECK_DNS:
        return Site.next_dns_check_at
    return Site.next_uptime_check_at
