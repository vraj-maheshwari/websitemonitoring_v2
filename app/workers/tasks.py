from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from datetime import timedelta
import logging
from app import create_app
from app.config.settings import Config
from app.extensions import db
from app.models.site import Site
from app.services.monitor_service import run_uptime_check as run_uptime_service
from app.services.monitoring_service import CHECK_SEO, CHECK_SSL, CHECK_UPTIME, get_due_site_ids
from app.services.retention_service import run_retention_cycle as run_retention_service
from app.services.seo_service import should_skip_seo_for_cooldown, run_seo_check as run_seo_service
from app.services.summary_service import run_daily_summary as run_daily_summary_service
from app.services.ssl_service import run_ssl_check as run_ssl_service
from app.utils.time import now_utc

logger = logging.getLogger(__name__)

# Initialize Celery
celery = Celery("tasks", broker=Config.CELERY_BROKER_URL, backend=Config.CELERY_RESULT_BACKEND)
celery.conf.update(
    beat_schedule=Config.CELERY_BEAT_SCHEDULE,
    timezone=Config.CELERY_TIMEZONE,
    broker_connection_timeout=1,
    broker_transport_options={"max_retries": 0, "socket_connect_timeout": 1},
    task_publish_retry=False,
    # Windows-safe pool — prefork (billiard) crashes on win32
    worker_pool=Config.CELERY_WORKER_POOL,
    worker_concurrency=Config.CELERY_WORKER_CONCURRENCY,
    # Suppress Celery 6.0 deprecation warning
    broker_connection_retry_on_startup=Config.BROKER_CONNECTION_RETRY_ON_STARTUP,
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
            "last_started_at": now_utc(),
            "app_status": "checking",
            "is_processing": True,
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

@celery.task(
    name="tasks.run_seo_check",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    soft_time_limit=300,
    time_limit=360,
)
def run_seo_check_task(self, site_id: int):
    app = create_app()
    with app.app_context():
        site = db.session.get(Site, site_id)
        if not site:
            return "Site not found"

        # Sub-fix A: check cooldown BEFORE acquiring the lock so we never
        # set seo_status="running" and then immediately override it to "pending".
        should_skip, reason = should_skip_seo_for_cooldown(site)
        if should_skip:
            logger.info("[SEO TASK] site_id=%s cooldown active, rescheduling. Reason: %s", site_id, reason)
            run_seo_check_task.apply_async(args=[site_id], countdown=120)
            return "Cooldown active"

        if not acquire_check_lock(site_id, "seo"):
            return "Already running"

        lock_released = False
        try:
            # Sub-fix B: acquire_check_lock already set seo_status="running" via
            # bulk UPDATE — do NOT set it again here.
            result = run_seo_service(site, db.session)
            site = db.session.get(Site, site_id)  # re-fetch after service commits
            site.seo_status = "done" if result and not result.get("error_message") else "failed"
            if result and result.get("fetch_valid") is False:
                site.seo_status = "done"
                logger.warning("[SEO TASK] site_id=%s fetch invalid: %s", site_id, result.get("invalidation_reason"))
            site.refresh_app_status()
            db.session.commit()
        except SoftTimeLimitExceeded:
            logger.error(
                "SEO check task soft time limit exceeded for site %s", site_id
            )
            db.session.rollback()
            site = db.session.get(Site, site_id)
            if site is not None:
                site.seo_status = "failed"
                release_check_lock(site, "seo")
                lock_released = True
        except Exception:
            logger.exception("[SEO TASK] site_id=%s exception", site_id)
            db.session.rollback()
            site = db.session.get(Site, site_id)
            site.seo_status = "failed"
            site.refresh_app_status()
            db.session.commit()
        finally:
            if not lock_released:
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


@celery.task(name="tasks.run_due_uptime_checks")
def run_due_uptime_checks():
    with create_app().app_context():
        return _dispatch_for_type(CHECK_UPTIME, run_uptime_check_task)


@celery.task(name="tasks.run_due_ssl_checks")
def run_due_ssl_checks():
    with create_app().app_context():
        return _dispatch_for_type(CHECK_SSL, run_ssl_check_task)


@celery.task(name="tasks.run_due_seo_checks")
def run_due_seo_checks():
    with create_app().app_context():
        return _dispatch_for_type(CHECK_SEO, run_seo_check_task)


@celery.task(name="tasks.run_zombie_rescue")
def run_zombie_rescue_task():
    with create_app().app_context():
        rescued = {"uptime": 0, "ssl": 0, "seo": 0}
        thresholds = {
            "uptime": timedelta(minutes=10),
            "ssl": timedelta(minutes=30),
            "seo": timedelta(minutes=90),
        }
        now = now_utc()
        for check_type, threshold in thresholds.items():
            cutoff = now - threshold
            status_field = getattr(Site, f"{check_type}_status")
            started_field = getattr(Site, f"{check_type}_started_at")
            stuck_sites = Site.query.filter(status_field == "running", started_field < cutoff).all()
            for site in stuck_sites:
                logger.warning(
                    "[ZOMBIE] Rescuing site_id=%s %s stuck since %s",
                    site.id,
                    check_type,
                    getattr(site, f"{check_type}_started_at"),
                )
                setattr(site, f"{check_type}_status", "failed")
                setattr(site, f"{check_type}_started_at", None)
                site.refresh_app_status()
                rescued[check_type] += 1
        db.session.commit()
        return rescued

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
