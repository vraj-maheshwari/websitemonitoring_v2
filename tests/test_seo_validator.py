from app.utils.seo_validator import validate_seo_fetch


def test_empty_content_is_invalid():
    result = validate_seo_fetch("", 0.0, None, None, "https://example.com")
    assert result.is_valid is False
    assert result.fetch_status == "empty"


def test_small_page_is_invalid():
    tiny_html = "<html><body>Hello</body></html>"
    result = validate_seo_fetch(tiny_html, 0.83, 200, None, "https://example.com")
    assert result.is_valid is False
    assert result.fetch_status == "invalid_content"
    assert "0.83 KB" in result.reason


def test_host_placeholder_detected():
    placeholder = "<html><body>This site is temporarily unavailable.</body></html>"
    result = validate_seo_fetch(placeholder, 2.5, 200, None, "https://example.com")
    assert result.is_valid is False
    assert "placeholder" in result.reason.lower()


def test_real_page_is_valid():
    real_html = "<html>" + "x" * 20000 + "</html>"
    result = validate_seo_fetch(real_html, 20.0, 200, None, "https://example.com")
    assert result.is_valid is True
    assert result.fetch_status == "ok"


def test_http_error_is_invalid():
    result = validate_seo_fetch("<html>Not found</html>", 10.0, 404, None, "https://example.com")
    assert result.is_valid is False
    assert "404" in result.reason


def test_html_preview_saved():
    html = "<html>" + "a" * 2000 + "</html>"
    result = validate_seo_fetch(html, 20.0, 200, None, "https://example.com")
    assert len(result.html_preview) == 1000


def test_timeout_error_has_timeout_status():
    result = validate_seo_fetch("", 0.0, None, "Read timeout", "https://example.com")
    assert result.is_valid is False
    assert result.fetch_status == "timeout"
