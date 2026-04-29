"""
services/ssl_service.py
------------------------
SSL certificate check logic using the standard ssl module + pyOpenSSL.
Upgraded for SaaS granular status tracking and resilience.
"""

import ssl
import socket
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models.site    import Site
from app.models.ssl_log import SSLLog
from app.services import alert_service
from app.services.monitoring_service import CHECK_SSL, schedule_next_run
from app.utils.time import now_utc

logger = logging.getLogger(__name__)

_SSL_PORT    = 443
_SSL_TIMEOUT = 10  # seconds

def run_ssl_check(site_id: int) -> SSLLog | None:
    """
    Check SSL certificate validity and expiry for *site_id*.
    """
    site: Site | None = db.session.get(Site, site_id)
    if site is None:
        logger.warning("run_ssl_check: Site %s not found.", site_id)
        return None

    hostname = _extract_hostname(site.url)
    logger.info("Checking SSL for %s", hostname)

    try:
        cert_data = _fetch_certificate(hostname)
        checked_at = now_utc()

        if cert_data["error"]:
            log = SSLLog(
                site_id=site.id,
                is_valid=False,
                state="ERROR",
                error_message=cert_data["error"],
                checked_at=checked_at,
            )
            site.ssl_state = "ERROR"
            site.ssl_status = "done"
            site.ssl_issuer = None
            site.ssl_expiry_date = None
            site.ssl_days_remaining = None
            site.ssl_last_error = cert_data["error"]
        else:
            expiry      = cert_data["expiry_date"]
            current_now = now_utc()
            days_left   = (expiry - current_now).days if expiry else None

            log = SSLLog(
                site_id=site.id,
                expiry_date=expiry,
                days_remaining=days_left,
                is_valid=cert_data["is_valid"],
                state=_ssl_state(days_left),
                issuer=cert_data["issuer"],
                checked_at=checked_at,
            )
            site.ssl_state = log.state
            site.ssl_status = "done"
            site.ssl_issuer = cert_data["issuer"]
            site.ssl_expiry_date = expiry
            site.ssl_days_remaining = days_left
            site.ssl_last_error = None

        schedule_next_run(site, CHECK_SSL, checked_at)
        db.session.add(log)
        
        # Trigger alerts
        alert_service.check_ssl_alerts(
            site=site,
            is_valid=log.is_valid,
            days_remaining=log.days_remaining,
            expiry_date=log.expiry_date,
            checked_at=checked_at
        )
        
        logger.info(
            "SSL check done — %s | valid=%s | days_left=%s",
            hostname, log.is_valid, log.days_remaining
        )
        db.session.commit()
        return log

    except Exception as exc:
        logger.exception("SSL check crashed for %s", hostname)
        site.ssl_status = "failed"
        raise


def get_ssl_logs(site_id: int, limit: int = 50) -> list[dict]:
    logs = (
        SSLLog.query
        .filter_by(site_id=site_id)
        .order_by(SSLLog.checked_at.desc())
        .limit(limit)
        .all()
    )
    return [log.to_dict() for log in logs]


from urllib.parse import urlparse


def _extract_hostname(url: str) -> str:
    """Strip scheme and path to get a bare hostname."""
    parsed = urlparse(url)
    hostname = parsed.hostname or url.split("/")[0]
    return hostname


def _fetch_certificate(hostname: str) -> dict:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, _SSL_PORT),
                                      timeout=_SSL_TIMEOUT) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        expiry_str  = cert.get("notAfter", "")
        expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)

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
                "issuer": None, "error": f"Cert verify failed: {exc}"}
    except ssl.SSLError as exc:
        return {"expiry_date": None, "is_valid": False,
                "issuer": None, "error": f"SSL error: {exc}"}
    except (socket.timeout, TimeoutError):
        return {"expiry_date": None, "is_valid": False,
                "issuer": None, "error": "Connection timed out"}
    except Exception as exc:
        return {"expiry_date": None, "is_valid": False,
                "issuer": None, "error": str(exc)}


def _ssl_state(days_left: int | None) -> str:
    if days_left is None:
        return "ERROR"
    if days_left < 0:
        return "EXPIRED"
    if days_left < 14:
        return "EXPIRING"
    return "VALID"
