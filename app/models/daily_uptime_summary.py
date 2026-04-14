from app.extensions import db


class DailyUptimeSummary(db.Model):
    __tablename__ = "daily_uptime_summaries"
    __table_args__ = (
        db.UniqueConstraint("site_id", "summary_date", name="uq_daily_uptime_summary"),
    )

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    summary_date = db.Column(db.Date, nullable=False, index=True)
    uptime_percentage = db.Column(db.Float, nullable=False, default=0.0)
    avg_response_time = db.Column(db.Float, nullable=True)
    outage_count = db.Column(db.Integer, nullable=False, default=0)
    total_checks = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "summary_date": self.summary_date.isoformat(),
            "uptime_percentage": self.uptime_percentage,
            "avg_response_time": self.avg_response_time,
            "outage_count": self.outage_count,
            "total_checks": self.total_checks,
        }
