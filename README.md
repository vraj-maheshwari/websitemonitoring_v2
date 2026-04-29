# Website Monitor and SEO Intelligence Engine

A Flask application for monitoring websites across three independent checks:
uptime, SSL certificate health, and SEO quality. The app exposes a dashboard,
JSON APIs, Celery background workers, alert history, notification recipients,
daily uptime summaries, and periodic cleanup jobs.

The current codebase is a single Flask app with SQLAlchemy models, Celery tasks,
HTTPX fetching, BeautifulSoup/lxml parsing, and SMTP-backed email alerts.

## Current Capabilities

### Monitoring Checks

- Uptime checks fetch the site with an explicit 5 second timeout.
- Uptime results store status code, total response time, true/available TTFB,
  current status, and error details.
- Slow responses are marked `DEGRADED` using `RESPONSE_TIME_THRESHOLD`.
- SSL checks connect to port 443 with Python's `ssl` and `socket` modules.
- SSL results include issuer, expiry date, days remaining, and state:
  `VALID`, `EXPIRING`, `EXPIRED`, or `ERROR`.
- SEO checks fetch HTML with an explicit 20 second timeout and streaming TTFB
  measurement.
- SEO parsing extracts title, meta description, headings, content length,
  links, image alt coverage, canonical URL, language, robots meta, viewport,
  mixed content, page size, robots.txt, and sitemap.xml signals.
- SEO scoring returns `GOOD`, `FAIR`, or `POOR` using weighted category scores:
  on-page, technical, content, performance, and security/mobile.

### Background Processing

Celery runs the check work asynchronously:

- `tasks.run_uptime_check`
- `tasks.run_ssl_check`
- `tasks.run_seo_check`
- `tasks.dispatch_due_checks`
- `tasks.run_zombie_rescue`
- `tasks.run_daily_summary`
- `tasks.run_retention_cycle`

Each check has its own status field:

- `uptime_status`
- `ssl_status`
- `seo_status`

Allowed values are `pending`, `running`, `done`, and `failed`.

The worker uses an atomic database update to acquire a per-site, per-check lock
before running work. This prevents duplicate uptime, SSL, or SEO checks from
running for the same site at the same time.

### Aggregate Status

`Site.refresh_app_status()` derives the user-facing `app_status` from the three
granular statuses:

- `pending`: all checks are pending
- `checking`: at least one check is running
- `ready`: all checks are done
- `partial`: at least one check failed, or the checks are mixed done/pending

`ready` is only possible when all three checks are `done`; a failed check cannot
be overwritten into `ready` by another check finishing later.

### Scheduling

Each site has independent intervals:

- `uptime_check_interval`, default 60 seconds
- `ssl_check_interval`, default 86400 seconds
- `seo_check_interval`, default 604800 seconds

The scheduler stores independent next-run timestamps:

- `next_uptime_check_at`
- `next_ssl_check_at`
- `next_seo_check_at`

Celery Beat currently schedules:

- due-check dispatch every 30 seconds
- zombie rescue every 5 minutes
- daily uptime summary once per day
- retention cleanup once per day

### Alerts

The alert service supports:

- downtime alerts when uptime transitions to `DOWN`
- recovery alerts when uptime returns from `DOWN`
- SSL invalid/error alerts
- SSL expiry warnings, deduplicated once per day
- SEO regression alerts when a previous SEO log exists and the score drops by
  more than 5 points

Alert attempts are recorded in `AlertHistory`. Recipients are configured per
site through `SiteNotification`.

### Dashboard and API

The dashboard is rendered with Jinja templates. The API returns JSON for site
management, polling, histories, and summaries.

`GET /api/sites` supports delta polling:

```text
GET /api/sites?since=2026-01-01T00:00:00Z
```

When `since` is provided, only sites with `updated_at > since` are returned.

## Tech Stack

