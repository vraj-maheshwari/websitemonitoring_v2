"""
utils/cwv_estimator.py
-----------------------
Server-side proxy estimates for Core Web Vitals.

Real CWV (LCP, FID, CLS) require a browser with JavaScript execution.
We cannot measure them from a server-side HTTP fetch. Instead, we derive
*proxy estimates* from signals we CAN measure:

  LCP proxy  — TTFB + estimated render time from page size and blocking resources
  FID proxy  — Total blocking JS weight in <head> (main-thread blocking time proxy)
  CLS proxy  — Presence of images without explicit width/height, layout-shifting
               patterns (ads, iframes without dimensions, late-loading fonts)

These are clearly labelled as estimates, not real field data.
For real CWV, use Google PageSpeed Insights API or Chrome UX Report.
"""

from dataclasses import dataclass


@dataclass
class CWVEstimate:
    # LCP — Largest Contentful Paint proxy (seconds)
    lcp_estimate_s: float
    lcp_rating: str          # "good" | "needs_improvement" | "poor"

    # FID — First Input Delay proxy (milliseconds, estimated from JS blocking)
    fid_estimate_ms: float
    fid_rating: str

    # CLS — Cumulative Layout Shift proxy (unitless score 0.0–1.0+)
    cls_estimate: float
    cls_rating: str

    # Explanation strings shown in the UI
    lcp_note: str
    fid_note: str
    cls_note: str


# CWV thresholds (Google's official values)
_LCP_GOOD = 2.5
_LCP_POOR = 4.0
_FID_GOOD = 100.0
_FID_POOR = 300.0
_CLS_GOOD = 0.1
_CLS_POOR = 0.25


def _rate_lcp(s: float) -> str:
    if s <= _LCP_GOOD:
        return "good"
    if s <= _LCP_POOR:
        return "needs_improvement"
    return "poor"


def _rate_fid(ms: float) -> str:
    if ms <= _FID_GOOD:
        return "good"
    if ms <= _FID_POOR:
        return "needs_improvement"
    return "poor"


def _rate_cls(score: float) -> str:
    if score <= _CLS_GOOD:
        return "good"
    if score <= _CLS_POOR:
        return "needs_improvement"
    return "poor"


def estimate_cwv(signals: dict, ttfb: float | None) -> CWVEstimate:
    """
    Derive CWV proxy estimates from SEO/performance signals.

    Args:
        signals: The signals dict produced by parse_seo_intelligence().
        ttfb:    Time-to-first-byte in seconds (from streaming fetch).

    Returns:
        CWVEstimate dataclass.
    """
    ttfb = ttfb or 0.8  # assume moderate if unknown

    # ── LCP Estimate ──────────────────────────────────────────────────────
    # LCP ≈ TTFB + render_delay
    # render_delay is estimated from:
    #   - page size (larger HTML = more parse time)
    #   - blocking CSS in <head> (each adds ~50ms)
    #   - blocking JS in <head> (each adds ~80ms)
    page_size_kb = float(signals.get("page_size_kb") or 0.0)
    js_blocking  = int(signals.get("js_blocking_count") or 0)
    css_blocking = int(signals.get("css_blocking_count") or 0)

    size_penalty   = min(page_size_kb / 1000.0 * 0.5, 1.0)   # up to +1.0s for 2MB page
    js_penalty     = js_blocking  * 0.08                       # 80ms per blocking script
    css_penalty    = css_blocking * 0.05                       # 50ms per blocking stylesheet
    render_delay   = size_penalty + js_penalty + css_penalty
    lcp_estimate   = round(ttfb + render_delay, 2)

    lcp_note = (
        f"Estimated from TTFB ({ttfb:.2f}s) + render delay "
        f"({render_delay:.2f}s from {js_blocking} blocking scripts, "
        f"{css_blocking} blocking stylesheets, {page_size_kb:.0f} KB page). "
        "Not a real browser measurement."
    )

    # ── FID Estimate ──────────────────────────────────────────────────────
    # FID proxy = total blocking JS weight in <head>
    # Each blocking script adds ~80ms of main-thread blocking time
    fid_estimate_ms = round(js_blocking * 80.0, 1)
    fid_note = (
        f"Estimated from {js_blocking} render-blocking script(s) in <head>. "
        "Each blocking script delays interactivity by ~80ms. "
        "Not a real browser measurement."
    )

    # ── CLS Estimate ──────────────────────────────────────────────────────
    # CLS proxy — count layout-shift risk factors:
    #   - images without explicit dimensions (most common CLS cause)
    #   - iframes without dimensions
    #   - late-loading web fonts (heuristic: no preload link for fonts)
    image_count       = int(signals.get("image_count") or 0)
    missing_alt_count = int(signals.get("missing_alt_count") or 0)
    # Images missing alt often also lack width/height — use as proxy
    # Each unsized image contributes ~0.05 to CLS (rough industry estimate)
    unsized_images = missing_alt_count  # best proxy we have without a browser
    cls_estimate   = round(min(unsized_images * 0.05, 1.0), 3)

    cls_note = (
        f"Estimated from {unsized_images} image(s) missing alt text "
        "(images without alt often also lack explicit dimensions, a primary CLS cause). "
        "Not a real browser measurement."
    )

    return CWVEstimate(
        lcp_estimate_s=lcp_estimate,
        lcp_rating=_rate_lcp(lcp_estimate),
        fid_estimate_ms=fid_estimate_ms,
        fid_rating=_rate_fid(fid_estimate_ms),
        cls_estimate=cls_estimate,
        cls_rating=_rate_cls(cls_estimate),
        lcp_note=lcp_note,
        fid_note=fid_note,
        cls_note=cls_note,
    )


def cwv_to_dict(cwv: CWVEstimate) -> dict:
    return {
        "lcp_estimate_s":  cwv.lcp_estimate_s,
        "lcp_rating":      cwv.lcp_rating,
        "lcp_note":        cwv.lcp_note,
        "fid_estimate_ms": cwv.fid_estimate_ms,
        "fid_rating":      cwv.fid_rating,
        "fid_note":        cwv.fid_note,
        "cls_estimate":    cwv.cls_estimate,
        "cls_rating":      cwv.cls_rating,
        "cls_note":        cwv.cls_note,
    }
