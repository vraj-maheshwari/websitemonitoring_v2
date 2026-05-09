"""
models/site.py
--------------
Represents a website being monitored. 
Upgraded for SaaS processing logic.
"""

from datetime import timedelta
from app.extensions import db
from app.utils.time import now_utc


class Site(db.Model):
    __tablename__ = "sites"
    __table_args__ = (
        db.Index("ix_sites_next_check_at", "next_check_at"),
        db.Index("ix_sites_current_status", "current_status"),
        db.UniqueConstraint("user_id", "normalized_url", name="uq_sites_user_normalized_url"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=True)
    url = db.Column(db.String(2048), nullable=False)
    normalized_url = db.Column(db.String(2048), nullable=False, index=True)
    check_interval = db.Column(db.Integer, default=60, nullable=False)
    uptime_check_interval = db.Column(db.Integer, default=60, nullable=False)
    ssl_check_interval = db.Column(db.Integer, default=86400, nullable=False)
    seo_check_interval = db.Column(db.Integer, default=604800, nullable=False)
    security_check_interval = db.Column(db.Integer, default=86400, nullable=False)  # Daily
    dns_check_interval = db.Column(db.Integer, default=3600, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False, index=True)

    # Check timestamps
    last_uptime_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_ssl_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_seo_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_security_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_dns_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_uptime_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_ssl_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_seo_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_security_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_dns_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_check_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # SaaS State Management
    app_status = db.Column(db.String(32), nullable=False, default="pending") 
    is_processing = db.Column(db.Boolean, nullable=False, default=False)
    last_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    uptime_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ssl_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    seo_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    security_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    dns_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Granular Statuses (pending, running, done, failed)
    uptime_status = db.Column(db.String(32), nullable=False, default="pending")
    ssl_status = db.Column(db.String(32), nullable=False, default="pending")
    seo_status = db.Column(db.String(32), nullable=False, default="pending")
    security_status = db.Column(db.String(32), nullable=False, default="pending")
    dns_status = db.Column(db.String(32), nullable=True, default="pending")

    # Uptime Metrics
    current_status = db.Column(db.String(32), nullable=False, default="PENDING")
    last_status_code = db.Column(db.Integer, nullable=True)
    last_response_time = db.Column(db.Float, nullable=True)
    last_ttfb = db.Column(db.Float, nullable=True)
    last_error_message = db.Column(db.Text, nullable=True)
    incident_opened_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_incident_resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # SSL Metrics
    ssl_state = db.Column(db.String(32), nullable=False, default="UNKNOWN")
    ssl_issuer = db.Column(db.String(512), nullable=True)
    ssl_expiry_date = db.Column(db.DateTime(timezone=True), nullable=True)
    ssl_days_remaining = db.Column(db.Integer, nullable=True)
    ssl_last_error = db.Column(db.Text, nullable=True)

    # SEO Metrics
    seo_state = db.Column(db.String(32), nullable=False, default="UNKNOWN")
    seo_score = db.Column(db.Integer, nullable=False, default=0)
    seo_last_error = db.Column(db.Text, nullable=True)
    last_seo_fetch_valid = db.Column(db.Boolean, default=True)
    last_downtime_ended_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Security Metrics
    security_score = db.Column(db.Integer, nullable=False, default=0)
    security_grade = db.Column(db.String(2), nullable=True)
    security_last_error = db.Column(db.Text, nullable=True)

    # DNS Metrics
    dns_resolved = db.Column(db.Boolean, nullable=True)
    dns_resolution_time_ms = db.Column(db.Float, nullable=True)
    dns_last_ips = db.Column(db.JSON, nullable=True)
    dns_last_ns = db.Column(db.JSON, nullable=True)
    dns_hijack_suspected = db.Column(db.Boolean, default=False, nullable=True)
    dns_ns_changed = db.Column(db.Boolean, default=False, nullable=True)
    dns_last_error = db.Column(db.String(500), nullable=True)

    # ── Denormalized CWV (from latest successful Playwright audit) ─
    lh_performance_score = db.Column(db.Integer, nullable=True)
    lh_lcp_ms            = db.Column(db.Float,   nullable=True)
    lh_tbt_ms            = db.Column(db.Float,   nullable=True)
    lh_fcp_ms            = db.Column(db.Float,   nullable=True)
    lh_cls               = db.Column(db.Float,   nullable=True)

    # Relationships
    uptime_logs = db.relationship("UptimeLog", backref="site", lazy="dynamic", cascade="all, delete-orphan")
    ssl_logs = db.relationship("SSLLog", backref="site", lazy="dynamic", cascade="all, delete-orphan")
    seo_logs = db.relationship("SEOLog", backref="site", lazy="dynamic", cascade="all, delete-orphan")
    dns_logs = db.relationship("DNSLog", backref="site", lazy="dynamic", cascade="all, delete-orphan")
    incidents = db.relationship("Incident", backref="site", lazy="dynamic", cascade="all, delete-orphan")
    alert_history = db.relationship("AlertHistory", backref="site", lazy="dynamic", cascade="all, delete-orphan")
    daily_summaries = db.relationship("DailyUptimeSummary", backref="site", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def security_headers(self) -> dict:
        from app.models.seo_log import SEOLog
        log = SEOLog.query.filter_by(site_id=self.id).order_by(SEOLog.checked_at.desc()).first()
        return log.security_headers if log else {}

    def display_name(self) -> str:
        return self.name or self.url

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "app_status": self.app_status,
            "uptime_status": self.uptime_status,
            "ssl_status": self.ssl_status,
            "seo_status": self.seo_status,
            "current_status": self.current_status,
            "last_status_code": self.last_status_code,
            "last_response_time": self.last_response_time,
            "last_ttfb": self.last_ttfb,
            "ssl_state": self.ssl_state,
            "ssl_issuer": self.ssl_issuer,
            "ssl_days_remaining": self.ssl_days_remaining,
            "ssl_expiry_date": self.ssl_expiry_date.isoformat() if self.ssl_expiry_date else None,
            "seo_state": self.seo_state,
            "seo_score": self.seo_score,
            "last_seo_fetch_valid": self.last_seo_fetch_valid,
            "security_score": self.security_score,
            "security_grade": self.security_grade,
            "security_headers": self.security_headers,
            "dns_resolved": self.dns_resolved,
            "dns_resolution_time_ms": self.dns_resolution_time_ms,
            "dns_last_ips": self.dns_last_ips or [],
            "dns_last_ns": self.dns_last_ns or [],
            "dns_hijack_suspected": self.dns_hijack_suspected,
            "dns_ns_changed": self.dns_ns_changed,
            "dns_status": self.dns_status,
            "dns_last_error": self.dns_last_error,
            "lighthouse": {
                "performance_score": self.lh_performance_score,
                "lcp_ms": self.lh_lcp_ms,
                "tbt_ms": self.lh_tbt_ms,
                "fcp_ms": self.lh_fcp_ms,
                "cls": self.lh_cls,
                "has_data": self.lh_performance_score is not None,
            },
            "last_uptime_check_at": self.last_uptime_check_at.isoformat() + "Z" if self.last_uptime_check_at else None,
            "last_ssl_check_at": self.last_ssl_check_at.isoformat() + "Z" if self.last_ssl_check_at else None,
            "last_seo_check_at": self.last_seo_check_at.isoformat() + "Z" if self.last_seo_check_at else None,
            "last_security_check_at": self.last_security_check_at.isoformat() + "Z" if self.last_security_check_at else None,
            "last_dns_check_at": self.last_dns_check_at.isoformat() + "Z" if self.last_dns_check_at else None,
            "next_check_at": self.next_check_at.isoformat() if self.next_check_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def refresh_app_status(self):
        statuses = [self.uptime_status, self.ssl_status, self.seo_status, self.security_status, self.dns_status]

        self.is_processing = any(s == "running" for s in statuses)

        # Guard: all pending means the site was just created — keep it "pending",
        # not "partial", so the UI doesn't show a warning state during init.
        if all(s == "pending" for s in statuses):
            self.app_status = "pending"
            return

        if any(s in ["running", "queued"] for s in statuses):
            self.app_status = "checking"
        elif all(s == "done" for s in statuses):
            self.app_status = "ready"
        elif any(s == "failed" for s in statuses):
            self.app_status = "partial"
        elif any(s == "pending" for s in statuses):
            # Some checks completed, others still pending - site is initializing
            self.app_status = "initializing"
        else:
            self.app_status = "partial"

    @classmethod
    def rescue_stuck_tasks(cls):
        now = now_utc()
        rescued = 0
        checks = (
            ("uptime", cls.uptime_status, cls.uptime_started_at, now - timedelta(minutes=10)),
            ("ssl", cls.ssl_status, cls.ssl_started_at, now - timedelta(minutes=30)),
            ("seo", cls.seo_status, cls.seo_started_at, now - timedelta(minutes=90)),
            ("security", cls.security_status, cls.security_started_at, now - timedelta(minutes=30)),
            ("dns", cls.dns_status, cls.dns_started_at, now - timedelta(minutes=10)),
        )

        for check_type, status_field, started_field, cutoff in checks:
            stuck = cls.query.filter(status_field == "running", started_field < cutoff).all()
            for site in stuck:
                setattr(site, f"{check_type}_status", "failed")
                setattr(site, f"{check_type}_started_at", None)
                site.refresh_app_status()
                rescued += 1

        return rescued

    def __repr__(self) -> str:
        return f"<Site id={self.id} url={self.url} app_status={self.app_status}>"
