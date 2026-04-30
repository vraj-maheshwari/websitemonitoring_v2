"""
models/seo_log.py
-----------------
Stores comprehensive SaaS-grade SEO audit results.
"""

from app.extensions import db
from app.utils.time import now_utc


class SEOLog(db.Model):
    __tablename__ = "seo_logs"
    __table_args__ = (
        db.Index("ix_seo_logs_site_checked_at", "site_id", "checked_at"),
        db.Index("ix_seo_logs_status", "status"),
        db.Index("ix_seo_logs_score", "score"),
    )

    id               = db.Column(db.Integer, primary_key=True)
    site_id          = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                                 nullable=False, index=True)

    # Core Metrics
    score            = db.Column(db.Integer, nullable=True)
    status           = db.Column(db.String(32), nullable=False, default="UNKNOWN")

    # 1. On-Page Signals
    title            = db.Column(db.String(512), nullable=False, default="")
    title_length     = db.Column(db.Integer, nullable=False, default=0)
    meta_description = db.Column(db.Text,    nullable=False, default="")
    meta_length      = db.Column(db.Integer, nullable=False, default=0)
    h1_list          = db.Column(db.JSON,    nullable=True)
    h1_count         = db.Column(db.Integer, nullable=False, default=0)
    h2_count         = db.Column(db.Integer, nullable=False, default=0)
    h3_count         = db.Column(db.Integer, nullable=False, default=0)
    word_count       = db.Column(db.Integer, nullable=False, default=0)
    keyword_density  = db.Column(db.JSON,    nullable=True) # Top keywords list

    # 2. Content Signals
    image_count      = db.Column(db.Integer, nullable=False, default=0)
    missing_alt_count= db.Column(db.Integer, nullable=False, default=0)
    internal_link_count = db.Column(db.Integer, nullable=False, default=0)
    external_link_count = db.Column(db.Integer, nullable=False, default=0)

    # 3. Technical Signals
    has_robots       = db.Column(db.Boolean, nullable=False, default=False)
    has_sitemap      = db.Column(db.Boolean, nullable=False, default=False)
    canonical        = db.Column(db.String(2048), nullable=False, default="")
    has_favicon      = db.Column(db.Boolean, nullable=False, default=False)
    has_hreflang     = db.Column(db.Boolean, nullable=False, default=False)
    robots_meta      = db.Column(db.String(255),  nullable=False, default="")
    html_lang        = db.Column(db.String(32),   nullable=False, default="")

    # 4. Performance Signals
    page_size_kb     = db.Column(db.Float,   nullable=False, default=0.0)
    js_blocking_count= db.Column(db.Integer, nullable=False, default=0)
    css_blocking_count=db.Column(db.Integer, nullable=False, default=0)
    ttfb             = db.Column(db.Float,   nullable=True)

    # 5. Mobile Signals
    has_viewport     = db.Column(db.Boolean, nullable=False, default=False)
    mobile_friendly  = db.Column(db.Boolean, nullable=False, default=False)

    # 6. Security Signals
    https_redirect   = db.Column(db.Boolean, nullable=False, default=False)
    mixed_content_count = db.Column(db.Integer, nullable=False, default=0)

    # Intelligence Outputs
    score_breakdown  = db.Column(db.JSON,    nullable=True)  # dict by category
    issues           = db.Column(db.JSON,    nullable=True)  # list of strings
    recommendations  = db.Column(db.JSON,    nullable=True)  # list of strings
    signals          = db.Column(db.JSON,    nullable=True)
    error_message    = db.Column(db.Text,    nullable=True)

    checked_at       = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False,
                                 index=True)

    fetch_valid = db.Column(db.Boolean, default=True)
    fetch_html_preview = db.Column(db.Text, nullable=True)
    fetch_page_size_kb = db.Column(db.Float, nullable=True)
    fetch_status = db.Column(db.String(20), default='ok')
    invalidation_reason = db.Column(db.Text, nullable=True)

    # Hybrid fetch metadata
    render_mode   = db.Column(db.String(32), nullable=True, default="HTTP")
    used_fallback = db.Column(db.Boolean,    nullable=False, default=False)
    fallback_reason = db.Column(db.Text,     nullable=True)

    # Core Web Vitals (server-side proxy estimates)
    cwv_lcp_estimate_s  = db.Column(db.Float,   nullable=True)
    cwv_lcp_rating      = db.Column(db.String(20), nullable=True)
    cwv_fid_estimate_ms = db.Column(db.Float,   nullable=True)
    cwv_fid_rating      = db.Column(db.String(20), nullable=True)
    cwv_cls_estimate    = db.Column(db.Float,   nullable=True)
    cwv_cls_rating      = db.Column(db.String(20), nullable=True)
    cwv_data            = db.Column(db.JSON,    nullable=True)  # full CWVEstimate dict

    # Technology profiler
    tech_stack          = db.Column(db.JSON,    nullable=True)  # detect_technologies() result
    tech_flat           = db.Column(db.JSON,    nullable=True)  # flat list of tech names
    tech_diff           = db.Column(db.JSON,    nullable=True)  # {added, removed, unchanged}

    # Broken link checker
    broken_links        = db.Column(db.JSON,    nullable=True)  # broken_link_report_to_dict()
    broken_link_count   = db.Column(db.Integer, nullable=False, default=0)
    links_checked       = db.Column(db.Integer, nullable=False, default=0)

    # Security audit
    security_score   = db.Column(db.Integer, nullable=True)
    security_headers = db.Column(db.JSON,    nullable=True)  # {header_name: bool}
    security_issues  = db.Column(db.JSON,    nullable=True)  # list of issue strings
    malware_flags    = db.Column(db.JSON,    nullable=True)  # list of matched signatures

    def to_dict(self) -> dict:
        return {
            "id":                self.id,
            "site_id":           self.site_id,
            "score":             self.score,
            "status":            self.status,
            "title":             self.title,
            "title_length":      self.title_length,
            "meta_description":  self.meta_description,
            "meta_length":       self.meta_length,
            "h1_count":          self.h1_count,
            "h2_count":          self.h2_count,
            "h3_count":          self.h3_count,
            "word_count":        self.word_count,
            "image_count":       self.image_count,
            "missing_alt_count": self.missing_alt_count,
            "internal_link_count": self.internal_link_count,
            "external_link_count": self.external_link_count,
            "has_robots":        self.has_robots,
            "has_sitemap":       self.has_sitemap,
            "page_size_kb":      self.page_size_kb,
            "ttfb":              self.ttfb,
            "mobile_friendly":   self.mobile_friendly,
            "https_redirect":    self.https_redirect,
            "mixed_content_count": self.mixed_content_count,
            "score_breakdown":   (self.score_breakdown or {}) if self.fetch_valid else None,
            "issues":            (self.issues or []) if self.fetch_valid else [],
            "recommendations":   (self.recommendations or []) if self.fetch_valid else [],
            "signals":           (self.signals or {}) if self.fetch_valid else {},
            "checked_at":        self.checked_at.isoformat(),
            "fetch_valid":       self.fetch_valid,
            "fetch_html_preview": self.fetch_html_preview,
            "fetch_page_size_kb": self.fetch_page_size_kb,
            "fetch_status":      self.fetch_status,
            "invalidation_reason": self.invalidation_reason,
            "error_message":     self.error_message,
            "render_mode":       self.render_mode or "HTTP",
            "used_fallback":     self.used_fallback or False,
            "fallback_reason":   self.fallback_reason,
            # Core Web Vitals estimates
            "cwv": self.cwv_data or {},
            # Technology stack
            "tech_stack": self.tech_stack or {},
            "tech_flat":  self.tech_flat or [],
            "tech_diff":  self.tech_diff or {},
            # Broken links
            "broken_links":      self.broken_links or {},
            "broken_link_count": self.broken_link_count,
            "links_checked":     self.links_checked,
            # Security
            "security_score":   self.security_score,
            "security_headers": self.security_headers or {},
            "security_issues":  self.security_issues or [],
            "malware_flags":    self.malware_flags or [],
        }

    def __repr__(self) -> str:
        return f"<SEOLog site={self.site_id} score={self.score}>"
