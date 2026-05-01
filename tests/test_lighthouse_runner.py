from unittest.mock import MagicMock, patch

import pytest

from app.utils.lighthouse_runner import (
    _METRICS_JS,
    _safe_round,
    LighthouseResult,
    PlaywrightTimeout,
    compute_cwv_rating,
    run_lighthouse_audit,
)


GOOD_METRICS_RESPONSE = {
    "ttfb": 200.0,
    "fcp": 900.0,
    "lcp": 1500.0,
    "cls": 0.02,
    "longTaskMs": 50.0,
    "longTaskCount": 1,
    "domInteractive": 1200.0,
    "loadEventEnd": 2000.0,
}

POOR_METRICS_RESPONSE = {
    "ttfb": 3000.0,
    "fcp": 5000.0,
    "lcp": 8000.0,
    "cls": 0.5,
    "longTaskMs": 1500.0,
    "longTaskCount": 12,
    "domInteractive": 7000.0,
    "loadEventEnd": 10000.0,
}


def _make_playwright_mock(js_return, nav_raises=None):
    mock_page = MagicMock()
    mock_page.evaluate.return_value = js_return
    if nav_raises is not None:
        mock_page.goto.side_effect = nav_raises
    else:
        mock_page.goto.return_value = None

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser

    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_p)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


@pytest.mark.parametrize(
    "metric,value,expected",
    [
        ("lcp", 2500, "good"),
        ("lcp", 2501, "needs_improvement"),
        ("lcp", 4000, "needs_improvement"),
        ("lcp", 4001, "poor"),
        ("tbt", 200, "good"),
        ("tbt", 201, "needs_improvement"),
        ("tbt", 600, "needs_improvement"),
        ("tbt", 601, "poor"),
        ("cls", 0.10, "good"),
        ("cls", 0.11, "needs_improvement"),
        ("cls", 0.25, "needs_improvement"),
        ("cls", 0.26, "poor"),
        ("fcp", 1800, "good"),
        ("fcp", 3000, "needs_improvement"),
        ("fcp", 3001, "poor"),
        ("ttfb", 800, "good"),
        ("ttfb", 1800, "needs_improvement"),
        ("ttfb", 1801, "poor"),
        ("lcp", None, "unknown"),
        ("cls", None, "unknown"),
        ("xyz", 100, "unknown"),
        ("lcp", 0, "good"),
    ],
)
def test_compute_cwv_rating(metric, value, expected):
    assert compute_cwv_rating(metric, value) == expected


def test_result_defaults_all_none():
    result = LighthouseResult(url="https://example.com")
    assert result.lcp_ms is None
    assert result.performance_score is None
    assert result.error is None
    assert result.audit_method == "playwright_perf"
    assert result.lcp_rating == "unknown"


def test_compute_ratings_sets_all_fields():
    result = LighthouseResult(
        url="https://x.com",
        lcp_ms=2000,
        tbt_ms=100,
        cls=0.05,
        fcp_ms=1000,
        ttfb_ms=300,
    )
    result.compute_ratings()
    assert result.lcp_rating == "good"
    assert result.tbt_rating == "good"
    assert result.cls_rating == "good"
    assert result.fcp_rating == "good"
    assert result.ttfb_rating == "good"


def test_performance_score_all_good_equals_100():
    result = LighthouseResult(
        url="https://x.com",
        lcp_ms=2000,
        tbt_ms=100,
        cls=0.05,
        fcp_ms=1000,
        ttfb_ms=300,
    )
    result.compute_ratings()
    result.compute_performance_score()
    assert result.performance_score == 100


def test_performance_score_all_poor_equals_0():
    result = LighthouseResult(
        url="https://x.com",
        lcp_ms=9000,
        tbt_ms=1000,
        cls=0.9,
        fcp_ms=6000,
        ttfb_ms=3000,
    )
    result.compute_ratings()
    result.compute_performance_score()
    assert result.performance_score == 0


def test_performance_score_all_unknown_is_none():
    result = LighthouseResult(url="https://x.com")
    result.compute_ratings()
    result.compute_performance_score()
    assert result.performance_score is None


def test_to_api_dict_shape():
    result = LighthouseResult(url="https://x.com", lcp_ms=2000, tbt_ms=100, cls=0.05)
    result.compute_ratings()
    data = result.to_api_dict()
    assert "performance_score" in data
    assert "metrics" in data
    assert set(data["metrics"].keys()) == {"lcp", "fcp", "tbt", "cls", "ttfb", "tti", "si"}
    assert "value_ms" in data["metrics"]["lcp"]
    assert "rating" in data["metrics"]["lcp"]
    assert "value" in data["metrics"]["cls"]
    assert "audited_at" in data


