"""
services/seo_service.py
------------------------
Orchestrates deep SEO audits with fetch validation and recovery cooldowns.
"""

from datetime import datetime, timedelta, timezone
import logging
import os
from urllib.parse import urljoin

import httpx

from app.extensions import db
from app.models.seo_log import SEOLog
from app.models.site import Site
from app.services import alert_service
from app.services.monitoring_service import CHECK_SEO, schedule_next_run
from app.utils.http import fetch_url
from app.utils.hybrid_fetch import fetch_html_for_seo
from app.utils.parser import parse_seo_intelligence
from app.utils.seo_engine import analyze_seo
from app.utils.seo_validator import validate_seo_fetch
from app.utils.time import now_utc
from app.utils.tech_profiler import detect_technologies, diff_tech_stacks
from app.utils.cwv_estimator import estimate_cwv, cwv_to_dict
from app.utils.broken_link_checker import extract_all_links, check_broken_links, broken_link_report_to_dict
from app.utils.lighthouse_runner import run_lighthouse_audit
from app.services.security_service import run_security_audit

logger = logging.getLogger(__name__)

SEO_COOLDOWN_AFTER_RECOVERY_SECONDS = 120
LIGHTHOUSE_ENABLED: bool = (
    os.environ.get("LIGHTHOUSE_ENABLED", "true").strip().lower() == "true"
)


def should_skip_seo_for_cooldown(site) -> tuple[bool, str]:
    if site.last_downtime_ended_at is None:
        return False, ""

    now = datetime.now(timezone.utc)
    last_recovery = site.last_downtime_ended_at
    if last_recovery.tzinfo is None:
        last_recovery = last_recovery.replace(tzinfo=timezone.utc)

    elapsed = (now - last_recovery).total_seconds()
    if elapsed < SEO_COOLDOWN_AFTER_RECOVERY_SECONDS:
        remaining = SEO_COOLDOWN_AFTER_RECOVERY_SECONDS - elapsed
        return True, (
            f"Site recovered from DOWN state {elapsed:.0f}s ago. "
            f"SEO check is on cooldown for {remaining:.0f}s more to allow server warm-up. "
            f"This prevents false scores from cold-start placeholder pages."
        )

    return False, ""


