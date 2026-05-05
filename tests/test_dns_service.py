from app.extensions import db
from app.models.dns_log import DNSLog
from app.models.site import Site
from app.models.user import User
from app.services import dns_service
from app.services.monitoring_service import CHECK_DNS, ensure_dns_monitoring_defaults, get_due_site_ids
from app.utils.time import now_utc


def test_detect_dns_hijacking_ignores_first_check(monkeypatch):
    monkeypatch.setattr(dns_service, "resolve_dns", lambda _hostname: {"ip_addresses": ["203.0.113.10"]})

    result = dns_service.detect_dns_hijacking("example.com", [])

    assert result["hijack_suspected"] is False
    assert result["new_ips"] == ["203.0.113.10"]


def test_detect_dns_hijacking_flags_new_ip(monkeypatch):
    monkeypatch.setattr(dns_service, "resolve_dns", lambda _hostname: {"ip_addresses": ["203.0.113.10", "203.0.113.11"]})

    result = dns_service.detect_dns_hijacking("example.com", ["203.0.113.10"])

    assert result["hijack_suspected"] is True
    assert result["new_ips"] == ["203.0.113.11"]


def test_detect_nameserver_changes_flags_added_and_removed(monkeypatch):
    monkeypatch.setattr(dns_service, "_resolve_records", lambda _hostname, _record_type: ["ns2.example.com", "ns3.example.com"])

    result = dns_service.detect_nameserver_changes("example.com", ["ns1.example.com", "ns2.example.com"])

    assert result["changed"] is True
    assert result["added_ns"] == ["ns3.example.com"]
    assert result["removed_ns"] == ["ns1.example.com"]


def test_run_dns_check_uses_previous_log_as_baseline(app, monkeypatch):
    with app.app_context():
        user = User(email="dns@example.com", password_hash="x")
        db.session.add(user)
        db.session.flush()
        site = Site(
            user_id=user.id,
            name="Example",
            url="https://example.com",
            normalized_url="https://example.com",
        )
        db.session.add(site)
        db.session.flush()
        db.session.add(DNSLog(
            site_id=site.id,
            checked_at=now_utc(),
            resolved=True,
            ip_addresses=["203.0.113.10"],
            nameservers=["ns1.example.com"],
        ))
        db.session.commit()

        monkeypatch.setattr(dns_service, "resolve_dns", lambda _hostname: {
            "resolved": True,
            "resolution_time_ms": 12.5,
            "ip_addresses": ["203.0.113.11"],
            "nameservers": ["ns2.example.com"],
            "mx_records": [],
            "error": None,
        })

        result = dns_service.run_dns_check(site)

        assert result["hostname"] == "example.com"
        assert result["hijack_suspected"] is True
        assert result["new_ips"] == ["203.0.113.11"]
        assert result["removed_ips"] == ["203.0.113.10"]
        assert result["ns_changed"] is True
        assert result["added_ns"] == ["ns2.example.com"]
        assert result["removed_ns"] == ["ns1.example.com"]


def test_dns_monitoring_defaults_seed_legacy_sites(app):
    with app.app_context():
        user = User(email="legacy-dns@example.com", password_hash="x")
        db.session.add(user)
        db.session.flush()
        site = Site(
            user_id=user.id,
            name="Legacy DNS",
            url="https://example.org",
            normalized_url="https://example.org",
            dns_status=None,
            next_dns_check_at=None,
        )
        db.session.add(site)
        db.session.commit()

        updated = ensure_dns_monitoring_defaults([site])

        assert updated == 1
        assert site.dns_status == "pending"
        assert site.next_dns_check_at is not None
        assert site.id in get_due_site_ids(CHECK_DNS)
