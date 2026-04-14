"""
models/seo_log.py
-----------------
Stores basic SEO audit results for a site.
"""

from datetime import datetime
from app.extensions import db


class SEOLog(db.Model):
    __tablename__ = "seo_logs"
    __table_args__ = (
        db.Index("ix_seo_logs_site_checked_at", "site_id", "checked_at"),
    )

    id               = db.Column(db.Integer, primary_key=True)
    site_id          = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    title            = db.Column(db.String(512), nullable=True)
    meta_description = db.Column(db.Text,    nullable=True)
    has_meta         = db.Column(db.Boolean, nullable=False, default=False)
    has_h1           = db.Column(db.Boolean, nullable=False, default=False)
    h1_text          = db.Column(db.String(512), nullable=True)
    error_message    = db.Column(db.Text,    nullable=True)
    checked_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False,
                                 index=True)

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "site_id":          self.site_id,
            "title":            self.title,
            "meta_description": self.meta_description,
            "has_meta":         self.has_meta,
            "has_h1":           self.has_h1,
            "h1_text":          self.h1_text,
            "error_message":    self.error_message,
            "checked_at":       self.checked_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (f"<SEOLog site={self.site_id} has_title={bool(self.title)} "
                f"has_meta={self.has_meta} has_h1={self.has_h1}>")
