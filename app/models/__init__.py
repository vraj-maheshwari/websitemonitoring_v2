from app.extensions import db

from .alert_history import AlertHistory
from .daily_seo_summary import DailySEOSummary
from .daily_ssl_summary import DailySSLSummary
from .daily_uptime_summary import DailyUptimeSummary
from .incident import Incident
from .seo_log import SEOLog
from .site import Site
from .site_notification import SiteNotification
from .ssl_log import SSLLog
from .uptime_log import UptimeLog
from .user import User

__all__ = [
    "db",
    "AlertHistory",
    "DailySEOSummary",
    "DailySSLSummary",
    "DailyUptimeSummary",
    "Incident",
    "SEOLog",
    "Site",
    "SiteNotification",
    "SSLLog",
    "UptimeLog",
    "User",
]
