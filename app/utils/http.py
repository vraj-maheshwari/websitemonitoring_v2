"""
utils/http.py
-------------
Reusable HTTP helpers — keeps service layer clean.
"""

import time
import httpx
from app.config.settings import Config


_http_client = None


def get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            follow_redirects=True,
            timeout=Config.HTTP_TIMEOUT,
            verify=Config.HTTP_VERIFY_SSL,
            headers={"User-Agent": Config.HTTP_USER_AGENT},
        )
    return _http_client


def fetch_url(url: str, timeout: int = Config.HTTP_TIMEOUT) -> dict:
    """
    Perform a GET request and return a normalised result dict.

    Returns:
        {
            "status_code":   int | None,
            "response_time": float,         # seconds
            "content":       str | None,    # raw HTML body
            "is_up":         bool,
            "error":         str | None,
        }
    """
    start = time.perf_counter()

    try:
        response = get_http_client().get(url, timeout=timeout)

        elapsed = time.perf_counter() - start
        return {
            "status_code":   response.status_code,
            "response_time": round(elapsed, 4),
            "content":       response.text,
            "is_up":         response.status_code < 400,
            "error":         None,
        }

    except httpx.TimeoutException:
        elapsed = time.perf_counter() - start
        return {
            "status_code":   None,
            "response_time": round(elapsed, 4),
            "content":       None,
            "is_up":         False,
            "error":         "Request timed out",
        }

    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return {
            "status_code":   None,
            "response_time": round(elapsed, 4),
            "content":       None,
            "is_up":         False,
            "error":         str(exc),
        }
