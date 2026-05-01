"""
config/settings.py
------------------
Central configuration loaded from environment variables.
All services import from here — never hardcode credentials.
"""
import os
from dotenv import load_dotenv
from celery.schedules import crontab

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

    # Windows: prefork pool (billiard) crashes — use solo instead.
    # On Linux/Mac prefork is used for true parallelism.
    CELERY_WORKER_POOL = "solo" if os.name == "nt" else "prefork"
    CELERY_WORKER_CONCURRENCY = 1 if os.name == "nt" else None

    # Suppress Celery 6.0 deprecation warning about broker retry on startup
    BROKER_CONNECTION_RETRY_ON_STARTUP = True

    CELERY_BEAT_SCHEDULE = {
        "run-due-uptime-checks": {
            "task": "tasks.run_due_uptime_checks",
            "schedule": 30.0,
        },
        "run-due-ssl-checks": {
            "task": "tasks.run_due_ssl_checks",
            "schedule": crontab(minute=0),
        },
        "run-due-seo-checks": {
            "task": "tasks.run_due_seo_checks",
            "schedule": crontab(minute=5),
        },
        "run-zombie-rescue": {
            "task": "tasks.run_zombie_rescue",
            "schedule": 300.0,
        },
        "run-daily-summary": {
            "task": "tasks.run_daily_summary",
            "schedule": crontab(hour=0, minute=5),
        },
        "run-data-retention": {
            "task": "tasks.run_retention_cycle",
            "schedule": crontab(hour=3, minute=0),
        },
    }

    # Monitoring
    RESPONSE_TIME_THRESHOLD = float(os.getenv("RESPONSE_TIME_THRESHOLD", "3.0"))
    SSL_EXPIRY_WARNING_DAYS = int(os.getenv("SSL_EXPIRY_WARNING_DAYS", "7"))
    SSL_CHECK_INTERVAL_SECONDS = int(os.getenv("SSL_CHECK_INTERVAL_SECONDS", "21600"))
    SEO_CHECK_INTERVAL_SECONDS = int(os.getenv("SEO_CHECK_INTERVAL_SECONDS", "21600"))
    ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "15"))
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
    LIGHTHOUSE_ENABLED = os.environ.get("LIGHTHOUSE_ENABLED", "true").strip().lower() == "true"

    # HTTP
    HTTP_TIMEOUT = 10
    HTTP_USER_AGENT = "WebsiteMonitor/1.0"
    HTTP_VERIFY_SSL = os.getenv("HTTP_VERIFY_SSL", "true").lower() == "true"

    # Alerts
    TEAMS_WEBHOOK_URL = os.getenv(
        "TEAMS_WEBHOOK_URL",
        "https://default7fb910a1b6dd4dfcb4b7f2f8393b00.24.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/f84a9e052f3344329e1b85f94fd30958/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=i7KVeG5N23_dKBTtNdB4RBmIqxMZ75apanok5PvSjTg",
    )

    # Retry logic
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
