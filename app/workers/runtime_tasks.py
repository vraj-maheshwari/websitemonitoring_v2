from celery import Celery

from app import create_app
from app.config.settings import Config
from app.services.monitor_service import run_uptime_check as run_uptime_service
from app.services.monitoring_service import CHECK_SEO, CHECK_SSL, CHECK_UPTIME, get_due_site_ids
from app.services.retention_service import run_retention_cycle as run_retention_service
from app.services.seo_service import run_seo_check as run_seo_service
from app.services.ssl_service import run_ssl_check as run_ssl_service

celery = Celery("tasks", broker=Config.CELERY_BROKER_URL, backend=Config.CELERY_RESULT_BACKEND)
celery.conf.update(
    beat_schedule=Config.CELERY_BEAT_SCHEDULE,
    timezone=Config.CELERY_TIMEZONE,
)


@celery.task(name="tasks.run_uptime_check")
def run_uptime_check_task(site_id: int):
    with create_app().app_context():
        log = run_uptime_service(site_id)
        return log.to_dict() if log else "Site not found"


@celery.task(name="tasks.run_ssl_check")
def run_ssl_check_task(site_id: int):
    with create_app().app_context():
        log = run_ssl_service(site_id)
        return log.to_dict() if log else "Site not found"


@celery.task(name="tasks.run_seo_check")
def run_seo_check_task(site_id: int):
    with create_app().app_context():
        log = run_seo_service(site_id)
        return log.to_dict() if log else "Site not found"


@celery.task(name="tasks.dispatch_due_checks")
def dispatch_due_checks():
    with create_app().app_context():
        return {
            CHECK_UPTIME: _dispatch_for_type(CHECK_UPTIME, run_uptime_check_task),
            CHECK_SSL: _dispatch_for_type(CHECK_SSL, run_ssl_check_task),
            CHECK_SEO: _dispatch_for_type(CHECK_SEO, run_seo_check_task),
        }


@celery.task(name="tasks.run_retention_cycle")
def run_retention_cycle_task():
    with create_app().app_context():
        return run_retention_service()


def _dispatch_for_type(check_type: str, task) -> int:
    site_ids = get_due_site_ids(check_type)
    for site_id in site_ids:
        task.delay(site_id)
    return len(site_ids)
