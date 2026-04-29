from app.extensions import db


class DailySEOSummary(db.Model):
    __tablename__ = "daily_seo_summaries"
    __table_args__ = (
        db.UniqueConstraint("site_id", "summary_date", name="uq_daily_seo_summary"),
    )

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    summary_date = db.Column(db.Date, nullable=False, index=True)
    
    # Aggregates
    total_checks = db.Column(db.Integer, nullable=False, default=0)
    avg_score = db.Column(db.Float, nullable=False, default=0.0)
    min_score = db.Column(db.Integer, nullable=True)
    max_score = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "summary_date": self.summary_date.isoformat(),
            "total_checks": self.total_checks,
            "avg_score": self.avg_score,
            "min_score": self.min_score,
            "max_score": self.max_score,
        }
