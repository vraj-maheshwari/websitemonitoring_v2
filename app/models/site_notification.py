from app.extensions import db


class SiteNotification(db.Model):
    __tablename__ = "site_notifications"
    __table_args__ = (
        db.UniqueConstraint("site_id", "email", name="uq_site_notification_site_email"),
    )

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    email = db.Column(db.String(320), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "email": self.email,
            "is_active": self.is_active,
        }
