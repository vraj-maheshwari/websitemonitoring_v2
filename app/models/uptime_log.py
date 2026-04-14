"""
models/uptime_log.py
--------------------
Stores results from each uptime (HTTP) check.
"""
 
from datetime import datetime
from app.extensions import db
 
 
class UptimeLog(db.Model):
    __tablename__ = "uptime_logs"
    __table_args__ = (
        db.Index("ix_uptime_logs_site_checked_at", "site_id", "checked_at"),
    )
 
    id            = db.Column(db.Integer, primary_key=True)
    site_id       = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    status_code   = db.Column(db.Integer, nullable=True)   # None if request failed
    response_time = db.Column(db.Float,   nullable=True)   # seconds
    is_up         = db.Column(db.Boolean, nullable=False, default=False)
    error_message = db.Column(db.Text,    nullable=True)   # network/timeout errors
    checked_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False,
                              index=True)
 
    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "site_id":       self.site_id,
            "status_code":   self.status_code,
            "response_time": self.response_time,
            "is_up":         self.is_up,
            "error_message": self.error_message,
            "checked_at":    self.checked_at.isoformat(),
        }
 
    def __repr__(self) -> str:
        return f"<UptimeLog site={self.site_id} status={self.status_code} up={self.is_up}>"
 
