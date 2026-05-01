"""
utils/lighthouse_runner.py
--------------------------
Collects real Core Web Vitals from a browser session using Playwright.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import math
from typing import Any

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    class PlaywrightTimeout(Exception):
        """Fallback timeout type used when Playwright is not installed."""

    def sync_playwright():
        """Raise a clear error when Playwright is unavailable."""
        raise ModuleNotFoundError("No module named 'playwright'")

logger = logging.getLogger(__name__)

CWV_THRESHOLDS: dict[str, dict[str, float]] = {
    "lcp": {"good": 2500.0, "needs_improvement": 4000.0},
    "tbt": {"good": 200.0, "needs_improvement": 600.0},
    "cls": {"good": 0.10, "needs_improvement": 0.25},
    "fcp": {"good": 1800.0, "needs_improvement": 3000.0},
    "ttfb": {"good": 800.0, "needs_improvement": 1800.0},
}

PERFORMANCE_WEIGHTS: dict[str, float] = {
    "lcp": 0.25,
    "tbt": 0.30,
    "cls": 0.15,
    "fcp": 0.10,
    "ttfb": 0.20,
}

BROWSER_LAUNCH_ARGS: list[str] = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-default-apps",
    "--mute-audio",
]

METRICS_COLLECTION_WAIT_MS = 3000
DEFAULT_VIEWPORT = {"width": 1350, "height": 940}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_METRICS_JS = """
() => new Promise((resolve) => {
  const result = { lcp: null, fcp: null, cls: 0, longTaskMs: 0,
                   longTaskCount: 0, ttfb: null, domInteractive: null,
                   loadEventEnd: null };

  // NavigationTiming
  const nav = performance.getEntriesByType('navigation')[0];
  if (nav) {
    result.ttfb = nav.responseStart;
    result.domInteractive = nav.domInteractive;
    result.loadEventEnd = nav.loadEventEnd;
  }

  // Buffered paint entries
  performance.getEntriesByType('paint').forEach(e => {
    if (e.name === 'first-contentful-paint') result.fcp = e.startTime;
  });

  // Buffered layout shift (CLS) - exclude hadRecentInput
  performance.getEntriesByType('layout-shift').forEach(e => {
    if (!e.hadRecentInput) result.cls += e.value;
  });

  // Buffered long tasks (TBT = sum of durations over 50ms)
  performance.getEntriesByType('longtask').forEach(e => {
    result.longTaskMs += Math.max(0, e.duration - 50);
    result.longTaskCount += 1;
  });

  // LCP via observer with buffered:true
  try {
    const lcpObs = new PerformanceObserver(list => {
      const entries = list.getEntries();
      if (entries.length > 0) {
        result.lcp = entries[entries.length - 1].startTime;
      }
    });
    lcpObs.observe({ type: 'largest-contentful-paint', buffered: true });
    setTimeout(() => { try { lcpObs.disconnect(); } catch(e) {} }, 2800);
  } catch(e) { /* browser does not support LCP observer */ }

  // Resolve after full wait
  setTimeout(() => resolve(result), 3000);
})
"""


def compute_cwv_rating(metric: str, value: float | None) -> str:
    """Return the Core Web Vitals rating for a metric value."""
    if value is None:
        return "unknown"

    thresholds = CWV_THRESHOLDS.get(metric)
    if thresholds is None:
        return "unknown"

    if value <= thresholds["good"]:
        return "good"
    if value <= thresholds["needs_improvement"]:
        return "needs_improvement"
    return "poor"


@dataclass
class LighthouseResult:
    """Real browser performance audit result."""

    url: str
    audit_method: str = "playwright_perf"

    lcp_ms: float | None = None
    fcp_ms: float | None = None
    tbt_ms: float | None = None
    cls: float | None = None
    ttfb_ms: float | None = None
    tti_ms: float | None = None
    si_ms: float | None = None
    page_load_ms: float | None = None

    lcp_rating: str = "unknown"
    fcp_rating: str = "unknown"
    tbt_rating: str = "unknown"
    cls_rating: str = "unknown"
    ttfb_rating: str = "unknown"

    performance_score: int | None = None
    audited_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None

    def compute_ratings(self) -> None:
        """Compute stored ratings for all Core Web Vitals metrics."""
        self.lcp_rating = compute_cwv_rating("lcp", self.lcp_ms)
        self.fcp_rating = compute_cwv_rating("fcp", self.fcp_ms)
        self.tbt_rating = compute_cwv_rating("tbt", self.tbt_ms)
        self.cls_rating = compute_cwv_rating("cls", self.cls)
        self.ttfb_rating = compute_cwv_rating("ttfb", self.ttfb_ms)

    def compute_performance_score(self) -> None:
        """Compute the weighted Lighthouse-style performance score."""
        rating_to_points = {"good": 100, "needs_improvement": 50, "poor": 0}
        rating_map = {
            "lcp": self.lcp_rating,
            "tbt": self.tbt_rating,
            "cls": self.cls_rating,
            "fcp": self.fcp_rating,
            "ttfb": self.ttfb_rating,
        }
        weighted_score = 0.0
        total_weight = 0.0

        for metric, weight in PERFORMANCE_WEIGHTS.items():
            points = rating_to_points.get(rating_map[metric])
            if points is not None:
                weighted_score += points * weight
                total_weight += weight

        self.performance_score = round(weighted_score / total_weight) if total_weight > 0 else None

    def to_api_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable API representation."""
        return {
            "performance_score": self.performance_score,
            "audit_method": self.audit_method,
            "audited_at": self.audited_at.isoformat() if self.audited_at else None,
            "error": self.error,
            "metrics": {
                "lcp": {"value_ms": self.lcp_ms, "rating": self.lcp_rating},
                "fcp": {"value_ms": self.fcp_ms, "rating": self.fcp_rating},
                "tbt": {"value_ms": self.tbt_ms, "rating": self.tbt_rating},
                "cls": {"value": self.cls, "rating": self.cls_rating},
                "ttfb": {"value_ms": self.ttfb_ms, "rating": self.ttfb_rating},
                "tti": {"value_ms": self.tti_ms, "rating": "n/a"},
                "si": {"value_ms": self.si_ms, "rating": "n/a"},
            },
            "page_load_ms": self.page_load_ms,
        }


