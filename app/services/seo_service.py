"""
services/seo_service.py
------------------------
Orchestrates deep SEO audits. 
Upgraded for granular status tracking and SaaS intelligence.
"""

import logging
from urllib.parse import urljoin
from app.extensions import db
from app.models.site    import Site
from app.models.seo_log import SEOLog
from app.services import alert_service
from app.services.monitoring_service import CHECK_SEO, schedule_next_run
from app.utils.http     import fetch_url, check_file_exists
from app.utils.parser   import parse_seo_intelligence
from app.utils.seo_engine import analyze_seo
from app.utils.time     import now_utc

logger = logging.getLogger(__name__)

def run_seo_check(site_id: int) -> SEOLog | None:
    site: Site | None = db.session.get(Site, site_id)
    if not site: return None

    checked_at = now_utc()
    try:
        # 1. Fetch
        result = fetch_url(site.url, timeout=20.0, stream_for_ttfb=True)
        if result["error"]:
            return _handle_failure(site, result["error"], checked_at)

        # 2. Parse (Deep Scan)
        signals = parse_seo_intelligence(result["content"], site.url)
        
        # 3. Technical checks (Async-like)
        signals["has_robots"] = check_file_exists(urljoin(site.url, "/robots.txt"))
        signals["has_sitemap"] = check_file_exists(urljoin(site.url, "/sitemap.xml"))
        signals["has_robots_txt"] = signals["has_robots"]
        signals["has_sitemap_xml"] = signals["has_sitemap"]
        signals["ttfb"] = result.get("ttfb")
        signals["total_response_time"] = result.get("response_time")
        signals["https_redirect"] = result.get("https_redirect", False)

        # 4. Analyze
        analysis = analyze_seo(signals, ttfb=result.get("ttfb"), https_redirect=result.get("https_redirect"))
        
        # 5. Persist
        log = SEOLog(
            site_id=site.id,
            score=analysis["score"],
            status=analysis["status"],
            
            # On-Page
            title=signals["title"],
            title_length=signals["title_length"],
            meta_description=signals["meta_description"],
            meta_length=signals["meta_length"],
            h1_list=signals["h1_list"],
            h1_count=signals["h1_count"],
            h2_count=signals["h2_count"],
            h3_count=signals["h3_count"],
            word_count=signals["word_count"],
            keyword_density=signals["keyword_density"],
            
            # Content
            image_count=signals["image_count"],
            missing_alt_count=signals["missing_alt_count"],
            internal_link_count=signals["internal_link_count"],
            external_link_count=signals["external_link_count"],
            
            # Tech
            has_robots=signals["has_robots"],
            has_sitemap=signals["has_sitemap"],
            canonical=signals["canonical"],
            has_favicon=signals["has_favicon"],
            has_hreflang=signals["has_hreflang"],
            robots_meta=signals["robots_meta"],
            html_lang=signals["html_lang"],
            
            # Perf
            page_size_kb=signals["page_size_kb"],
            js_blocking_count=signals["js_blocking_count"],
            css_blocking_count=signals["css_blocking_count"],
            ttfb=result.get("ttfb"),
            
            # Mobile & Security
            has_viewport=signals["has_viewport"],
            mobile_friendly=signals["mobile_friendly"],
            https_redirect=result.get("https_redirect", False),
            mixed_content_count=signals["mixed_content_count"],
            signals=signals,
            
            # Breakdown
            score_breakdown=analysis["breakdown"],
            issues=analysis["issues"],
            recommendations=analysis["recommendations"],
            checked_at=checked_at
        )
        
        site.seo_score = analysis["score"]
        site.seo_state = analysis["status"]
        site.seo_status = "done"
        site.seo_last_error = None
        
        db.session.add(log)
        
        schedule_next_run(site, CHECK_SEO, checked_at)

        alert_service.check_seo_alerts(
            site=site,
            score=log.score,
            status=log.status,
            checked_at=checked_at
        )
        db.session.commit()
        return log

    except Exception as exc:
        logger.exception("SEO Audit crashed for %s", site.url)
        _handle_failure(site, str(exc), checked_at)
        raise


def _handle_failure(site: Site, error: str, checked_at) -> SEOLog:
    log = SEOLog(
        site_id=site.id,
        score=0, status="POOR",
        error_message=error,
        checked_at=checked_at
    )
    site.seo_status = "failed"
    site.seo_last_error = error
    db.session.add(log)
    return log
