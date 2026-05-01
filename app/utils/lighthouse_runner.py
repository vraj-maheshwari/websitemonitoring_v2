"""
utils/lighthouse_runner.py
---------------------------
Real Core Web Vitals measurement using Playwright's PerformanceObserver
and Navigation Timing APIs.

This module collects actual browser-measured performance metrics by
navigating to a URL in headless Chromium and injecting JavaScript that
reads the Performance API. Results are returned as a typed LighthouseResult
dataclass and are never raised as exceptions — all errors are captured in
the result.error field.

The existing cwv_estimator.py proxy estimates remain as a fallback when
LIGHTHOUSE_ENABLED=false or when Playwright fails.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

# ── Google CWV thresholds (official 2024) ─────────────────────────────────
# Values are the UPPER BOUND of each tier.
# Anything above "needs_improvement" is automatically "poor".
CWV_THRESHOLDS: dict[str, dict[str, float]] = {
    "lcp":  {"good": 2500.0,  "needs_improvement": 4000.0},
    "tbt":  {"good": 200.0,   "needs_improvement": 600.0},
    "cls":  {"good": 0.10,    "needs_improvement": 0.25},
    "fcp":  {"good": 1800.0,  "needs_improvement": 3000.0},
    "ttfb": {"good": 800.0,   "needs_improvement": 1800.0},
}

# ── Lighthouse-style performance weights (must sum to 1.0) ────────────────
PERFORMANCE_WEIGHTS: dict[str, float] = {
    "lcp":  0.25,
    "tbt":  0.30,
    "cls":  0.15,
    "fcp":  0.10,
    "ttfb": 0.20,
}

assert abs(sum(PERFORMANCE_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# ── Browser configuration ─────────────────────────────────────────────────
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

METRICS_COLLECTION_WAIT_MS: int = 3000

DEFAULT_VIEWPORT: dict[str, int] = {"width": 1350, "height": 940}

DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ── JavaScript injected into the page to collect metrics ─────────────────
_METRICS_JS: str = """
() => new Promise((resolve) => {
  const result = {
    lcp: null, fcp: null, cls: 0, longTaskMs: 0,
    longTaskCount: 0, ttfb: null, domInteractive: null,
    loadEventEnd: null
  };

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

  // Buffered layout shift (CLS) — exclude hadRecentInput per spec
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


# ── Helper functions ──────────────────────────────────────────────────────

def _safe_round(value: object, decimals: int = 1) -> float | None:
    """
    Safely convert a value to float and round it.

    Returns None if value is None or cannot be converted.
    Never raises — JavaScript numbers can be NaN, Infinity, or undefined.
    """
    if value is None:
        return None
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


def compute_cwv_rating(metric: str, value: float | None) -> str:
    """
    Return the Google CWV rating for a metric value.

    Args:
        metric: One of "lcp", "tbt", "cls", "fcp", "ttfb".
        value:  The measured value (ms for timing metrics, unitless for CLS).

    Returns:
        "good", "needs_improvement", "poor", or "unknown" if value is None
        or metric is not recognised.
    """
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


# ── Result dataclass ──────────────────────────────────────────────────────

@dataclass
class LighthouseResult:
    """
    Typed result from a Playwright-based Core Web Vitals audit.

    All metric fields are nullable — a failed audit returns an instance
    with all metrics as None and the error field populated.
    """

    url: str
    audit_method: str = "playwright_perf"

    # Raw metric values
    lcp_ms:       float | None = None
    fcp_ms:       float | None = None
    tbt_ms:       float | None = None
    cls:          float | None = None
    ttfb_ms:      float | None = None
    tti_ms:       float | None = None
    si_ms:        float | None = None
    page_load_ms: float | None = None

    # Ratings (set by compute_ratings())
    lcp_rating:  str = "unknown"
    fcp_rating:  str = "unknown"
    tbt_rating:  str = "unknown"
    cls_rating:  str = "unknown"
    ttfb_rating: str = "unknown"

    # Score and metadata
    performance_score: int | None = None
    audited_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    error: str | None = None

    def compute_ratings(self) -> None:
        """Compute and store CWV ratings for all measured metrics."""
        self.lcp_rating  = compute_cwv_rating("lcp",  self.lcp_ms)
        self.fcp_rating  = compute_cwv_rating("fcp",  self.fcp_ms)
        self.tbt_rating  = compute_cwv_rating("tbt",  self.tbt_ms)
        self.cls_rating  = compute_cwv_rating("cls",  self.cls)
        self.ttfb_rating = compute_cwv_rating("ttfb", self.ttfb_ms)

    def compute_performance_score(self) -> None:
        """
        Compute a weighted performance score (0–100) from CWV ratings.

        Uses the same metric weights as Lighthouse. Metrics with "unknown"
        rating are excluded from the weighted average. If all metrics are
        unknown, performance_score is set to None.
        """
        rating_to_points: dict[str, int] = {
            "good": 100,
            "needs_improvement": 50,
            "poor": 0,
        }
        rating_map: dict[str, str] = {
            "lcp":  self.lcp_rating,
            "fcp":  self.fcp_rating,
            "tbt":  self.tbt_rating,
            "cls":  self.cls_rating,
            "ttfb": self.ttfb_rating,
        }

        weighted_score: float = 0.0
        total_weight: float = 0.0

        for metric, weight in PERFORMANCE_WEIGHTS.items():
            rating = rating_map.get(metric, "unknown")
            points = rating_to_points.get(rating)
            if points is not None:  # "unknown" is not in rating_to_points
                weighted_score += points * weight
                total_weight   += weight

        if total_weight > 0:
            self.performance_score = round(weighted_score / total_weight)
        else:
            self.performance_score = None

    def to_api_dict(self) -> dict:
        """
        Return a JSON-serialisable dict for the /lighthouse API endpoint.

        CLS uses "value" (not "value_ms") because it is a unitless score.
        TTI and SI use "n/a" rating as they are proxy metrics.
        """
        return {
            "performance_score": self.performance_score,
            "audit_method":      self.audit_method,
            "audited_at":        self.audited_at.isoformat() if self.audited_at else None,
            "error":             self.error,
            "metrics": {
                "lcp":  {"value_ms": self.lcp_ms,  "rating": self.lcp_rating},
                "fcp":  {"value_ms": self.fcp_ms,  "rating": self.fcp_rating},
                "tbt":  {"value_ms": self.tbt_ms,  "rating": self.tbt_rating},
                "cls":  {"value":    self.cls,      "rating": self.cls_rating},
                "ttfb": {"value_ms": self.ttfb_ms, "rating": self.ttfb_rating},
                "tti":  {"value_ms": self.tti_ms,  "rating": "n/a"},
                "si":   {"value_ms": self.si_ms,   "rating": "n/a"},
            },
            "page_load_ms": self.page_load_ms,
        }


# ── Main public function ──────────────────────────────────────────────────

def run_lighthouse_audit(
    url: str,
    timeout_ms: int = 30_000,
    wait_until: str = "networkidle",
) -> LighthouseResult:
    """
    Collect real Core Web Vitals for a URL using Playwright headless Chromium.

    Navigates to the URL, waits for the page to load, then injects JavaScript
    that reads NavigationTiming and PerformanceObserver APIs to collect LCP,
    FCP, CLS, TBT, TTFB, TTI, and page load time.

    Args:
        url:        Full URL including scheme (e.g. "https://example.com").
        timeout_ms: Maximum time in milliseconds to wait for page navigation.
                    Default 30,000ms (30 seconds).
        wait_until: Playwright navigation wait condition. Options:
                    "networkidle" (default), "load", "domcontentloaded".

    Returns:
        LighthouseResult dataclass. Always returns — never raises.
        On error, metrics are None and result.error contains the message.
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

            # Navigate — timeout is expected on slow sites; collect what we can
            try:
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            except PlaywrightTimeout:
                logger.warning(
                    "[LIGHTHOUSE] Navigation timeout for %s — collecting partial metrics",
                    url,
                )

            # Collect metrics (blocks ~3s for PerformanceObserver flush)
            try:
                raw: dict = page.evaluate(_METRICS_JS)
            finally:
                context.close()
                browser.close()

        # Map JS output to result fields
        result.ttfb_ms      = _safe_round(raw.get("ttfb"))
        result.fcp_ms       = _safe_round(raw.get("fcp"))
        result.lcp_ms       = _safe_round(raw.get("lcp"))
        result.cls          = round(float(raw.get("cls") or 0.0), 4)
        result.tbt_ms       = _safe_round(raw.get("longTaskMs"))
        result.tti_ms       = _safe_round(raw.get("domInteractive"))
        result.page_load_ms = _safe_round(raw.get("loadEventEnd"))

        if result.fcp_ms is not None and result.lcp_ms is not None:
            result.si_ms = round((result.fcp_ms + result.lcp_ms) / 2, 1)

        result.compute_ratings()
        result.compute_performance_score()

        logger.info(
            "[LIGHTHOUSE] CWV audit complete url=%s score=%s lcp=%sms cls=%s",
            url,
            result.performance_score,
            result.lcp_ms,
            result.cls,
        )

    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
        logger.error("[LIGHTHOUSE] Audit failed for %s: %s", url, result.error)

    return result