- Python 3.12
- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- Celery
- Redis as Celery broker/result backend
- SQLite for local development
- PostgreSQL-compatible SQLAlchemy configuration for production
- HTTPX
- BeautifulSoup4 with lxml
- python-dotenv
- SMTP email via `smtplib`

## Project Structure

```text
app/
  __init__.py                  Flask app factory
  extensions.py                Shared SQLAlchemy extension
  api/
    routes.py                  Web routes, auth routes, and JSON API routes
  config/
    settings.py                Environment-backed configuration
  models/
    user.py                    Basic user model and password hashing
    site.py                    Site config, live state, aggregate status
    uptime_log.py              Uptime history
    ssl_log.py                 SSL history
    seo_log.py                 SEO audit history
    incident.py                Uptime incidents
    alert_history.py           Alert delivery history
    site_notification.py       Per-site email recipients
    daily_uptime_summary.py    Daily uptime aggregates
    daily_ssl_summary.py       Existing SSL summary model
    daily_seo_summary.py       Existing SEO summary model
  services/
    monitor_service.py         Uptime check logic
    ssl_service.py             SSL certificate check logic
    seo_service.py             SEO orchestration
    alert_service.py           Alert rules and alert history
    email_service.py           SMTP transport
    monitoring_service.py      Scheduling helpers
    retention_service.py       Old data cleanup
    summary_service.py         Daily uptime summary generation
  utils/
    http.py                    Explicit-timeout HTTP fetch and TTFB measurement
    parser.py                  SEO signal extraction
    seo_engine.py              SEO scoring and recommendations
    time.py                    UTC datetime helpers
    urls.py                    URL validation and normalization
  workers/
    tasks.py                   Celery app and task definitions
  templates/
    base.html
    dashboard.html
    site_detail.html
  static/
    dashboard.css

run.py                         Flask entry point
requirements.txt               Python dependencies
implementation.md              Architecture notes and target implementation spec
```

## Data Model Overview

### User

`User` stores email, password hash, creation time, and active state. The API
auth endpoints store `user_id` in the Flask session after register/login.

### Site

`Site` is the primary monitored entity. Important fields include:

- ownership: `user_id`
- URL data: `url`, `normalized_url`, `name`
- intervals: `uptime_check_interval`, `ssl_check_interval`,
  `seo_check_interval`
- next/last check timestamps for each check type
- granular statuses: `uptime_status`, `ssl_status`, `seo_status`
- aggregate status: `app_status`
- uptime metrics: `current_status`, `last_status_code`,
  `last_response_time`, `last_ttfb`
- SSL metrics: `ssl_state`, `ssl_expiry_date`, `ssl_days_remaining`,
  `ssl_issuer`
- SEO metrics: `seo_score`, `seo_state`
- polling support: `updated_at`

### Logs and History

- `UptimeLog`: status code, response time, TTFB, up/down/degraded status, error
- `SSLLog`: certificate state, issuer, expiry, days remaining, error
- `SEOLog`: score, status, score breakdown, extracted signals, issues,
  recommendations, error
- `Incident`: open/resolved uptime incidents
- `AlertHistory`: alert delivery records
- `DailyUptimeSummary`: daily totals, up/down/degraded counts, uptime
  percentage, average response time, average TTFB

## API Endpoints

