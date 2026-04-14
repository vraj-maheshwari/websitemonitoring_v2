"""
services/ssl_service.py
------------------------
SSL certificate check logic using the standard ssl module + pyOpenSSL.
"""

import ssl
import socket
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models.site    import Site
from app.models.ssl_log import SSLLog
from app.services.monitoring_service import CHECK_SSL, schedule_next_run

logger = logging.getLogger(__name__)

_SSL_PORT    = 443
_SSL_TIMEOUT = 10  # seconds


def run_ssl_check(site_id: int) -> SSLLog | None:
    """
    Check SSL certificate validity and expiry for *site_id*.

    Steps:
      1. Load site.
      2. Connect via TLS and retrieve the peer certificate.
      3. Parse expiry date and issuer.
      4. Persist as SSLLog.
      5. Trigger alerts if cert is invalid or expiring soon.
    """
    site: Site | None = db.session.get(Site, site_id)
    if site is None:
        logger.warning("run_ssl_check: Site %s not found.", site_id)
        return None

    hostname = _extract_hostname(site.url)
    logger.info("Checking SSL for %s", hostname)

    cert_data = _fetch_certificate(hostname)
    checked_at = datetime.utcnow()

    if cert_data["error"]:
        log = SSLLog(
            site_id=site.id,
            is_valid=False,
            error_message=cert_data["error"],
            checked_at=checked_at,
        )
        site.ssl_status = "INVALID"
        site.ssl_issuer = None
        site.ssl_expiry_date = None
        site.ssl_days_remaining = None
        site.ssl_last_error = cert_data["error"]
    else:
        expiry      = cert_data["expiry_date"]
        now_utc     = datetime.now(timezone.utc)
        days_left   = (expiry.replace(tzinfo=timezone.utc) - now_utc).days if expiry else None

        log = SSLLog(
            site_id=site.id,
            expiry_date=expiry,
            days_remaining=days_left,
            is_valid=cert_data["is_valid"],
            issuer=cert_data["issuer"],
            checked_at=checked_at,
        )
        site.ssl_status = "EXPIRING" if days_left is not None and days_left <= 7 else "VALID"
        site.ssl_issuer = cert_data["issuer"]
        site.ssl_expiry_date = expiry
        site.ssl_days_remaining = days_left
        site.ssl_last_error = None

    schedule_next_run(site, CHECK_SSL, checked_at)
    db.session.add(log)

    # ── Alert evaluation ───────────────────────────────────────────────────
    db.session.commit()

    logger.info(
        "SSL check done — %s | valid=%s | days_left=%s",
        hostname, log.is_valid, log.days_remaining
    )
    return log


def get_ssl_logs(site_id: int, limit: int = 50) -> list[dict]:
    logs = (
        SSLLog.query
        .filter_by(site_id=site_id)
        .order_by(SSLLog.checked_at.desc())
        .limit(limit)
        .all()
    )
    return [log.to_dict() for log in logs]


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_hostname(url: str) -> str:
    """Strip scheme and path to get a bare hostname."""
    hostname = url.replace("https://", "").replace("http://", "").split("/")[0]
    return hostname.split(":")[0]  # remove explicit port if present


def _fetch_certificate(hostname: str) -> dict:
    """
    Open a TLS socket and extract certificate metadata.

    Returns:
        {
            "expiry_date": datetime | None,
            "is_valid":    bool,
            "issuer":      str | None,
            "error":       str | None,
        }
    """
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, _SSL_PORT),
                                      timeout=_SSL_TIMEOUT) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        # notAfter format: 'May 10 12:00:00 2025 GMT'
        expiry_str  = cert.get("notAfter", "")
        expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")

        # Build a readable issuer string from the nested tuple structure
        issuer_dict = dict(x[0] for x in cert.get("issuer", []))
        issuer = issuer_dict.get("organizationName") or issuer_dict.get("commonName", "Unknown")

        return {
            "expiry_date": expiry_date,
            "is_valid":    True,
            "issuer":      issuer,
            "error":       None,
        }

    except ssl.SSLCertVerificationError as exc:
        return {"expiry_date": None, "is_valid": False,
                "issuer": None, "error": f"SSL verification failed: {exc}"}
    except ssl.SSLError as exc:
        return {"expiry_date": None, "is_valid": False,
                "issuer": None, "error": f"SSL error: {exc}"}
    except (socket.timeout, TimeoutError):
        return {"expiry_date": None, "is_valid": False,
                "issuer": None, "error": "Connection timed out"}
    except Exception as exc:  # noqa: BLE001
        return {"expiry_date": None, "is_valid": False,
                "issuer": None, "error": str(exc)}