def run_seo_check(site_or_id, db_session=None) -> dict | None:
    """
    Run a complete SEO analysis.

    Accepts either a Site instance or site id for compatibility with existing
    Celery callers. Invalid fetches are logged but never scored.
    """
    db_session = db_session or db.session
    site = site_or_id if isinstance(site_or_id, Site) else db_session.get(Site, site_or_id)
    if site is None:
        return None

    result = {
        "score": None,
        "status": "UNKNOWN",
        "fetch_valid": False,
        "fetch_status": "error",
        "invalidation_reason": None,
        "fetch_html_preview": "",
        "fetch_page_size_kb": 0.0,
        "score_breakdown": {},
        "issues": [],
        "recommendations": [],
        "signals": {},
        "error_message": None,
    }
    checked_at = now_utc()

    should_skip, skip_reason = should_skip_seo_for_cooldown(site)
    if should_skip:
        logger.info("[SEO] site_id=%s skipping due to cooldown: %s", site.id, skip_reason)
        result["status"] = "INVALID"
        result["fetch_status"] = "invalid_content"
        result["invalidation_reason"] = skip_reason
        _save_seo_log(site, result, db_session, checked_at)
        site.last_seo_fetch_valid = False
        db_session.commit()
        return result

    try:
        fetch_result = fetch_html_for_seo(site.url)
    except Exception as exc:  # noqa: BLE001
        result["error_message"] = str(exc)
        result["fetch_status"] = "error"
        _save_seo_log(site, result, db_session, checked_at)
        site.last_seo_fetch_valid = False
        site.seo_last_error = str(exc)
        db_session.commit()
        logger.exception("[SEO] site_id=%s fetch exception", site.id)
        return result

    html_content = fetch_result.html or ""
    page_size_kb = fetch_result.page_size_kb

    # Store render mode in result for persistence
    result["render_mode"]    = fetch_result.render_mode
    result["used_fallback"]  = fetch_result.used_fallback
    result["fallback_reason"] = fetch_result.fallback_reason

    if fetch_result.render_mode == "BROWSER":
        logger.info(
            "[SEO] site_id=%s used browser rendering. Reason: %s",
            site.id, fetch_result.fallback_reason,
        )

    # Build a fetch_result-compatible dict for downstream code
    fetch_dict = {
        "html_content":       html_content,
        "content":            html_content,
        "page_size_kb":       page_size_kb,
        "status_code":        fetch_result.status_code,
        "ttfb":               fetch_result.ttfb,
        "total_response_time": fetch_result.response_time,
        "response_time":      fetch_result.response_time,
        "https_redirect":     fetch_result.https_redirect,
        "headers":            fetch_result.headers,
        "is_up":              fetch_result.is_up,
        "error":              fetch_result.error,
    }

    validation = validate_seo_fetch(
        html_content=html_content,
        page_size_kb=page_size_kb,
        status_code=fetch_dict.get("status_code"),
        error=fetch_dict.get("error"),
        site_url=site.url,
    )
    result["fetch_valid"] = validation.is_valid
    result["fetch_status"] = validation.fetch_status
    result["invalidation_reason"] = validation.reason
    result["fetch_html_preview"] = validation.html_preview
    result["fetch_page_size_kb"] = page_size_kb

    if not validation.is_valid:
        result["status"] = "INVALID"
        logger.warning(
            "[SEO] site_id=%s fetch invalid status=%s reason=%s",
            site.id,
            validation.fetch_status,
            validation.reason,
        )
        _save_seo_log(site, result, db_session, checked_at)
        site.last_seo_fetch_valid = False
        site.seo_last_error = validation.reason
        schedule_next_run(site, CHECK_SEO, checked_at)
        db_session.commit()
        return result

    try:
        signals = parse_seo_intelligence(html_content, site.url)
        signals["has_robots"] = _check_resource_exists(site.url, "/robots.txt", timeout=8.0)
        signals["has_sitemap"] = _check_resource_exists(site.url, "/sitemap.xml", timeout=8.0)
        signals["has_robots_txt"] = signals["has_robots"]
        signals["has_sitemap_xml"] = signals["has_sitemap"]
        signals["ttfb"] = fetch_dict.get("ttfb")
        signals["total_response_time"] = fetch_dict.get("total_response_time") or fetch_dict.get("response_time")
        signals["page_size_kb"] = page_size_kb
        signals["https_redirect"] = fetch_dict.get("https_redirect", False)
    except Exception as exc:  # noqa: BLE001
        result["error_message"] = f"Parser error: {exc}"
        _save_seo_log(site, result, db_session, checked_at)
        site.last_seo_fetch_valid = False
        site.seo_last_error = result["error_message"]
        db_session.commit()
        logger.exception("[SEO] site_id=%s parser exception", site.id)
        return result

    try:
        analysis = analyze_seo(signals)
        result.update(
            {
                "score": analysis["score"],
                "status": analysis["status"],
                "score_breakdown": analysis.get("breakdown", {}),
                "issues": analysis.get("issues", []),
                "recommendations": analysis.get("recommendations", []),
                "signals": signals,
                "fetch_valid": True,
                "fetch_status": "ok",
                "invalidation_reason": None,
            }
        )
    except Exception as exc:  # noqa: BLE001
        result["error_message"] = f"Scorer error: {exc}"
        _save_seo_log(site, result, db_session, checked_at)
        site.last_seo_fetch_valid = False
        site.seo_last_error = result["error_message"]
        db_session.commit()
        logger.exception("[SEO] site_id=%s scorer exception", site.id)
        return result

    # ── Core Web Vitals estimates ──────────────────────────────────────────
    try:
        cwv = estimate_cwv(signals, ttfb=signals.get("ttfb"))
        result["cwv"] = cwv_to_dict(cwv)
    except Exception:  # noqa: BLE001
        result["cwv"] = {}
        logger.exception("[SEO] site_id=%s CWV estimation failed", site.id)

    # ── Technology profiler ────────────────────────────────────────────────
    try:
        response_headers = fetch_dict.get("headers") or {}
        tech = detect_technologies(html_content, response_headers)
        result["tech_stack"] = tech

        # Diff against previous scan's tech stack
        previous_seo = (
            db_session.query(SEOLog)
            .filter(SEOLog.site_id == site.id, SEOLog.fetch_valid.is_(True))
            .order_by(SEOLog.checked_at.desc())
            .first()
        )
        prev_flat = (previous_seo.tech_flat or []) if previous_seo else []
        result["tech_diff"] = diff_tech_stacks(prev_flat, tech["flat"])
        if result["tech_diff"]["added"]:
            logger.info(
                "[TECH] site_id=%s new technologies detected: %s",
                site.id, result["tech_diff"]["added"],
            )
        if result["tech_diff"]["removed"]:
            logger.info(
                "[TECH] site_id=%s technologies no longer detected: %s",
                site.id, result["tech_diff"]["removed"],
            )
    except Exception:  # noqa: BLE001
        result["tech_stack"] = {}
        result["tech_diff"] = {}
        logger.exception("[SEO] site_id=%s tech profiler failed", site.id)

    # ── Broken link checker ────────────────────────────────────────────────
    try:
        all_links = extract_all_links(html_content, site.url)
        link_report = check_broken_links(all_links, site.url)
        result["broken_links"] = broken_link_report_to_dict(link_report)
        result["broken_link_count"] = link_report.broken_count
        result["links_checked"] = link_report.total_checked
        if link_report.broken_count > 0:
            logger.warning(
                "[LINKS] site_id=%s found %d broken link(s) out of %d checked",
                site.id, link_report.broken_count, link_report.total_checked,
            )
    except Exception:  # noqa: BLE001
        result["broken_links"] = {}
        result["broken_link_count"] = 0
        result["links_checked"] = 0
        logger.exception("[SEO] site_id=%s broken link checker failed", site.id)

    # ── Security audit ─────────────────────────────────────────────────────
    try:
        response_headers_for_security = fetch_dict.get("headers") or {}
        sec = run_security_audit(
            html=html_content,
            response_headers=response_headers_for_security,
            url=site.url  # NEW — needed for CORS checks
        )
        result["security_score"]   = sec["score"]
        result["security_grade"]   = sec["grade"]
        result["security_headers"] = sec["security_headers"]
        result["security_issues"]  = sec["security_issues"]
        result["malware_flags"]    = sec["malware_flags"]
        result["security_categories"] = sec["categories"]
        result["cors_issues"]      = sec["categories"]["cors"]["issues"]
        result["csp_issues"]       = sec["categories"]["csp"]["issues"]
        result["mixed_content_detail"] = sec["categories"]["mixed_content"]["details"]
        if sec["malware_flags"]:
            logger.warning("[SECURITY] site_id=%s malware flags: %s", site.id, sec["malware_flags"])
    except Exception:  # noqa: BLE001
        result["security_score"]   = None
        result["security_grade"]   = None
        result["security_headers"] = {}
        result["security_issues"]  = []
        result["malware_flags"]    = []
        result["security_categories"] = {}
        result["cors_issues"]      = []
        result["csp_issues"]       = []
        result["mixed_content_detail"] = {}
        logger.exception("[SEO] site_id=%s security audit failed", site.id)

    # Capture the old score BEFORE updating site.seo_score so the regression
    # comparison is always old-vs-new, never new-vs-new.
    old_score = site.seo_score if site.seo_score else None

    seo_log = _save_seo_log(site, result, db_session, checked_at)

    site.seo_score = result["score"] or 0
    site.seo_state = result["status"]
    site.seo_status = "done"
    site.seo_last_error = None
    site.last_seo_fetch_valid = True
    schedule_next_run(site, CHECK_SEO, checked_at)

    new_score = result["score"]
    if old_score is not None and new_score is not None and new_score < old_score - 5:
        logger.warning(
            "[SEO] site_id=%s score regression previous=%s current=%s drop=%s",
            site.id,
            old_score,
            new_score,
            old_score - new_score,
        )

    try:
        alert_service.check_seo_alerts(
            site=site,
            score=result["score"],
            status=result["status"],
            checked_at=checked_at,
            old_score=old_score,
        )
    except Exception:  # noqa: BLE001
        logger.exception("[SEO] alert checks failed for site_id=%s", site.id)

    db_session.commit()

    if LIGHTHOUSE_ENABLED and seo_log.fetch_valid:
        lh = run_lighthouse_audit(site.url, timeout_ms=30_000)

        seo_log.lh_lcp_ms = lh.lcp_ms
        seo_log.lh_fcp_ms = lh.fcp_ms
        seo_log.lh_tbt_ms = lh.tbt_ms
        seo_log.lh_cls = lh.cls
        seo_log.lh_ttfb_ms = lh.ttfb_ms
        seo_log.lh_tti_ms = lh.tti_ms
        seo_log.lh_si_ms = lh.si_ms
        seo_log.lh_page_load_ms = lh.page_load_ms
        seo_log.lh_performance_score = lh.performance_score
        seo_log.lh_lcp_rating = lh.lcp_rating
        seo_log.lh_fcp_rating = lh.fcp_rating
        seo_log.lh_tbt_rating = lh.tbt_rating
        seo_log.lh_cls_rating = lh.cls_rating
        seo_log.lh_ttfb_rating = lh.ttfb_rating
        seo_log.lh_audit_method = lh.audit_method
        seo_log.lh_audited_at = lh.audited_at
        seo_log.lh_error = lh.error

        if lh.performance_score is not None:
            site.lh_performance_score = lh.performance_score
            site.lh_lcp_ms = lh.lcp_ms
            site.lh_cls = lh.cls

        db_session.commit()

    return result


