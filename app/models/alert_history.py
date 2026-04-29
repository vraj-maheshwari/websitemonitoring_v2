from datetime import datetime
from app.extensions import db
from app.utils.time import now_utc


class AlertHistory(db.Model):
    __tablename__ = "alert_history"
    __table_args__ = (
        db.Index("ix_alert_history_site_event", "site_id", "event_type", "sent_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id", ondelete="SET NULL"),
                            nullable=True, index=True)
    event_type = db.Column(db.String(32), nullable=False)
    recipient = db.Column(db.String(320), nullable=False)
    subject = db.Column(db.String(512), nullable=False)
    body = db.Column(db.Text, nullable=False)
    delivery_status = db.Column(db.String(32), nullable=False, default="PENDING")
    error_message = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    incident = db.relationship("Incident", backref=db.backref("alert_history", lazy="dynamic"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "incident_id": self.incident_id,
            "event_type": self.event_type,
            "recipient": self.recipient,
            "subject": self.subject,
            "delivery_status": self.delivery_status,
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat(),
        }
