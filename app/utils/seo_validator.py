"""
seo_validator.py

Validates whether a fetched HTML response is real page content
vs a host placeholder, error page, or empty response.

If validation fails, the SEO check is marked fetch_valid=False
and NO score is generated. This prevents false POOR reports.
"""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("seo.validator")

MIN_VALID_PAGE_SIZE_KB = 5.0
MIN_VALID_WORD_COUNT = 30
HOST_PLACEHOLDER_SIGNATURES = [
    "This site is temporarily unavailable",
    "Account suspended",
    "under construction",
    "Coming Soon",
    "Parked Domain",
    "This domain is for sale",
    "Web Hosting",
    "Free Website",
    "infinityfree",
    "great-site.net",
    "000webhost",
    "byethost",
    "Website is not configured",
    "Welcome to nginx",
    "Apache2 Default Page",
    "It works!",
    "Index of /",
    "403 Forbidden",
    "503 Service Unavailable",
]

@dataclass
class ValidationResult:
    is_valid: bool
    fetch_status: str
    reason: Optional[str]
    html_preview: str

def validate_seo_fetch(
    html_content: str,
    page_size_kb: float,
    status_code: Optional[int],
    error: Optional[str],
    site_url: str,
) -> ValidationResult:
    html_preview = html_content[:1000] if html_content else ""
    # Rule 1: Fetch completely failed
    if error and not html_content:
        fetch_status = "timeout" if "timeout" in error.lower() or "timed out" in error.lower() else "error"
        result = ValidationResult(
            is_valid=False,
            fetch_status=fetch_status,
            reason=f"Fetch failed with error: {error}",
            html_preview=html_preview
        )
        logger.warning("SEO fetch invalid", extra={"site_url": site_url, "fetch_status": result.fetch_status, "page_size_kb": page_size_kb, "status_code": status_code, "reason": result.reason, "html_preview_length": len(result.html_preview)})
        return result
    # Rule 2: Empty response
    if not html_content or len(html_content.strip()) == 0:
        result = ValidationResult(
            is_valid=False,
            fetch_status="empty",
            reason="Fetched HTML content is empty (0 bytes). Server may have returned no body.",
            html_preview=""
        )
        logger.warning("SEO fetch invalid", extra={"site_url": site_url, "fetch_status": result.fetch_status, "page_size_kb": page_size_kb, "status_code": status_code, "reason": result.reason, "html_preview_length": len(result.html_preview)})
        return result
    # Rule 3: Page too small
    if page_size_kb < MIN_VALID_PAGE_SIZE_KB:
        html_lower = html_content.lower()
        matched_signature = None
        for sig in HOST_PLACEHOLDER_SIGNATURES:
            if sig.lower() in html_lower:
                matched_signature = sig
                break
        reason = (
            f"Page size is only {page_size_kb:.2f} KB (minimum: {MIN_VALID_PAGE_SIZE_KB} KB). "
            f"Real multi-section pages are typically 10-200 KB. "
        )
        if matched_signature:
            reason += f"Detected host placeholder signature: '{matched_signature}'. "
        reason += "This is likely a host splash page, cold-start error, or server not ready."
        result = ValidationResult(
            is_valid=False,
            fetch_status="invalid_content",
            reason=reason,
            html_preview=html_preview
        )
        logger.warning("SEO fetch invalid", extra={"site_url": site_url, "fetch_status": result.fetch_status, "page_size_kb": page_size_kb, "status_code": status_code, "reason": result.reason, "html_preview_length": len(result.html_preview)})
        return result
    # Rule 4: HTTP error status
    if status_code and status_code >= 400:
        result = ValidationResult(
            is_valid=False,
            fetch_status="error",
            reason=f"Server returned HTTP {status_code}. Content is an error page, not the real site.",
            html_preview=html_preview
        )
        logger.warning("SEO fetch invalid", extra={"site_url": site_url, "fetch_status": result.fetch_status, "page_size_kb": page_size_kb, "status_code": status_code, "reason": result.reason, "html_preview_length": len(result.html_preview)})
        return result
    # Rule 5: Host placeholders in any size page
    html_lower = html_content.lower()
    for sig in HOST_PLACEHOLDER_SIGNATURES:
        if sig.lower() in html_lower:
            result = ValidationResult(
                is_valid=False,
                fetch_status="invalid_content",
                reason=f"Detected known host placeholder signature: '{sig}'. This is not the real site content.",
                html_preview=html_preview
            )
            logger.warning("SEO fetch invalid", extra={"site_url": site_url, "fetch_status": result.fetch_status, "page_size_kb": page_size_kb, "status_code": status_code, "reason": result.reason, "html_preview_length": len(result.html_preview)})
            return result
    # All checks passed
    result = ValidationResult(
        is_valid=True,
        fetch_status="ok",
        reason=None,
        html_preview=html_preview
    )
    logger.info("SEO fetch valid", extra={"site_url": site_url, "page_size_kb": page_size_kb, "status_code": status_code})
    return result
