# Website Monitor and SEO Intelligence Engine

This project is a Flask + Celery SaaS-style website monitoring system. It monitors each website through three independent checks:

- Uptime
- SSL certificate health
- SEO quality

The system is designed so a slow or unstable website does not create misleading SEO results. SEO scans now validate fetched HTML before scoring, store fetch debugging data, and skip scoring cold-start placeholder pages.

## Current System Flow

### 1. User Adds A Website

A site can be created from the dashboard or through the API.

Flow:

1. User submits a URL and optional name/check intervals.
2. The URL is normalized by `app/utils/urls.py`.
3. A `Site` row is created.
4. Initial check timestamps are prepared by `prepare_site()`.
5. Notification email recipients are saved if provided.
6. The app queues three Celery jobs:
   - uptime check
   - SSL check
   - SEO check
7. The dashboard starts polling for updates.

Main files:

- `app/api/routes.py`
- `app/models/site.py`
- `app/services/monitoring_service.py`
- `app/workers/tasks.py`

## Data Model Logic

### Site

`Site` is the main monitored entity.

Important fields:

- URL identity: `url`, `normalized_url`, `name`
- ownership: `user_id`
- intervals: `uptime_check_interval`, `ssl_check_interval`, `seo_check_interval`
- last check timestamps: `last_uptime_check_at`, `last_ssl_check_at`, `last_seo_check_at`
- next check timestamps: `next_uptime_check_at`, `next_ssl_check_at`, `next_seo_check_at`
- per-check status: `uptime_status`, `ssl_status`, `seo_status`
- aggregate status: `app_status`
- uptime state: `current_status`, `last_status_code`, `last_response_time`, `last_ttfb`
- SSL state: `ssl_state`, `ssl_issuer`, `ssl_expiry_date`, `ssl_days_remaining`
- SEO state: `seo_score`, `seo_state`, `last_seo_fetch_valid`
- SEO cooldown support: `last_downtime_ended_at`

### SEOLog

`SEOLog` stores both the SEO score and the fetch quality metadata.

Important fetch-validation fields:

- `fetch_valid`
- `fetch_status`
- `fetch_page_size_kb`
- `fetch_html_preview`
- `invalidation_reason`

If `fetch_valid=False`, the log is stored for debugging, but no SEO score is produced.

## Status Logic

Each check has its own status:

```text
pending -> running -> done
pending -> running -> failed
```

Fields:

- `uptime_status`
- `ssl_status`
- `seo_status`

The user-facing `app_status` is derived by `Site.refresh_app_status()`:

- `pending`: all checks are pending
- `checking`: at least one check is running
- `ready`: all checks are done
- `partial`: mixed results or at least one failed check

This prevents one successful check from hiding another failed check.

## Uptime Check Flow

Main file:

- `app/services/monitor_service.py`

Flow:

1. Celery task acquires the uptime lock.
2. `fetch_url(site.url, timeout=5.0)` runs an HTTP GET.
3. The result stores:
   - status code
   - response time
   - TTFB
   - final URL
   - error message, if any
4. The service determines the current uptime state:
   - `DOWN` if fetch failed or status is not up
   - `DEGRADED` if response time is above `RESPONSE_TIME_THRESHOLD`
   - `UP` otherwise
5. A `UptimeLog` row is created.
6. The `Site` uptime fields are updated.
7. The next uptime check is scheduled.
8. Alert logic runs for downtime/recovery transitions.
9. If previous status was `DOWN` and current status becomes `UP` or `DEGRADED`, the system records:

```python
site.last_downtime_ended_at = checked_at
```

That timestamp activates the SEO cooldown.

## SEO Cooldown Logic

Main file:

- `app/services/seo_service.py`

SEO should not run immediately after a site recovers from downtime because many free PHP hosts return a cold, blank, or placeholder page during warm-up.

Rule:

```text
If site recovered from DOWN less than 120 seconds ago, skip/reschedule SEO.
```

Function:

```python
should_skip_seo_for_cooldown(site)
```

If cooldown is active:

- Celery SEO task reschedules itself after 120 seconds.
- Manual API checks return cooldown status.
- SEO service logs an invalid fetch result if called directly.

## SEO Check Flow

Main file:

- `app/services/seo_service.py`

SEO now has a safe, multi-step pipeline.

### Step 1: Cooldown Check

Before fetching HTML, SEO checks:

```python
should_skip_seo_for_cooldown(site)
```

If the site recently recovered from DOWN, SEO is skipped to avoid scoring a cold-start placeholder page.

