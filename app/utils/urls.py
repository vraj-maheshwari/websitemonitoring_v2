from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> tuple[str, str]:
    raw_url = (url or "").strip()
    if not raw_url:
        raise ValueError("URL is required")

    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"

    parsed = urlsplit(raw_url)
    scheme = parsed.scheme.lower() or "https"
    if scheme not in ["http", "https"]:
        raise ValueError("Only http and https protocols are supported")
        
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("URL hostname is required")

    port = parsed.port
    if port and ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        port = None

    netloc = hostname if port is None else f"{hostname}:{port}"
    path = parsed.path or ""
    if path != "/":
        path = path.rstrip("/")
    query = parsed.query

    canonical_url = urlunsplit((scheme, netloc, path or "/", query, ""))
    normalized_url = urlunsplit(("https", hostname, path or "/", query, ""))
    return canonical_url, normalized_url
