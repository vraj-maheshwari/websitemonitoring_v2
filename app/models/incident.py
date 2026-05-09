from datetime import datetime
from app.extensions import db
from app.utils.time import now_utc


class Incident(db.Model):
    __tablename__ = "incidents"
    __table_args__ = (
        db.Index("ix_incidents_site_resolved", "site_id", "resolved_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="OPEN")
    opened_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    opened_status_code = db.Column(db.Integer, nullable=True)
    opened_response_time = db.Column(db.Float, nullable=True)
    opened_error_message = db.Column(db.Text, nullable=True)
    resolved_status_code = db.Column(db.Integer, nullable=True)
    resolved_response_time = db.Column(db.Float, nullable=True)
    resolved_error_message = db.Column(db.Text, nullable=True)

    # RCA + Timeline
    root_cause = db.Column(db.String(32), nullable=True)   # TIMEOUT|DNS|SERVER|CLIENT|UNKNOWN
    timeline   = db.Column(db.JSON, nullable=True)          # list of event dicts

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "status": self.status,
            "opened_at": self.opened_at.isoformat() + "Z",
            "resolved_at": self.resolved_at.isoformat() + "Z" if self.resolved_at else None,
            "opened_status_code": self.opened_status_code,
            "opened_response_time": self.opened_response_time,
            "opened_error_message": self.opened_error_message,
            "resolved_status_code": self.resolved_status_code,
            "resolved_response_time": self.resolved_response_time,
            "resolved_error_message": self.resolved_error_message,
            "root_cause": self.root_cause,
            "timeline": self.timeline or [],
        }