### Step 2: Fetch HTML

SEO fetch uses:

```python
fetch_url(site.url, timeout=25.0, stream_for_ttfb=True)
```

SEO uses a longer timeout than uptime because full HTML pages, especially on free hosting, can take longer than a simple uptime request.

The fetch result includes:

- `html_content`
- `ttfb`
- `total_response_time`
- `status_code`
- `is_up`
- `error`
- `final_url`
- `https_redirect`
- `page_size_kb`

### Step 3: Validate Fetch

Before parsing or scoring, the fetched HTML is passed through:

```python
validate_seo_fetch(...)
```

Main file:

- `app/utils/seo_validator.py`

The validator rejects:

- empty responses
- timeout/error responses
- HTTP error pages
- pages smaller than 5 KB
- host placeholders such as account suspended, coming soon, InfinityFree, great-site.net placeholders, default nginx/Apache pages, and directory listings

If validation fails:

- `SEOLog.fetch_valid=False`
- `SEOLog.score=None`
- `SEOLog.status="INVALID"`
- `SEOLog.fetch_status` is set to `empty`, `timeout`, `error`, or `invalid_content`
- `SEOLog.fetch_page_size_kb` stores the actual size
- `SEOLog.fetch_html_preview` stores the first 1000 characters
- `SEOLog.invalidation_reason` explains what happened
- `Site.last_seo_fetch_valid=False`
- No SEO score is generated
- No false `POOR` rating is shown

### Step 4: Parse SEO Signals

If fetch validation passes, the HTML is parsed by:

```python
parse_seo_intelligence(html_content, site.url)
```

Main file:

- `app/utils/parser.py`

Extracted signals include:

- title and title length
- meta description and length
- H1/H2/H3 counts
- word count
- keyword density
- image count and missing alt count
- internal and external links
- canonical URL
- favicon
- hreflang
- robots meta
- HTML language
- viewport/mobile signal
- mixed content count
- blocking JS/CSS counts
- page size

The SEO service also checks:

- `/robots.txt`
- `/sitemap.xml`

Those resource checks use separate HEAD requests with an 8 second timeout.

### Step 5: Score SEO

Scoring is handled by:

```python
analyze_seo(signals)
```

Main file:

- `app/utils/seo_engine.py`

The scoring engine has a defensive hard gate:

```text
If page_size_kb < 5.0, raise ValueError.
```

That means even if someone accidentally calls the scorer before validation, tiny placeholder pages cannot be scored.

SEO categories:

- on-page
- technical
- content
- performance
- security/mobile

Performance scoring uses true streaming TTFB from `signals["ttfb"]`, not total download time.

Score status:

- `GOOD`: score >= 80
- `FAIR`: score >= 60
- `POOR`: score < 60

### Step 6: Save SEO Log

Valid SEO checks create an `SEOLog` with:

- score
- status
- score breakdown
- extracted signals
- issues
- recommendations
- fetch metadata

Invalid SEO checks create an `SEOLog` with:

- no score
- invalid status
- fetch metadata
- invalidation reason
- HTML preview

### Step 7: Update Site

For valid SEO checks:

- `site.seo_score` is updated
- `site.seo_state` is updated
- `site.last_seo_fetch_valid=True`
- next SEO check is scheduled

For invalid SEO checks:

- `site.last_seo_fetch_valid=False`
- the old SEO score is not replaced by a false POOR score
- the dashboard displays an invalid-fetch warning

## SSL Check Flow

Main file:

- `app/services/ssl_service.py`

Flow:

1. Celery task acquires the SSL lock.
2. The service connects to the site's hostname on port 443.
3. The certificate is inspected.
4. Expiry date, issuer, and days remaining are calculated.
5. An `SSLLog` row is created.
6. The `Site` SSL fields are updated.
7. The next SSL check is scheduled.
8. SSL alert rules run for invalid certificates and expiry warnings.

SSL states:

- `VALID`
- `EXPIRING`
- `EXPIRED`
- `ERROR`

## HTTP Fetch Logic

Main file:

- `app/utils/http.py`

All callers must pass an explicit timeout:

```python
fetch_url(url, timeout=5.0)
```

If timeout is `None`, `fetch_url()` raises `TypeError`.

Timeouts by caller:

- uptime: 5 seconds
- SEO page fetch: 25 seconds
- robots/sitemap HEAD checks: 8 seconds

When `stream_for_ttfb=True`, TTFB is measured when the first response byte arrives, not after the full page downloads.