def _save_seo_log(site: Site, result: dict, db_session, checked_at=None) -> SEOLog:
    signals = result.get("signals") or {}
    checked_at = checked_at or now_utc()
    log = SEOLog(
        site_id=site.id,
        score=result.get("score"),
        status=result.get("status") or "UNKNOWN",
        title=signals.get("title", ""),
        title_length=signals.get("title_length", 0),
        meta_description=signals.get("meta_description", ""),
        meta_length=signals.get("meta_length", 0),
        h1_list=signals.get("h1_list", []),
        h1_count=signals.get("h1_count", 0),
        h2_count=signals.get("h2_count", 0),
        h3_count=signals.get("h3_count", 0),
        word_count=signals.get("word_count", 0),
        keyword_density=signals.get("keyword_density", []),
        image_count=signals.get("image_count", 0),
        missing_alt_count=signals.get("missing_alt_count", 0),
        internal_link_count=signals.get("internal_link_count", 0),
        external_link_count=signals.get("external_link_count", 0),
        has_robots=signals.get("has_robots", False),
        has_sitemap=signals.get("has_sitemap", False),
        canonical=signals.get("canonical", ""),
        has_favicon=signals.get("has_favicon", False),
        has_hreflang=signals.get("has_hreflang", False),
        robots_meta=signals.get("robots_meta", ""),
        html_lang=signals.get("html_lang", ""),
        page_size_kb=result.get("fetch_page_size_kb") or signals.get("page_size_kb", 0.0) or 0.0,
        js_blocking_count=signals.get("js_blocking_count", 0),
        css_blocking_count=signals.get("css_blocking_count", 0),
        ttfb=signals.get("ttfb"),
        has_viewport=signals.get("has_viewport", False),
        mobile_friendly=signals.get("mobile_friendly", False),
        https_redirect=signals.get("https_redirect", False),
        mixed_content_count=signals.get("mixed_content_count", 0),
        fetch_valid=result.get("fetch_valid", False),
        fetch_status=result.get("fetch_status", "error"),
        fetch_html_preview=result.get("fetch_html_preview"),
        fetch_page_size_kb=result.get("fetch_page_size_kb"),
        invalidation_reason=result.get("invalidation_reason"),
        score_breakdown=result.get("score_breakdown", {}),
        signals=signals,
        issues=result.get("issues", []),
        recommendations=result.get("recommendations", []),
        error_message=result.get("error_message"),
        checked_at=checked_at,
        # Core Web Vitals
        cwv_data=result.get("cwv") or {},
        cwv_lcp_estimate_s=(result.get("cwv") or {}).get("lcp_estimate_s"),
        cwv_lcp_rating=(result.get("cwv") or {}).get("lcp_rating"),
        cwv_fid_estimate_ms=(result.get("cwv") or {}).get("fid_estimate_ms"),
        cwv_fid_rating=(result.get("cwv") or {}).get("fid_rating"),
        cwv_cls_estimate=(result.get("cwv") or {}).get("cls_estimate"),
        cwv_cls_rating=(result.get("cwv") or {}).get("cls_rating"),
        # Technology profiler
        tech_stack=(result.get("tech_stack") or {}).get("detected") or {},
        tech_flat=(result.get("tech_stack") or {}).get("flat") or [],
        tech_diff=result.get("tech_diff") or {},
        # Broken links
        broken_links=result.get("broken_links") or {},
        broken_link_count=result.get("broken_link_count") or 0,
        links_checked=result.get("links_checked") or 0,
        # Security
        security_score=result.get("security_score"),
        security_grade=result.get("security_grade"),
        security_headers=result.get("security_headers") or {},
        security_issues=result.get("security_issues") or [],
        malware_flags=result.get("malware_flags") or [],
        security_categories=result.get("security_categories") or {},
        cors_issues=result.get("cors_issues") or [],
        csp_issues=result.get("csp_issues") or [],
        mixed_content_detail=result.get("mixed_content_detail") or {},
        # Hybrid fetch
        render_mode=result.get("render_mode", "HTTP"),
        used_fallback=result.get("used_fallback", False),
        fallback_reason=result.get("fallback_reason"),
    )
    db_session.add(log)
    db_session.flush()
    return log


def _check_resource_exists(base_url: str, path: str, timeout: float) -> bool:
    try:
        url = urljoin(base_url, path)
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.head(url)
            return response.status_code < 400
    except Exception:  # noqa: BLE001
        return False
