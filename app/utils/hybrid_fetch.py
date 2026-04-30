"""
utils/hybrid_fetch.py
----------------------
Hybrid fetch strategy for SEO audits.

Fast path:  httpx (no browser overhead, ~1-3s)
Slow path:  Playwright headless Chromium (JS rendering, ~5-20s)

The browser fallback is triggered automatically when the HTTP response
looks like a bot-protection page, a JS-only shell, or is too small to
score meaningfully.

Public API
----------
    result = fetch_html_for_seo(url)
    result.html          # full HTML string
    result.render_mode   # "HTTP" | "BROWSER" | "HTTP_BROWSER_FAILED"
    result.used_fallback # bool
    result.status_code   # int | None
    result.ttfb          # float | None  (seconds)
    result.response_time # float | None  (seconds)
    result.page_size_kb  # float
    result.https_redirect# bool
    result.headers       # dict
    result.error         # str | None
    result.is_up         # bool
"""

import logging
import time
from dataclasses import dataclass, field

import httpx

from app.config.settings import Config

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

_HTTP_TIMEOUT      = 15.0   # seconds for httpx fetch
_BROWSER_TIMEOUT   = 20_000 # milliseconds for Playwright page load
_MIN_REAL_SIZE_KB  = 2.0    # pages smaller than this are suspicious

# Realistic browser User-Agent — avoids trivial bot detection
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Signatures that indicate the HTTP response is NOT the real page
_BOT_PROTECTION_SIGNATURES = [
    "aes.js",
    "tonumbers(",
    "toNumbers(",
    "challenge-platform",
    "cf-challenge",
    "__cf_chl",
    "jschl_vc",
    "ray id",
    "ddos-guard",
    "please enable javascript",
    "please enable cookies",
    "checking your browser",
    "just a moment",
    "enable javascript and cookies",
]

_PLACEHOLDER_SIGNATURES = [
    "coming soon",
    "account suspended",
    "default web site page",
    "under construction",
    "parked domain",
    "this domain is for sale",
    "website is not configured",
    "welcome to nginx",
    "apache2 default page",
    "it works!",
    "index of /",
]


# ── Result dataclass ───────────────────────────────────────────────────────

@dataclass
class HybridFetchResult:
    html:           str
    render_mode:    str          # "HTTP" | "BROWSER" | "HTTP_BROWSER_FAILED"
    used_fallback:  bool
    status_code:    int | None   = None
    ttfb:           float | None = None
    response_time:  float | None = None
    page_size_kb:   float        = 0.0
    https_redirect: bool         = False
    headers:        dict         = field(default_factory=dict)
    error:          str | None   = None
    is_up:          bool         = True
    fallback_reason: str | None  = None  # why browser was triggered


# ── Public entry point ─────────────────────────────────────────────────────