def _safe_round(value: object, decimals: int = 1) -> float | None:
    """Safely convert a value to a rounded finite float."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, decimals)


def run_lighthouse_audit(
    url: str,
    timeout_ms: int = 30_000,
    wait_until: str = "networkidle",
) -> LighthouseResult:
    """
    Collect real Core Web Vitals via Playwright browser APIs.

    Args:
        url: Absolute URL to audit. It must include the scheme.
        timeout_ms: Navigation timeout in milliseconds.
        wait_until: Playwright navigation state, such as "load",
            "domcontentloaded", "networkidle", or "commit".

    Returns:
        A LighthouseResult in all cases; this function never raises.

    On error:
        Metric fields are left as None and the error field contains the
        exception type and message.
    """
    result = LighthouseResult(url=url)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=BROWSER_LAUNCH_ARGS,
            )
            context = browser.new_context(
                viewport=DEFAULT_VIEWPORT,
                user_agent=DEFAULT_USER_AGENT,
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            except PlaywrightTimeout:
                logger.warning("CWV audit navigation timeout url=%s", url)

            try:
                raw: dict[str, Any] = page.evaluate(_METRICS_JS)
            finally:
                try:
                    context.close()
                finally:
                    browser.close()

        result.ttfb_ms = _safe_round(raw.get("ttfb"))
        result.fcp_ms = _safe_round(raw.get("fcp"))
        result.lcp_ms = _safe_round(raw.get("lcp"))
        cls_value = _safe_round(raw.get("cls"), decimals=4)
        result.cls = cls_value if cls_value is not None else 0.0
        result.tbt_ms = _safe_round(raw.get("longTaskMs"))
        result.tti_ms = _safe_round(raw.get("domInteractive"))
        result.page_load_ms = _safe_round(raw.get("loadEventEnd"))

        if result.fcp_ms is not None and result.lcp_ms is not None:
            result.si_ms = round((result.fcp_ms + result.lcp_ms) / 2, 1)

        result.compute_ratings()
        result.compute_performance_score()

        logger.info(
            "CWV audit complete url=%s score=%s lcp=%sms cls=%s",
            url,
            result.performance_score,
            result.lcp_ms,
            result.cls,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
        logger.error("CWV audit failed url=%s error=%s", url, result.error)
        return result
