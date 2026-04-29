from celery import Celery
from app import create_app
from app.config.settings import Config
from app.extensions import db
from app.models.site import Site
from app.services.monitor_service import run_uptime_check as run_uptime_service
from app.services.monitoring_service import CHECK_SEO, CHECK_SSL, CHECK_UPTIME, get_due_site_ids
from app.services.retention_service import run_retention_cycle as run_retention_service
from app.services.seo_service import run_seo_check as run_seo_service
from app.services.summary_service import run_daily_summary as run_daily_summary_service
from app.services.ssl_service import run_ssl_check as run_ssl_service
from app.utils.time import now_utc

# Initialize Celery
celery = Celery("tasks", broker=Config.CELERY_BROKER_URL, backend=Config.CELERY_RESULT_BACKEND)
celery.conf.update(
    beat_schedule=Config.CELERY_BEAT_SCHEDULE,
    timezone=Config.CELERY_TIMEZONE,
    broker_connection_timeout=1,
    broker_transport_options={"max_retries": 0, "socket_connect_timeout": 1},
    task_publish_retry=False,
)

def acquire_check_lock(site_id: int, check_type: str) -> bool:
    status_field = getattr(Site, f"{check_type}_status")
    started_name = f"{check_type}_started_at"
    updated = (
        Site.query
        .filter(Site.id == site_id, status_field != "running")
        .update({
            f"{check_type}_status": "running",
            started_name: now_utc(),
            Site.last_started_at: now_utc(),
            Site.app_status: "checking",
            Site.is_processing: True,
        }, synchronize_session=False)
    )
    db.session.commit()
    return updated == 1


def release_check_lock(site: Site, check_type: str) -> None:
    setattr(site, f"{check_type}_started_at", None)
    site.refresh_app_status()
    db.session.commit()


@celery.task(name="tasks.run_uptime_check", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_uptime_check_task(site_id: int):
    app = create_app()
    with app.app_context():
        site = db.session.get(Site, site_id)
        if not site: return "Site not found"
        if not acquire_check_lock(site_id, "uptime"):
            return "Already running"
        
        try:
            run_uptime_service(site_id)
        except Exception:
            db.session.rollback()
            site = db.session.get(Site, site_id)
            site.uptime_status = "failed"
            site.refresh_app_status()
            db.session.commit()
            raise
        finally:
            db.session.refresh(site)
            if site.uptime_status == "running":
                site.uptime_status = "failed"
            release_check_lock(site, "uptime")
    return "OK"

@celery.task(name="tasks.run_ssl_check", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_ssl_check_task(site_id: int):
    app = create_app()
    with app.app_context():
        site = db.session.get(Site, site_id)
        if not site: return "Site not found"

        if not acquire_check_lock(site_id, "ssl"):
            return "Already running"

        try:
            run_ssl_service(site_id)
        except Exception:
            db.session.rollback()
            site = db.session.get(Site, site_id)
            site.ssl_status = "failed"
            site.refresh_app_status()
            db.session.commit()
            raise
        finally:
            db.session.refresh(site)
            if site.ssl_status == "running":
                site.ssl_status = "failed"
            release_check_lock(site, "ssl")
    return "OK"

@celery.task(name="tasks.run_seo_check", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_seo_check_task(site_id: int):
    app = create_app()
    with app.app_context():
        site = db.session.get(Site, site_id)
        if not site: return "Site not found"

        if not acquire_check_lock(site_id, "seo"):
            return "Already running"

        try:
            run_seo_service(site_id)
        except Exception:
            db.session.rollback()
            site = db.session.get(Site, site_id)
            site.seo_status = "failed"
            site.refresh_app_status()
            db.session.commit()
            raise
        finally:
            db.session.refresh(site)
            if site.seo_status == "running":
                site.seo_status = "failed"
            release_check_lock(site, "seo")
    return "OK"

@celery.task(name="tasks.dispatch_due_checks")
def dispatch_due_checks():
    with create_app().app_context():
        return {
            CHECK_UPTIME: _dispatch_for_type(CHECK_UPTIME, run_uptime_check_task),
            CHECK_SSL: _dispatch_for_type(CHECK_SSL, run_ssl_check_task),
            CHECK_SEO: _dispatch_for_type(CHECK_SEO, run_seo_check_task),
        }


@celery.task(name="tasks.run_zombie_rescue")
def run_zombie_rescue_task():
    with create_app().app_context():
        rescued = Site.rescue_stuck_tasks()
        db.session.commit()
        return {"rescued": rescued}

@celery.task(name="tasks.run_retention_cycle", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_retention_cycle_task():
    with create_app().app_context():
        return run_retention_service()


@celery.task(name="tasks.run_daily_summary", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_daily_summary_task():
    with create_app().app_context():
        return run_daily_summary_service()

def _dispatch_for_type(check_type: str, task) -> int:
    site_ids = get_due_site_ids(check_type)
    for site_id in site_ids:
        task.delay(site_id)
    return len(site_ids)