### Auth

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
```

Example register body:

```json
{
  "email": "user@example.com",
  "password": "secret"
}
```

### Sites

```text
GET    /api/sites
GET    /api/sites?since=<ISO8601 datetime>
POST   /api/sites
GET    /api/sites/<site_id>
DELETE /api/sites/<site_id>
POST   /api/sites/<site_id>/check
GET    /api/sites/<site_id>/history/uptime?days=7
GET    /api/sites/<site_id>/history/ssl?limit=10
GET    /api/sites/<site_id>/history/seo?limit=5
GET    /api/sites/<site_id>/uptime-summary?days=30
```

Example create-site body:

```json
{
  "url": "https://example.com",
  "name": "Example",
  "uptime_check_interval": 60,
  "ssl_check_interval": 86400,
  "seo_check_interval": 604800,
  "notification_emails": ["ops@example.com"]
}
```

### Legacy/Compatibility Routes

These routes still exist for the dashboard and older API calls:

```text
GET  /api/check/<site_id>
GET  /api/check-seo/<site_id>
GET  /api/check-ssl/<site_id>
GET  /api/logs/<site_id>
GET  /api/seo-logs/<site_id>
GET  /api/site/<site_id>/status
POST /sites/new
POST /site/<site_id>/run/<check_type>
```

## Check Flow

### Add Site

1. The API validates and normalizes the URL.
2. A `Site` row is created with per-check intervals and next-run timestamps.
3. Notification recipients are stored.
4. Uptime, SSL, and SEO Celery tasks are queued.
5. The dashboard/API can poll status while checks run.

### Worker Task

1. The task creates a Flask application context.
2. It atomically acquires the check lock by moving that check status to
   `running`.
3. It runs the corresponding service.
4. The service writes logs and updates the site metrics.
5. The service schedules the next check timestamp.
6. The worker releases the lock in a `finally` block and refreshes
   `app_status`.

### Zombie Rescue

`Site.rescue_stuck_tasks()` marks stale running checks as failed:

- uptime timeout: 10 minutes
- SSL timeout: 30 minutes
- SEO timeout: 60 minutes

The rescue task is separate from data retention.

### Daily Summary

`summary_service.run_daily_summary()` aggregates the previous UTC calendar day
from `UptimeLog` into `DailyUptimeSummary`. The task is idempotent for a given
site/date pair.

### Data Retention

`retention_service.run_retention_cycle()` deletes old uptime logs, SSL logs,
SEO logs, incidents, and alert history using `LOG_RETENTION_DAYS`. It does not
delete daily uptime summaries.

## Configuration

Configuration is loaded from environment variables in `app/config/settings.py`.

Useful variables:

```text
SECRET_KEY=dev-secret-key
FLASK_DEBUG=true
DATABASE_URL=sqlite:///monitor.db
REDIS_URL=redis://localhost:6379/0
RESPONSE_TIME_THRESHOLD=3.0
SSL_EXPIRY_WARNING_DAYS=7
ALERT_COOLDOWN_MINUTES=15
LOG_RETENTION_DAYS=30
HTTP_VERIFY_SSL=true
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=admin@example.com
```

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file with at least:

```text
SECRET_KEY=change-me
DATABASE_URL=sqlite:///website_monitor.db
REDIS_URL=redis://localhost:6379/0
```

Start Redis before running Celery.

## Running Locally

Start the Flask app:

```bash
python run.py
```

Start a Celery worker:

```bash
celery -A app.workers.tasks worker --loglevel=info -P solo
```

Start Celery Beat:

```bash
celery -A app.workers.tasks beat --loglevel=info
```

The dashboard is available at:

```text
http://127.0.0.1:5000/
```

## Verification Commands

Import check without writing bytecode:

```bash
set PYTHONDONTWRITEBYTECODE=1
python -c "from app import create_app; app = create_app(); print(len(list(app.url_map.iter_rules())))"
```

Run against an in-memory database:

```bash
set PYTHONDONTWRITEBYTECODE=1
set DATABASE_URL=sqlite:///:memory:
python -c "from app import create_app; app = create_app(); print('ok')"
```

## Current Limitations

- The app uses `db.create_all()` on startup rather than Alembic migrations.
- Auth is currently session-based with a basic `User` model, not a full
  Flask-Login integration.
- Existing dashboard routes use a local development owner when no user is
  logged in, so local dashboard usage still works while avoiding ownerless rows.
- If this workspace refuses SQLite file writes, the app falls back to in-memory
  SQLite for development startup. Data will not persist in that fallback mode.
- SQLite is fine for local testing, but production should use PostgreSQL and a
  real migration workflow.
- Celery requires Redis to be running for background checks.
- SMTP settings must be configured before real email delivery will work.
