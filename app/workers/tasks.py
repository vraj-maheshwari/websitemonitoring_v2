"""Legacy task module shim.

This file keeps the historical import path stable while delegating all active
Celery tasks to app.workers.runtime_tasks.
"""

from celery import Celery
from app import create_app
from app.config.settings import Config
from app.services.monitor_service import run_uptime_check as run_uptime_service
from app.services.seo_service import run_seo_check as run_seo_service

celery = Celery(
    "tasks",
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND
)
@celery.task
def run_uptime_check(site_id):
    app = create_app()

    with app.app_context():
        log = run_uptime_service(site_id)

        if log is None:
            return "Site not found"

        return log.to_dict()

        """Legacy inline implementation replaced by service-based task.
        log = UptimeLog(
            site_id=site.id,
            status_code=status_code,   # ✅ FIX
            response_time=response_time,
            is_up=is_up,               # ✅ ADD
            error_message=error_message
        )

        db.session.add(log)
        db.session.commit()

        return {
            "site": site.url,
            "status_code": status_code,
            "response_time": response_time,
            "is_up": is_up
        }
        """


@celery.task(name="tasks.run_seo_check")
def run_seo_check_task(site_id):
    app = create_app()

    with app.app_context():
        log = run_seo_service(site_id)
        if log is None:
            return "Site not found"
        return log.to_dict()


from app.workers.runtime_tasks import (  # noqa: E402
    celery,
    dispatch_due_checks,
    run_retention_cycle_task,
    run_seo_check_task,
    run_ssl_check_task,
    run_uptime_check_task,
)
