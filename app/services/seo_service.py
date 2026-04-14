"""
services/seo_service.py
------------------------
Basic SEO audit — fetches page HTML and inspects key signals.
"""

import logging
from datetime import datetime

from app.extensions import db
from app.models.site    import Site
from app.models.seo_log import SEOLog
from app.services.monitoring_service import CHECK_SEO, schedule_next_run
from app.utils.http     import fetch_url
from app.utils.parser   import parse_seo_tags

logger = logging.getLogger(__name__)


def run_seo_check(site_id: int) -> SEOLog | None:
    """
    Fetch the site's homepage and run a basic SEO audit.

    Checks:
      - Page title presence
      - Meta description presence
      - H1 tag presence (and text)

    Returns the saved SEOLog or None if site not found.
    """
    site: Site | None = db.session.get(Site, site_id)
    if site is None:
        logger.warning("run_seo_check: Site %s not found.", site_id)
        return None

    logger.info("Running SEO check for %s", site.url)
    checked_at = datetime.utcnow()
    result = fetch_url(site.url)

    if result["error"] or not result["content"]:
        log = SEOLog(
            site_id=site.id,
            error_message=result["error"] or "Empty response body",
            checked_at=checked_at,
        )
        site.seo_status = "ERROR"
        site.seo_last_error = result["error"] or "Empty response body"
        site.seo_title = None
        site.seo_meta_description = None
        site.seo_has_meta = False
        site.seo_has_h1 = False
        site.seo_h1_text = None
        site.seo_score = 0
    else:
        seo = parse_seo_tags(result["content"])
        log = SEOLog(
            site_id=site.id,
            title=seo["title"],
            meta_description=seo["meta_description"],
            has_meta=seo["has_meta"],
            has_h1=seo["has_h1"],
            h1_text=seo["h1_text"],
            checked_at=checked_at,
        )
        site.seo_title = seo["title"]
        site.seo_meta_description = seo["meta_description"]
        site.seo_has_meta = seo["has_meta"]
        site.seo_has_h1 = seo["has_h1"]
        site.seo_h1_text = seo["h1_text"]
        site.seo_score = _calculate_seo_score(seo)
        site.seo_status = "HEALTHY" if site.seo_score >= 70 else "ISSUES"
        site.seo_last_error = None

    schedule_next_run(site, CHECK_SEO, checked_at)
    db.session.add(log)
    db.session.commit()

    logger.info(
        "SEO check done — %s | title=%s | has_meta=%s | has_h1=%s",
        site.url,
        bool(log.title),
        log.has_meta,
        log.has_h1,
    )
    return log


def _calculate_seo_score(seo: dict) -> int:
    return sum([
        40 if seo["title"] else 0,
        30 if seo["has_meta"] else 0,
        30 if seo["has_h1"] else 0,
    ])


def get_seo_logs(site_id: int, limit: int = 50) -> list[dict]:
    logs = (
        SEOLog.query
        .filter_by(site_id=site_id)
        .order_by(SEOLog.checked_at.desc())
        .limit(limit)
        .all()
    )
    return [log.to_dict() for log in logs]
