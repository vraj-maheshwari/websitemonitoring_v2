from app.extensions import db


class DailySSLSummary(db.Model):
    __tablename__ = "daily_ssl_summaries"
    __table_args__ = (
        db.UniqueConstraint("site_id", "summary_date", name="uq_daily_ssl_summary"),
    )

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    summary_date = db.Column(db.Date, nullable=False, index=True)
    
    # Aggregates
    total_checks = db.Column(db.Integer, nullable=False, default=0)
    valid_count = db.Column(db.Integer, nullable=False, default=0)
    avg_days_remaining = db.Column(db.Float, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "summary_date": self.summary_date.isoformat(),
            "total_checks": self.total_checks,
            "valid_count": self.valid_count,
            "avg_days_remaining": self.avg_days_remaining,
        }
