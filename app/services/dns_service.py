import socket
import time
from urllib.parse import urlparse

import dns.resolver

from app.models.dns_log import DNSLog
from app.utils.time import now_utc


def resolve_dns(hostname: str) -> dict:
    """
    Resolve hostname and return A, NS, and MX DNS information.
    """
    start = time.perf_counter()
    try:
        addrinfo = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        resolution_time_ms = (time.perf_counter() - start) * 1000
        ip_addresses = sorted({item[4][0] for item in addrinfo})
    except Exception as exc:  # noqa: BLE001
        return {
            "resolved": False,
            "resolution_time_ms": (time.perf_counter() - start) * 1000,
            "ip_addresses": [],
            "nameservers": [],
            "mx_records": [],
            "error": str(exc),
        }

    return {
        "resolved": True,
        "resolution_time_ms": resolution_time_ms,
        "ip_addresses": ip_addresses,
        "nameservers": _resolve_records(hostname, "NS"),
        "mx_records": _resolve_records(hostname, "MX"),
        "error": None,
    }


def detect_dns_hijacking(hostname: str, expected_ips: list[str]) -> dict:
    current_ips = resolve_dns(hostname)["ip_addresses"]
    expected = sorted(set(expected_ips or []))
    current = sorted(set(current_ips))
    new_ips = sorted(set(current) - set(expected))
    removed_ips = sorted(set(expected) - set(current))
    return {
        "hijack_suspected": bool(expected and new_ips),
        "current_ips": current,
        "expected_ips": expected,
        "new_ips": new_ips,
        "removed_ips": removed_ips,
    }


def detect_nameserver_changes(hostname: str, expected_ns: list[str]) -> dict:
    current_ns = _resolve_records(hostname, "NS")
    expected = _normalize_records(expected_ns or [])
    current = _normalize_records(current_ns)
    added_ns = sorted(set(current) - set(expected))
    removed_ns = sorted(set(expected) - set(current))
    return {
        "changed": bool(expected and (added_ns or removed_ns)),
        "current_ns": current,
        "expected_ns": expected,
        "added_ns": added_ns,
        "removed_ns": removed_ns,
    }


def run_dns_check(site) -> dict:
    """
    Full DNS check for a site.
    """
    hostname = _hostname_from_url(site.normalized_url or site.url)
    result = resolve_dns(hostname)
    previous = (
        DNSLog.query
        .filter_by(site_id=site.id, resolved=True)
        .order_by(DNSLog.checked_at.desc())
        .first()
    )
    expected_ips = previous.ip_addresses if previous else []
    expected_ns = previous.nameservers if previous else []

    hijack = _compare_ips(result["ip_addresses"], expected_ips)
    ns_change = _compare_ns(result["nameservers"], expected_ns)

    return {
        **result,
        "hostname": hostname,
        "checked_at": now_utc(),
        "hijack_suspected": hijack["hijack_suspected"],
        "expected_ips": hijack["expected_ips"],
        "new_ips": hijack["new_ips"],
        "removed_ips": hijack["removed_ips"],
        "ns_changed": ns_change["changed"],
        "expected_ns": ns_change["expected_ns"],
        "added_ns": ns_change["added_ns"],
        "removed_ns": ns_change["removed_ns"],
    }


def _resolve_records(hostname: str, record_type: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(hostname, record_type)
    except Exception:  # noqa: BLE001
        return []
    return _normalize_records([answer.to_text() for answer in answers])


def _normalize_records(records: list[str]) -> list[str]:
    return sorted({record.rstrip(".").lower() for record in records if record})


def _compare_ips(current_ips: list[str], expected_ips: list[str]) -> dict:
    expected = sorted(set(expected_ips or []))
    current = sorted(set(current_ips or []))
    new_ips = sorted(set(current) - set(expected))
    removed_ips = sorted(set(expected) - set(current))
    return {
        "hijack_suspected": bool(expected and new_ips),
        "current_ips": current,
        "expected_ips": expected,
        "new_ips": new_ips,
        "removed_ips": removed_ips,
    }


def _compare_ns(current_ns: list[str], expected_ns: list[str]) -> dict:
    expected = _normalize_records(expected_ns or [])
    current = _normalize_records(current_ns or [])
    added_ns = sorted(set(current) - set(expected))
    removed_ns = sorted(set(expected) - set(current))
    return {
        "changed": bool(expected and (added_ns or removed_ns)),
        "current_ns": current,
        "expected_ns": expected,
        "added_ns": added_ns,
        "removed_ns": removed_ns,
    }


def _hostname_from_url(url: str) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname if parsed.hostname else urlparse(f"https://{url}").hostname
    if not hostname:
        raise ValueError("Site URL does not contain a hostname")
    return hostname
