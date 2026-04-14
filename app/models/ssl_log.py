"""
models/ssl_log.py
-----------------
Stores SSL certificate check results.
"""

from datetime import datetime
from app.extensions import db


class SSLLog(db.Model):
    __tablename__ = "ssl_logs"
    __table_args__ = (
        db.Index("ix_ssl_logs_site_checked_at", "site_id", "checked_at"),
    )

    id            = db.Column(db.Integer, primary_key=True)
    site_id       = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    expiry_date   = db.Column(db.DateTime, nullable=True)
    days_remaining= db.Column(db.Integer,  nullable=True)
    is_valid      = db.Column(db.Boolean,  nullable=False, default=False)
    issuer        = db.Column(db.String(512), nullable=True)
    error_message = db.Column(db.Text,     nullable=True)
    checked_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False,
                              index=True)

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "site_id":        self.site_id,
            "expiry_date":    self.expiry_date.isoformat() if self.expiry_date else None,
            "days_remaining": self.days_remaining,
            "is_valid":       self.is_valid,
            "issuer":         self.issuer,
            "error_message":  self.error_message,
            "checked_at":     self.checked_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (f"<SSLLog site={self.site_id} valid={self.is_valid} "
                f"expires={self.expiry_date}>")