def test_cls_precision():
    result = LighthouseResult(url="https://x.com", cls=0.123456789)
    assert result.cls == 0.123456789


@patch("app.utils.lighthouse_runner.sync_playwright")
def test_success_returns_populated_result(mock_pw):
    mock_pw.return_value = _make_playwright_mock(GOOD_METRICS_RESPONSE)
    result = run_lighthouse_audit("https://example.com")

    assert result.error is None
    assert result.lcp_ms == 1500.0
    assert result.ttfb_ms == 200.0
    assert result.cls == 0.02
    assert result.tbt_ms == 50.0
    assert result.lcp_rating == "good"
    assert result.performance_score == 100


@patch("app.utils.lighthouse_runner.sync_playwright")
def test_poor_site_scores_zero(mock_pw):
    mock_pw.return_value = _make_playwright_mock(POOR_METRICS_RESPONSE)
    result = run_lighthouse_audit("https://slow.com")

    assert result.performance_score == 0
    assert result.lcp_rating == "poor"
    assert result.tbt_rating == "poor"
    assert result.cls_rating == "poor"
    assert result.ttfb_rating == "poor"


@patch("app.utils.lighthouse_runner.sync_playwright")
def test_playwright_crash_returns_error_result(mock_pw):
    mock_pw.side_effect = Exception("Chromium binary not found")
    result = run_lighthouse_audit("https://example.com")

    assert isinstance(result, LighthouseResult)
    assert result.error is not None
    assert "Chromium binary not found" in result.error
    assert result.lcp_ms is None
    assert result.performance_score is None


@patch("app.utils.lighthouse_runner.sync_playwright")
def test_navigation_timeout_collects_partial_metrics(mock_pw):
    mock_pw.return_value = _make_playwright_mock(
        js_return=GOOD_METRICS_RESPONSE,
        nav_raises=PlaywrightTimeout("Timeout 30000ms exceeded"),
    )
    result = run_lighthouse_audit("https://slow-site.com")

    assert isinstance(result, LighthouseResult)
    assert result.error is None
    assert result.lcp_ms == 1500.0


@patch("app.utils.lighthouse_runner.sync_playwright")
def test_speed_index_computed_when_fcp_and_lcp_available(mock_pw):
    mock_pw.return_value = _make_playwright_mock({
        **GOOD_METRICS_RESPONSE,
        "fcp": 1000.0,
        "lcp": 2000.0,
    })
    result = run_lighthouse_audit("https://example.com")
    assert result.si_ms == 1500.0


@patch("app.utils.lighthouse_runner.sync_playwright")
def test_speed_index_none_when_lcp_missing(mock_pw):
    mock_pw.return_value = _make_playwright_mock({**GOOD_METRICS_RESPONSE, "lcp": None})
    result = run_lighthouse_audit("https://example.com")
    assert result.si_ms is None


@patch("app.utils.lighthouse_runner.sync_playwright")
def test_cls_floors_at_zero(mock_pw):
    mock_pw.return_value = _make_playwright_mock({**GOOD_METRICS_RESPONSE, "cls": 0.0})
    result = run_lighthouse_audit("https://example.com")
    assert result.cls == 0.0
    assert result.cls_rating == "good"


@patch("app.utils.lighthouse_runner.sync_playwright")
def test_browser_closed_on_evaluate_exception(mock_pw):
    """Verify browser.close() is called even when evaluate() raises."""
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.evaluate.side_effect = Exception("JS evaluation failed")
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context
    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_p)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_pw.return_value = mock_cm

    result = run_lighthouse_audit("https://example.com")

    mock_context.close.assert_called_once()
    mock_browser.close.assert_called_once()
    assert result.error is not None


def test_safe_round_handles_none():
    assert _safe_round(None) is None


def test_safe_round_handles_string_number():
    assert _safe_round("123.456") == 123.5


def test_safe_round_handles_invalid_string():
    assert _safe_round("not-a-number") is None


def test_evaluate_uses_metrics_js_constant():
    mock_cm = _make_playwright_mock(GOOD_METRICS_RESPONSE)
    mock_page = mock_cm.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value
    with patch("app.utils.lighthouse_runner.sync_playwright", return_value=mock_cm):
        run_lighthouse_audit("https://example.com")
    mock_page.evaluate.assert_called_once_with(_METRICS_JS)
