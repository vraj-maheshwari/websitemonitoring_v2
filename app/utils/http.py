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


RETRY_DELAYS = [1.0, 2.0]


def fetch_url(url: str, timeout: float, stream_for_ttfb: bool = False, max_bytes: int | None = None) -> dict:
    """
    Perform a GET request and return a normalised result dict.
    Captured metadata includes true streaming TTFB and redirect history.
    """
    if timeout is None:
        raise TypeError("fetch_url() requires an explicit timeout. Never use None.")

    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay > 0:
            time.sleep(delay)
        try:
            if stream_for_ttfb:
                return _fetch_streaming_ttfb(url, timeout, max_bytes=max_bytes)

            start = time.perf_counter()
            client = get_http_client()
            response = client.get(url, timeout=timeout)
            total_time = time.perf_counter() - start
            return _make_result(
                response=response,
                total_time=total_time,
                ttfb=total_time,
                html_content=response.text,
            )
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.TimeoutException, httpx.NetworkError) as e:
            if attempt == len(RETRY_DELAYS):
                return _make_error_result(str(e))
        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            return _make_error_result(str(exc))

    # Safety fallback: all retries exhausted without returning a result.
    return _make_error_result("All retries exhausted without a result")


def _fetch_streaming_ttfb(url: str, timeout: float, max_bytes: int | None = None) -> dict:
    start = time.perf_counter()
    ttfb = None
    chunks = []
    bytes_read = 0
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        verify=Config.HTTP_VERIFY_SSL,
        headers={"User-Agent": Config.HTTP_USER_AGENT},
    ) as client:
        with client.stream("GET", url) as response:
            for chunk in response.iter_bytes():
                if ttfb is None:
                    ttfb = time.perf_counter() - start
                bytes_read += len(chunk)
                if max_bytes and bytes_read > max_bytes:
                    break
                chunks.append(chunk)
    total_time = time.perf_counter() - start
    html_content = b"".join(chunks).decode("utf-8", errors="replace")
    page_size_kb = len(html_content.encode()) / 1024
    return {
        "html_content": html_content,
        "ttfb": ttfb,
        "total_response_time": total_time,
        "status_code": response.status_code,
        "is_up": response.status_code < 400,
        "final_url": str(response.url),
        "https_redirect": str(response.url).startswith("https://"),
        "page_size_kb": page_size_kb,
        "error": None,
        "response_time": total_time,
        "content": html_content,
        "headers": dict(response.headers),
    }


def _fetch_streaming(client: httpx.Client, url: str, timeout: float, start: float, max_bytes: int | None) -> dict:
    ttfb = None
    with client.stream("GET", url, timeout=timeout) as response:
        ctype = response.headers.get("Content-Type", "").lower()
        if max_bytes and "text/html" not in ctype:
            return _make_result(response, time.perf_counter() - start, ttfb, error=f"Invalid Content-Type: {ctype}")

        clength = response.headers.get("Content-Length")
        if max_bytes and clength and int(clength) > max_bytes:
            return _make_result(response, time.perf_counter() - start, ttfb, error="Response too large")

        content_chunks = []
        bytes_read = 0
        for chunk in response.iter_bytes():
            if ttfb is None:
                ttfb = round(time.perf_counter() - start, 4)
            bytes_read += len(chunk)
            if max_bytes and bytes_read > max_bytes:
                return _make_result(response, time.perf_counter() - start, ttfb, error="Size limit exceeded")
            content_chunks.append(chunk)

        if ttfb is None:
            ttfb = round(time.perf_counter() - start, 4)
        content = b"".join(content_chunks).decode("utf-8", errors="replace")
        return _make_result(response, time.perf_counter() - start, ttfb, html_content=content)


def check_file_exists(url: str) -> bool:
    """Check if a file (like robots.txt) exists with a 200 OK status."""
    client = get_http_client()
    try:
        response = client.head(url, timeout=8.0, follow_redirects=True)
        return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _make_result(response, total_time, ttfb, html_content="", error=None):
    final_url = str(response.url)
    https_enforced = final_url.startswith("https://") and len(response.history) > 0
    page_size_kb = len((html_content or "").encode()) / 1024
    
    return {
        "status_code":   response.status_code,
        "response_time": total_time,
        "total_response_time": total_time,
        "ttfb":          ttfb,
        "content":       html_content,
        "html_content":  html_content,
        "is_up":         response.status_code < 400 and not error,
        "error":         error,
        "headers":       dict(response.headers),
        "https_redirect": https_enforced,
        "final_url":     final_url,
        "page_size_kb":  page_size_kb,
    }


def _make_error_result(error):
    return {
        "status_code":   None,
        "response_time": None,
        "total_response_time": None,
        "ttfb":          None,
        "content":       None,
        "html_content":  "",
        "is_up":         False,
        "error":         error,
        "headers":       {},
        "https_redirect": False,
        "final_url":     None,
        "page_size_kb":  0.0,
    }