Network errors and timeouts are retried with backoff:

```text
1 second
2 seconds
```

HTTP 4xx/5xx responses are not retried as network errors because they are real server responses.

## Celery Worker Flow

Main file:

- `app/workers/tasks.py`

Each check task follows the same broad structure:

1. Create Flask application context.
2. Load the `Site`.
3. Acquire a per-site/per-check lock.
4. Mark the check as `running`.
5. Run the service.
6. Update status to `done` or `failed`.
7. Refresh aggregate `app_status`.
8. Release the lock in `finally`.

Task names:

```text
tasks.run_uptime_check
tasks.run_ssl_check
tasks.run_seo_check
tasks.run_due_uptime_checks
tasks.run_due_ssl_checks
tasks.run_due_seo_checks
tasks.dispatch_due_checks
tasks.run_zombie_rescue
tasks.run_daily_summary
tasks.run_retention_cycle
```

## Celery Beat Schedule

Main file:

- `app/config/settings.py`

Current beat schedule:

- uptime due-check dispatcher: every 30 seconds
- SSL due-check dispatcher: every hour
- SEO due-check dispatcher: every hour at minute 5
- zombie rescue: every 5 minutes
- daily summary: every day at 00:05 UTC
- data retention: every day at 03:00 UTC

Per-site intervals are still enforced by:

- `next_uptime_check_at`
- `next_ssl_check_at`
- `next_seo_check_at`

So even if Celery Beat wakes up every hour for SEO, each site only runs SEO when its own `next_seo_check_at` is due.

## Zombie Rescue

Main file:

- `app/workers/tasks.py`

Zombie rescue fixes checks stuck in `running`.

Timeout thresholds:

- uptime stuck over 10 minutes
- SSL stuck over 30 minutes
- SEO stuck over 90 minutes

When rescued:

- the check status becomes `failed`
- the started timestamp is cleared
- `app_status` is refreshed

Zombie rescue is separate from data retention.

## API Flow

Main file:

- `app/api/routes.py`

### Site List

```text
GET /api/sites
GET /api/sites?since=<ISO8601 datetime>
```

The `since` parameter supports delta polling. When supplied, only sites changed after that timestamp are returned.

### Site Detail

```text
GET /api/sites/<site_id>
```

Includes:

- site summary
- latest uptime log
- latest SSL log
- latest SEO log
- SEO fetch validation summary

SEO response includes:

```json
{
  "score": 76,
  "state": "FAIR",
  "last_fetch_valid": true,
  "last_check_at": "2026-04-30T12:00:00+00:00",
  "warning": null,
  "latest_log": {}
}
```

If the last SEO fetch was invalid, `warning` explains that the score may be inaccurate.

### Manual Check

```text
POST /api/sites/<site_id>/check
```

Response includes:

- uptime dispatch status
- SSL dispatch status
- SEO dispatch status
- `cooldown_active`
- `cooldown_reason`

SEO may be skipped if cooldown is active.

### Histories

```text
GET /api/sites/<site_id>/history/uptime?days=7
GET /api/sites/<site_id>/history/ssl?limit=10
GET /api/sites/<site_id>/history/seo?limit=5
```

SEO history includes fetch validation fields:

- `fetch_valid`
- `fetch_status`
- `fetch_page_size_kb`
- `invalidation_reason`
- `fetch_html_preview`

## Dashboard Flow

Main files:

- `app/templates/dashboard.html`
- `app/templates/site_detail.html`
- `app/static/dashboard.css`

Dashboard behavior:

1. The main dashboard lists all monitored sites.
2. It shows uptime, SSL, SEO, and aggregate status.
3. It polls `/api/sites?since=<timestamp>` every 3 seconds.
4. Only changed sites are returned after the first poll.

Site detail behavior:

1. Shows operational health, latency, SSL, and SEO state.
2. Shows SEO score only when the last SEO fetch was valid.
3. Shows a warning banner when the last SEO fetch was invalid.
4. Shows SEO history with page size, fetch validity, and invalidation notes.
5. Allows manual SEO re-run after the site is fully online.

## Alert Flow

Main file:

- `app/services/alert_service.py`

Alerts supported:

- downtime
- recovery
- SSL invalid/error
- SSL expiry warning
- SEO score regression

Alert attempts are saved in `AlertHistory`.

Per-site recipients are stored in `SiteNotification`.

Email transport is handled by:

- `app/services/email_service.py`

## Scheduling Flow

Main file:

