"""
utils/broken_link_checker.py
-----------------------------
Crawls all internal and external links found on a page and checks
each one for HTTP errors (4xx/5xx) or connection failures.

Design constraints:
  - Max 50 links checked per run (configurable) to keep task time bounded
  - Uses HEAD requests first, falls back to GET if HEAD returns 405
  - Concurrent checks via httpx with a thread pool (not async, to stay
    compatible with the existing sync Celery worker)
  - Respects a per-request timeout of 8 seconds
  - Never follows more than 3 redirects
  - Skips mailto:, tel:, javascript:, #fragment-only links
  - Returns structured results grouped by status
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT        = 8.0    # seconds per link check
_MAX_REDIRECTS  = 3
_MAX_LINKS      = 500    # practical upper bound — concurrent so wall-clock stays low
_CONCURRENCY    = 12     # parallel workers
_SKIP_SCHEMES   = {"mailto", "tel", "javascript", "data", "ftp"}


@dataclass
class LinkResult:
    url: str
    status_code: int | None
    is_broken: bool
    error: str | None
    link_type: str          # "internal" | "external"
    anchor_text: str


@dataclass
class BrokenLinkReport:
    total_found: int          # Total links found in HTML (before deduplication)
    total_checked: int        # Total unique links tested
    broken_count: int
    internal_count: int       # Unique internal links
    external_count: int       # Unique external links
    broken: list[LinkResult] = field(default_factory=list)
    ok: list[LinkResult]     = field(default_factory=list)
    skipped: int             = 0
    error_message: str | None = None


def check_broken_links(
    links: list[dict],
    base_url: str,
    max_links: int = _MAX_LINKS,
) -> BrokenLinkReport:
    """
    Check a list of link dicts (from parse_seo_intelligence) for broken URLs.
    """
    if not links:
        return BrokenLinkReport(total_found=0, total_checked=0, broken_count=0, internal_count=0, external_count=0)

    total_found = len(links)
    
    # Resolve and deduplicate
    resolved: list[tuple[str, str, str]] = []  # (absolute_url, type, anchor_text)
    seen: set[str] = set()

    internal_unique = 0
    external_unique = 0

    for link in links:
        href = (link.get("url") or "").strip()
        if not href:
            continue

        # Skip non-HTTP schemes
        parsed = urlparse(href)
        if parsed.scheme in _SKIP_SCHEMES:
            continue
        if href.startswith("#"):
            continue

        # Resolve and Normalize relative URLs
        absolute = urljoin(base_url, href)
        
        # Strip trailing slash for stricter deduplication
        norm_url = absolute.rstrip('/')
        
        if norm_url in seen:
            continue
        seen.add(norm_url)
        
        l_type = link.get("type", "external")
        resolved.append((absolute, l_type, link.get("text", "")))

    # Only count what we are actually going to check
    skipped = max(0, len(resolved) - max_links)
    to_check = resolved[:max_links]
    
    # Final Math Lock: Count based on the actual list being checked
    for _, l_type, _ in to_check:
        if l_type == "internal":
            internal_unique += 1
        else:
            external_unique += 1

    results: list[LinkResult] = []
    with ThreadPoolExecutor(max_workers=_CONCURRENCY) as pool:
        futures = {
            pool.submit(_check_single_link, url, link_type, anchor): (url, link_type, anchor)
            for url, link_type, anchor in to_check
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                url, link_type, anchor = futures[future]
                results.append(LinkResult(
                    url=url,
                    status_code=None,
                    is_broken=True,
                    error=str(exc),
                    link_type=link_type,
                    anchor_text=anchor,
                ))

    broken = [r for r in results if r.is_broken]
    ok     = [r for r in results if not r.is_broken]

    return BrokenLinkReport(
        total_found=total_found,
        total_checked=len(results),
        broken_count=len(broken),
        internal_count=internal_unique,
        external_count=external_unique,
        broken=sorted(broken, key=lambda r: r.url),
        ok=sorted(ok, key=lambda r: r.url),
        skipped=skipped,
    )


def _check_single_link(url: str, link_type: str, anchor_text: str) -> LinkResult:
    """Check one URL. Uses HEAD, falls back to GET on 405."""
    try:
        with httpx.Client(
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
            timeout=_TIMEOUT,
            verify=False,  # noqa: S501 — we're checking external links, not verifying their certs
            headers={"User-Agent": "WebMonitor-LinkChecker/1.0"},
        ) as client:
            try:
                resp = client.head(url)
                if resp.status_code == 405:
                    resp = client.get(url)
            except httpx.HTTPStatusError as exc:
                resp = exc.response

        is_broken = resp.status_code >= 400
        return LinkResult(
            url=url,
            status_code=resp.status_code,
            is_broken=is_broken,
            error=f"HTTP {resp.status_code}" if is_broken else None,
            link_type=link_type,
            anchor_text=anchor_text[:120],
        )

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return LinkResult(
            url=url,
            status_code=None,
            is_broken=True,
            error=str(exc)[:200],
            link_type=link_type,
            anchor_text=anchor_text[:120],
        )
    except Exception as exc:  # noqa: BLE001
        return LinkResult(
            url=url,
            status_code=None,
            is_broken=True,
            error=str(exc)[:200],
            link_type=link_type,
            anchor_text=anchor_text[:120],
        )


def extract_all_links(html: str, base_url: str) -> list[dict]:
    """
    Extract all <a href> links from HTML with type classification.
    Designed to be called from parser.py or seo_service.py.

    Returns list of {"url": str, "text": str, "type": "internal"|"external"}
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return []

    base_domain = urlparse(base_url).netloc
    links = []

    for tag in soup.find_all("a", href=True):
        href = (tag.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue

        absolute = urljoin(base_url, href)
        parsed   = urlparse(absolute)

        if parsed.scheme not in ("http", "https"):
            continue

        link_type = "internal" if parsed.netloc == base_domain else "external"
        links.append({
            "url":  absolute,
            "text": tag.get_text(strip=True)[:120],
            "type": link_type,
        })

    return links


def broken_link_report_to_dict(report: BrokenLinkReport) -> dict:
    return {
        "total_found":   report.total_found,
        "total_checked": report.total_checked,
        "broken_count":  report.broken_count,
        "internal_count": report.internal_count,
        "external_count": report.external_count,
        "skipped":       report.skipped,
        "error_message": report.error_message,
        "broken": [
            {
                "url":         r.url,
                "status_code": r.status_code,
                "error":       r.error,
                "link_type":   r.link_type,
                "anchor_text": r.anchor_text,
            }
            for r in report.broken
        ],
    }
