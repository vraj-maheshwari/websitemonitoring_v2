"""
config/settings.py
------------------
Central configuration loaded from environment variables.
All services import from here — never hardcode credentials.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///website_monitor.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Redis / Celery
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_SERIALIZER = "json"
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_TIMEZONE = "UTC"
    CELERY_BEAT_SCHEDULE = {
        "run-due-checks-every-30-seconds": {
            "task": "tasks.dispatch_due_checks",
            "schedule": 30.0,
        },
        "run-zombie-rescue-every-5-minutes": {
            "task": "tasks.run_zombie_rescue",
            "schedule": 300.0,
        },
        "run-daily-uptime-summary": {
            "task": "tasks.run_daily_summary",
            "schedule": 86400.0,
        },
        "run-log-retention-nightly": {
            "task": "tasks.run_retention_cycle",
            "schedule": 86400.0,
        },
    }

    # Monitoring
    RESPONSE_TIME_THRESHOLD = float(os.getenv("RESPONSE_TIME_THRESHOLD", "3.0"))
    SSL_EXPIRY_WARNING_DAYS = int(os.getenv("SSL_EXPIRY_WARNING_DAYS", "7"))
    SSL_CHECK_INTERVAL_SECONDS = int(os.getenv("SSL_CHECK_INTERVAL_SECONDS", "21600"))
    SEO_CHECK_INTERVAL_SECONDS = int(os.getenv("SEO_CHECK_INTERVAL_SECONDS", "21600"))
    ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "15"))
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))

    # HTTP
    HTTP_TIMEOUT = 10
    HTTP_USER_AGENT = "WebsiteMonitor/1.0"
    HTTP_VERIFY_SSL = os.getenv("HTTP_VERIFY_SSL", "true").lower() == "true"

    # Alerts
    ALERT_EMAIL = os.getenv("ALERT_EMAIL", "admin@example.com")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", ALERT_EMAIL)

    # Retry logic
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