- `app/services/monitoring_service.py`

Each check type has an independent interval and next-run timestamp.

After a service finishes, it calls:

```python
schedule_next_run(site, check_type, checked_at)
```

That updates:

- the check-specific last timestamp
- the check-specific next timestamp
- the aggregate `next_check_at`

Due check dispatchers query sites whose next timestamp is due.

## Data Retention And Summary Flow

### Daily Summary

Main file:

- `app/services/summary_service.py`

The daily summary task aggregates the previous UTC day from `UptimeLog` into `DailyUptimeSummary`.

Stored summary data:

- total checks
- up/down/degraded counts
- uptime percentage
- average response time
- average TTFB

### Retention

Main file:

- `app/services/retention_service.py`

Retention deletes old logs and history based on:

```text
LOG_RETENTION_DAYS
```

It cleans old:

- uptime logs
- SSL logs
- SEO logs
- incidents
- alert history

It does not delete daily uptime summaries.

## Project Structure

```text
app/
  __init__.py                  Flask app factory
  extensions.py                SQLAlchemy extension
  api/
    routes.py                  Dashboard routes and JSON API
  config/
    settings.py                Environment-backed config and Celery Beat schedule
  models/
    site.py                    Monitored website state
    uptime_log.py              Uptime history
    ssl_log.py                 SSL history
    seo_log.py                 SEO history and fetch validation metadata
    incident.py                Uptime incidents
    alert_history.py           Alert records
    site_notification.py       Per-site notification recipients
    daily_uptime_summary.py    Daily uptime aggregates
    daily_ssl_summary.py       SSL summary model
    daily_seo_summary.py       SEO summary model
    user.py                    User account model
  services/
    monitor_service.py         Uptime logic
    ssl_service.py             SSL logic
    seo_service.py             SEO validation, parsing, scoring orchestration
    alert_service.py           Alert rules
    email_service.py           SMTP delivery
    monitoring_service.py      Scheduling helpers
    retention_service.py       Cleanup jobs
    summary_service.py         Daily summaries
  utils/
    http.py                    HTTP fetch, retry, timeout, TTFB logic
    parser.py                  SEO signal extraction
    seo_engine.py              SEO scoring
    seo_validator.py           SEO fetch validation
    time.py                    UTC helpers
    urls.py                    URL normalization
  workers/
    tasks.py                   Celery tasks
  templates/
    dashboard.html
    site_detail.html
    base.html
  static/
    dashboard.css
migrations/
  env.py
  versions/
    20260430_add_seo_fetch_validation_fields.py
run.py
requirements.txt
```

## Configuration

Configuration is loaded from `.env` and `app/config/settings.py`.

Useful environment variables:

```text
SECRET_KEY=change-me
FLASK_DEBUG=true
DATABASE_URL=sqlite:///website_monitor.db
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

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env`:

```text
SECRET_KEY=change-me
DATABASE_URL=sqlite:///website_monitor.db
REDIS_URL=redis://localhost:6379/0
```

Apply migrations with Alembic:

```bash
python -m alembic upgrade head
```

## Running Locally

Start Flask:

```bash
python run.py
```

Start Celery worker:

```bash
celery -A app.workers.tasks worker --loglevel=info -P solo
```

Start Celery Beat:

```bash
celery -A app.workers.tasks beat --loglevel=info
```

Dashboard:

```text
http://127.0.0.1:5000/
```

## Tests

Run tests:

```bash
python -m pytest tests
```

Current SEO-focused tests cover:

- empty SEO fetch rejection
- tiny placeholder page rejection
- host placeholder detection
- valid large page acceptance
- HTTP error rejection
- HTML preview truncation
- timeout fetch status
- SEO cooldown behavior
- invalid fetch does not produce a score
- explicit fetch timeout requirement
- page-size hard gate in scorer
- TTFB-based performance scoring

## Important Production Behavior

The most important SEO safety rule:

```text
Only valid fetched HTML is scored.
```

A tiny 0.83 KB placeholder page should produce:

```json
{
  "fetch_valid": false,
  "score": null,
  "fetch_status": "invalid_content"
}
```

It should not produce a false `POOR` score.

## Current Limitations

- Celery requires Redis.
- SMTP must be configured before email alerts work.
- SQLite is acceptable for local development; production should use PostgreSQL.
- Some local development code still uses `db.create_all()` on app startup, while migrations are also present.
- Dashboard authentication is session-based and lightweight.
- The dashboard uses a local fallback user when no user is logged in.
