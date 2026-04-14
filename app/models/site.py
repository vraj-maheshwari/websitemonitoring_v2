"""
models/site.py
--------------
Represents a website being monitored.
"""
 
from datetime import datetime
from app.extensions import db
 
 
class Site(db.Model):
    __tablename__ = "sites"
    __table_args__ = (
        db.Index("ix_sites_next_check_at", "next_check_at"),
        db.Index("ix_sites_current_status", "current_status"),
    )
 
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=True)
    url = db.Column(db.String(2048), nullable=False)
    normalized_url = db.Column(db.String(2048), nullable=False, unique=True, index=True)
    check_interval = db.Column(db.Integer, default=60, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    last_uptime_check_at = db.Column(db.DateTime, nullable=True)
    last_ssl_check_at = db.Column(db.DateTime, nullable=True)
    last_seo_check_at = db.Column(db.DateTime, nullable=True)
    next_uptime_check_at = db.Column(db.DateTime, nullable=True)
    next_ssl_check_at = db.Column(db.DateTime, nullable=True)
    next_seo_check_at = db.Column(db.DateTime, nullable=True)
    next_check_at = db.Column(db.DateTime, nullable=True)

    current_status = db.Column(db.String(32), nullable=False, default="PENDING")
    last_status_code = db.Column(db.Integer, nullable=True)
    last_response_time = db.Column(db.Float, nullable=True)
    last_error_message = db.Column(db.Text, nullable=True)
    incident_opened_at = db.Column(db.DateTime, nullable=True)
    last_incident_resolved_at = db.Column(db.DateTime, nullable=True)

    ssl_status = db.Column(db.String(32), nullable=False, default="PENDING")
    ssl_issuer = db.Column(db.String(512), nullable=True)
    ssl_expiry_date = db.Column(db.DateTime, nullable=True)
    ssl_days_remaining = db.Column(db.Integer, nullable=True)
    ssl_last_error = db.Column(db.Text, nullable=True)

    seo_status = db.Column(db.String(32), nullable=False, default="PENDING")
    seo_title = db.Column(db.String(512), nullable=True)
    seo_meta_description = db.Column(db.Text, nullable=True)
    seo_has_meta = db.Column(db.Boolean, nullable=False, default=False)
    seo_has_h1 = db.Column(db.Boolean, nullable=False, default=False)
    seo_h1_text = db.Column(db.String(512), nullable=True)
    seo_score = db.Column(db.Integer, nullable=False, default=0)
    seo_last_error = db.Column(db.Text, nullable=True)
 
    # ── Relationships (lazy="dynamic" keeps queries efficient) ─────────────
    uptime_logs = db.relationship("UptimeLog", backref="site", lazy="dynamic",
                                  cascade="all, delete-orphan")
    ssl_logs = db.relationship("SSLLog", backref="site", lazy="dynamic",
                               cascade="all, delete-orphan")
    seo_logs = db.relationship("SEOLog", backref="site", lazy="dynamic",
                               cascade="all, delete-orphan")
    incidents = db.relationship("Incident", backref="site", lazy="dynamic",
                                cascade="all, delete-orphan")
    notifications = db.relationship("SiteNotification", backref="site", lazy="dynamic",
                                    cascade="all, delete-orphan")
    alert_history = db.relationship("AlertHistory", backref="site", lazy="dynamic",
                                    cascade="all, delete-orphan")
    daily_summaries = db.relationship("DailyUptimeSummary", backref="site", lazy="dynamic",
                                      cascade="all, delete-orphan")
 
    def display_name(self) -> str:
        return self.name or self.url

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "normalized_url": self.normalized_url,
            "check_interval": self.check_interval,
            "created_at": self.created_at.isoformat(),
            "current_status": self.current_status,
            "last_status_code": self.last_status_code,
            "last_response_time": self.last_response_time,
            "last_error_message": self.last_error_message,
            "last_uptime_check_at": self.last_uptime_check_at.isoformat() if self.last_uptime_check_at else None,
            "last_ssl_check_at": self.last_ssl_check_at.isoformat() if self.last_ssl_check_at else None,
            "last_seo_check_at": self.last_seo_check_at.isoformat() if self.last_seo_check_at else None,
            "next_check_at": self.next_check_at.isoformat() if self.next_check_at else None,
            "incident_opened_at": self.incident_opened_at.isoformat() if self.incident_opened_at else None,
            "last_incident_resolved_at": self.last_incident_resolved_at.isoformat() if self.last_incident_resolved_at else None,
            "ssl_status": self.ssl_status,
            "ssl_days_remaining": self.ssl_days_remaining,
            "seo_status": self.seo_status,
            "seo_score": self.seo_score,
        }

    def __repr__(self) -> str:
        return f"<Site id={self.id} url={self.url} status={self.current_status}>"