def fetch_html_for_seo(url: str) -> HybridFetchResult:
    """
    Fetch a page for SEO analysis using the hybrid strategy.

    1. Try httpx (fast, no JS).
    2. If the response looks like a bot-protection shell or is too small,
       fall back to Playwright (full JS rendering).
    3. If Playwright also fails, return the HTTP result with a flag.
    """
    # ── Fast path: HTTP ────────────────────────────────────────────────────
    http_result = _fetch_httpx(url)

    needs_browser, reason = _needs_browser(
        html=http_result.html,
        status_code=http_result.status_code,
        error=http_result.error,
    )

    if not needs_browser:
        logger.debug("[FETCH] %s → HTTP (%.1f KB)", url, http_result.page_size_kb)
        return http_result

    # ── Slow path: Playwright ──────────────────────────────────────────────
    logger.info("[FETCH] %s → browser fallback. Reason: %s", url, reason)
    try:
        browser_html, browser_ttfb = _fetch_playwright(url)
        page_size_kb = len(browser_html.encode("utf-8", errors="replace")) / 1024
        return HybridFetchResult(
            html=browser_html,
            render_mode="BROWSER",
            used_fallback=True,
            status_code=http_result.status_code or 200,
            ttfb=browser_ttfb,
            response_time=browser_ttfb,
            page_size_kb=page_size_kb,
            https_redirect=url.startswith("https://"),
            headers=http_result.headers,   # headers from HTTP phase
            error=None,
            is_up=True,
            fallback_reason=reason,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[FETCH] %s → browser fallback failed: %s", url, exc)
        # Return HTTP result with degraded mode flag
        http_result.render_mode = "HTTP_BROWSER_FAILED"
        http_result.used_fallback = True
        http_result.fallback_reason = reason
        http_result.error = f"Browser fallback failed: {exc}"
        return http_result


# ── HTTP fetch ─────────────────────────────────────────────────────────────

def _fetch_httpx(url: str) -> HybridFetchResult:
    start = time.perf_counter()
    ttfb: float | None = None
    chunks: list[bytes] = []
    bytes_read = 0

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=_HTTP_TIMEOUT,
            verify=Config.HTTP_VERIFY_SSL,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            with client.stream("GET", url) as response:
                for chunk in response.iter_bytes():
                    if ttfb is None:
                        ttfb = time.perf_counter() - start
                    bytes_read += len(chunk)
                    chunks.append(chunk)

        total_time = time.perf_counter() - start
        html = b"".join(chunks).decode("utf-8", errors="replace")
        page_size_kb = len(html.encode("utf-8", errors="replace")) / 1024
        final_url = str(response.url)
        https_redirect = final_url.startswith("https://") and len(response.history) > 0

        return HybridFetchResult(
            html=html,
            render_mode="HTTP",
            used_fallback=False,
            status_code=response.status_code,
            ttfb=ttfb,
            response_time=total_time,
            page_size_kb=page_size_kb,
            https_redirect=https_redirect,
            headers=dict(response.headers),
            error=None,
            is_up=response.status_code < 400,
        )

    except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException,
            httpx.RemoteProtocolError, httpx.NetworkError) as exc:
        return HybridFetchResult(
            html="",
            render_mode="HTTP",
            used_fallback=False,
            status_code=None,
            ttfb=None,
            response_time=None,
            page_size_kb=0.0,
            https_redirect=False,
            headers={},
            error=str(exc),
            is_up=False,
        )
    except Exception as exc:  # noqa: BLE001
        return HybridFetchResult(
            html="",
            render_mode="HTTP",
            used_fallback=False,
            status_code=None,
            ttfb=None,
            response_time=None,
            page_size_kb=0.0,
            https_redirect=False,
            headers={},
            error=str(exc),
            is_up=False,
        )


# ── Browser fetch ──────────────────────────────────────────────────────────

def _fetch_playwright(url: str) -> tuple[str, float]:
    """
    Fetch a page using Playwright headless Chromium.
    Returns (html_content, ttfb_seconds).
    Raises on any failure — caller handles the exception.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    start = time.perf_counter()
    ttfb: float | None = None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
            ],
        )
        try:
            context = browser.new_context(
                user_agent=_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
                ignore_https_errors=True,
            )
            page = context.new_page()

            # Capture TTFB from the first response event
            def on_response(response):
                nonlocal ttfb
                if ttfb is None and response.url == page.url or url in response.url:
                    ttfb = time.perf_counter() - start

            page.on("response", on_response)

            try:
                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=_BROWSER_TIMEOUT,
                )
            except PWTimeout:
                # networkidle timed out — grab whatever rendered so far
                logger.warning("[BROWSER] networkidle timeout for %s, using partial content", url)

            html = page.content()
            if ttfb is None:
                ttfb = time.perf_counter() - start

            return html, ttfb
        finally:
            browser.close()


# ── Detection logic ────────────────────────────────────────────────────────

def _needs_browser(html: str, status_code: int | None, error: str | None) -> tuple[bool, str]:
    """
    Decide whether the HTTP response requires a browser fallback.
    Returns (needs_browser: bool, reason: str).
    """
    # Network error with no HTML
    if error and not html:
        return True, f"HTTP fetch failed: {error}"

    # Empty or whitespace response
    if not html or not html.strip():
        return True, "Empty response body"

    html_lower = html.lower()
    page_size_kb = len(html.encode("utf-8", errors="replace")) / 1024

    # HTTP error status
    if status_code is not None and status_code >= 400:
        return True, f"HTTP {status_code} error response"

    # Page too small — likely a JS shell or redirect stub
    if page_size_kb < _MIN_REAL_SIZE_KB:
        return True, f"Page too small ({page_size_kb:.1f} KB) — likely a JS shell"

    # Bot protection / challenge page signatures
    for sig in _BOT_PROTECTION_SIGNATURES:
        if sig.lower() in html_lower:
            return True, f"Bot protection detected: '{sig}'"

    # Known placeholder content
    for sig in _PLACEHOLDER_SIGNATURES:
        if sig.lower() in html_lower:
            return True, f"Placeholder page detected: '{sig}'"

    return False, ""
