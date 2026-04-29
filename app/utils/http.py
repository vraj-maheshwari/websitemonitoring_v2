"""
utils/http.py
-------------
Enhanced HTTP helpers for monitoring and SEO audits.
"""

import time
import httpx
from app.config.settings import Config


_http_client: httpx.Client | None = None


def get_http_client(refresh: bool = False) -> httpx.Client:
    """Returns the shared httpx.Client. If refresh=True, a new client is created."""
    global _http_client
    if _http_client is None or refresh:
        if _http_client:
            _http_client.close()
        _http_client = httpx.Client(
            follow_redirects=True,
            timeout=None,
            verify=Config.HTTP_VERIFY_SSL,
            headers={"User-Agent": Config.HTTP_USER_AGENT},
        )
    return _http_client


def refresh_http_client() -> None:
    """Explicitly recreates the global HTTP client to pick up config changes."""
    get_http_client(refresh=True)


def fetch_url(url: str, timeout: float, stream_for_ttfb: bool = False, max_bytes: int | None = None) -> dict:
    """
    Perform a GET request and return a normalised result dict.
    Captured metadata includes true streaming TTFB and redirect history.
    """
    if timeout is None:
        raise TypeError("fetch_url() requires an explicit timeout")

    start = time.perf_counter()
    client = get_http_client()
    ttfb = None
    attempts = 0

    while True:
        try:
            if stream_for_ttfb or max_bytes:
                return _fetch_streaming(client, url, timeout, start, max_bytes)

            response = client.get(url, timeout=timeout)
            ttfb = round(response.elapsed.total_seconds(), 4)
            return _make_result(response, start, ttfb, content=response.text)

        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.TimeoutException) as exc:
            if attempts >= 2:
                return _make_error_result(start, str(exc) or "Request failed")
            time.sleep(2 ** attempts)
            attempts += 1
        except Exception as exc:  # noqa: BLE001
            return _make_error_result(start, str(exc))


def _fetch_streaming(client: httpx.Client, url: str, timeout: float, start: float, max_bytes: int | None) -> dict:
    ttfb = None
    with client.stream("GET", url, timeout=timeout) as response:
        ctype = response.headers.get("Content-Type", "").lower()
        if max_bytes and "text/html" not in ctype:
            return _make_result(response, start, ttfb, error=f"Invalid Content-Type: {ctype}")

        clength = response.headers.get("Content-Length")
        if max_bytes and clength and int(clength) > max_bytes:
            return _make_result(response, start, ttfb, error="Response too large")

        content_chunks = []
        bytes_read = 0
        for chunk in response.iter_bytes():
            if ttfb is None:
                ttfb = round(time.perf_counter() - start, 4)
            bytes_read += len(chunk)
            if max_bytes and bytes_read > max_bytes:
                return _make_result(response, start, ttfb, error="Size limit exceeded")
            content_chunks.append(chunk)

        if ttfb is None:
            ttfb = round(time.perf_counter() - start, 4)
        content = b"".join(content_chunks).decode("utf-8", errors="replace")
        return _make_result(response, start, ttfb, content=content)


def check_file_exists(url: str) -> bool:
    """Check if a file (like robots.txt) exists with a 200 OK status."""
    client = get_http_client()
    try:
        response = client.head(url, timeout=5, follow_redirects=True)
        return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _make_result(response, start_time, ttfb, content=None, error=None):
    elapsed = round(time.perf_counter() - start_time, 4)
    # Check if we landed on HTTPS and if we arrived there via redirect
    final_url = str(response.url)
    https_enforced = final_url.startswith("https://") and len(response.history) > 0
    
    return {
        "status_code":   response.status_code,
        "response_time": elapsed,
        "ttfb":          ttfb,
        "content":       content,
        "is_up":         response.status_code < 400 and not error,
        "error":         error,
        "headers":       dict(response.headers),
        "https_redirect": https_enforced,
        "final_url":     final_url,
    }


def _make_error_result(start_time, error):
    return {
        "status_code":   None,
        "response_time": round(time.perf_counter() - start_time, 4),
        "ttfb":          None,
        "content":       None,
        "is_up":         False,
        "error":         error,
        "headers":       {},
        "https_redirect": False,
        "final_url":     None,
    }
