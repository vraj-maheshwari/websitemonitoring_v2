from app.extensions import db
from app.utils.time import now_utc


class DNSLog(db.Model):
    __tablename__ = "dns_logs"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    checked_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    resolved = db.Column(db.Boolean)
    resolution_time_ms = db.Column(db.Float)
    ip_addresses = db.Column(db.JSON)
    nameservers = db.Column(db.JSON)
    mx_records = db.Column(db.JSON)
    hijack_suspected = db.Column(db.Boolean, default=False)
    new_ips = db.Column(db.JSON)
    removed_ips = db.Column(db.JSON)
    ns_changed = db.Column(db.Boolean, default=False)
    added_ns = db.Column(db.JSON)
    removed_ns = db.Column(db.JSON)
    error_message = db.Column(db.Text)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "resolved": self.resolved,
            "resolution_time_ms": self.resolution_time_ms,
            "ip_addresses": self.ip_addresses or [],
            "nameservers": self.nameservers or [],
            "mx_records": self.mx_records or [],
            "hijack_suspected": self.hijack_suspected,
            "new_ips": self.new_ips or [],
            "removed_ips": self.removed_ips or [],
            "ns_changed": self.ns_changed,
            "added_ns": self.added_ns or [],
            "removed_ns": self.removed_ns or [],
            "error_message": self.error_message,
        }
