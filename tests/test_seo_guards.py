import pytest

from app.utils.http import fetch_url
from app.utils.seo_engine import analyze_seo, _score_performance


def test_fetch_url_requires_explicit_timeout():
    with pytest.raises(TypeError):
        fetch_url("https://example.com", timeout=None)


def test_analyze_seo_rejects_tiny_pages():
    with pytest.raises(ValueError):
        analyze_seo({"page_size_kb": 0.83})


def test_performance_score_uses_ttfb_before_total_time():
    score = _score_performance({
        "ttfb": 0.2,
        "total_response_time": 9.0,
        "page_size_kb": 20.0,
        "js_blocking_count": 0,
        "css_blocking_count": 0,
    })
    assert score == 100
