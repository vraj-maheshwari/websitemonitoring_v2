"""
seo_validator.py

Validates whether a fetched HTML response is real page content
vs a host placeholder, error page, or empty response.

If validation fails, the SEO check is marked fetch_valid=False
and NO score is generated. This prevents false POOR reports.

Design rules
------------
- Domain-name strings (great-site.net, 000webhost, etc.) are NOT checked
  on large pages — they appear in real site content (links, canonical URLs).
  They are only checked on small pages (< MIN_VALID_PAGE_SIZE_KB) where
  the entire page IS the splash screen.
- Phrase-based signatures (e.g. "Account suspended") are checked on all
  pages because they are unambiguous error messages, not incidental text.
"""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("seo.validator")

MIN_VALID_PAGE_SIZE_KB = 5.0

# Checked on ALL page sizes — unambiguous error/placeholder phrases
PHRASE_SIGNATURES = [
    "This site is temporarily unavailable",
    "Account suspended",
    "Parked Domain",
    "This domain is for sale",
    "Website is not configured",
    "Welcome to nginx",
    "Apache2 Default Page",
    "403 Forbidden",
    "503 Service Unavailable",
]

# Checked ONLY on small pages (< MIN_VALID_PAGE_SIZE_KB)
# These are free-hosting domain strings that appear in real site HTML too
SMALL_PAGE_ONLY_SIGNATURES = [
    "infinityfree",
    "great-site.net",
    "000webhost",
    "byethost",
    "under construction",
    "Coming Soon",
    "Web Hosting",
    "Free Website",
    "It works!",
    "Index of /",
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
        fetch_status = (
            "timeout"
            if error and ("timeout" in error.lower() or "timed out" in error.lower())
            else "error"
        )
        return _invalid(fetch_status, f"Fetch failed with error: {error}", html_preview, site_url, page_size_kb, status_code)

    # Rule 2: Empty response
    if not html_content or not html_content.strip():
        return _invalid("empty", "Fetched HTML content is empty. Server returned no body.", "", site_url, page_size_kb, status_code)

    html_lower = html_content.lower()

    # Rule 3: Page too small — check both signature lists
    if page_size_kb < MIN_VALID_PAGE_SIZE_KB:
        matched = _match_any(html_lower, PHRASE_SIGNATURES + SMALL_PAGE_ONLY_SIGNATURES)
        reason = (
            f"Page size is only {page_size_kb:.2f} KB (minimum: {MIN_VALID_PAGE_SIZE_KB} KB). "
            "Real pages are typically 10–200 KB."
        )
        if matched:
            reason += f" Detected placeholder signature: '{matched}'."
        reason += " Likely a host splash page, cold-start error, or server not ready."
        return _invalid("invalid_content", reason, html_preview, site_url, page_size_kb, status_code)

    # Rule 4: HTTP error status
    if status_code and status_code >= 400:
        return _invalid(
            "error",
            f"Server returned HTTP {status_code}. Content is an error page, not the real site.",
            html_preview, site_url, page_size_kb, status_code,
        )

    # Rule 5: Unambiguous placeholder phrases on any size page
    matched = _match_any(html_lower, PHRASE_SIGNATURES)
    if matched:
        return _invalid(
            "invalid_content",
            f"Detected placeholder signature: '{matched}'. This is not the real site content.",
            html_preview, site_url, page_size_kb, status_code,
        )

    # All checks passed
    logger.info(
        "SEO fetch valid",
        extra={"site_url": site_url, "page_size_kb": page_size_kb, "status_code": status_code},
    )
    return ValidationResult(is_valid=True, fetch_status="ok", reason=None, html_preview=html_preview)


# ── Helpers ────────────────────────────────────────────────────────────────

def _match_any(html_lower: str, signatures: list[str]) -> Optional[str]:
    for sig in signatures:
        if sig.lower() in html_lower:
            return sig
    return None


def _invalid(
    fetch_status: str,
    reason: str,
    html_preview: str,
    site_url: str,
    page_size_kb: float,
    status_code: Optional[int],
) -> ValidationResult:
    result = ValidationResult(
        is_valid=False,
        fetch_status=fetch_status,
        reason=reason,
        html_preview=html_preview,
    )
    logger.warning(
        "SEO fetch invalid",
        extra={
            "site_url": site_url,
            "fetch_status": fetch_status,
            "page_size_kb": page_size_kb,
            "status_code": status_code,
            "reason": reason,
            "html_preview_length": len(html_preview),
        },
    )
    return result
