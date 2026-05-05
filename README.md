# Website Monitor

Website Monitor is a Flask based SaaS-style monitoring platform for tracking website uptime, SSL certificate health, SEO quality, Core Web Vitals, technology stack changes, broken links, security posture, incidents, alerts, analytics, and downloadable reports.

The system has two user-facing surfaces:

- A server-rendered web dashboard for managing monitored sites and viewing current health.
- A JSON API for auth, site management, histories, analytics, incidents, SEO intelligence, security results, and manual check dispatch.

Background checks are handled by Celery workers and scheduled by Celery Beat. Data is stored with SQLAlchemy models and maintained through Alembic migrations.

## Table of Contents

1. [Main Capabilities](#main-capabilities)
2. [Technology Stack](#technology-stack)
3. [Quick Start](#quick-start)
4. [Deployment](#deployment)
5. [Environment Variables](#environment-variables)
6. [Environment Variables Details](#environment-variables-details)
7. [Runtime Architecture](#runtime-architecture)
8. [Application Flow](#application-flow)
9. [Data Model](#data-model)
10. [Service Layer](#service-layer)
11. [Worker and Scheduling Logic](#worker-and-scheduling-logic)
12. [SEO Logic](#seo-logic)
13. [Security Logic](#security-logic)
14. [Uptime, SSL, Incidents, and Alerts](#uptime-ssl-incidents-and-alerts)
15. [API Reference](#api-reference)
16. [Web UI](#web-ui)
17. [File and Folder Guide](#file-and-folder-guide)
18. [Migrations](#migrations)
19. [Tests](#tests)
20. [Contributing](#contributing)
21. [License](#license)
22. [Recent Implementation Notes](#recent-implementation-notes)
23. [Operational Notes](#operational-notes)

## Main Capabilities

| Area | What the software does |
| --- | --- |
| Uptime monitoring | Performs HTTP checks, records status code, response time, TTFB, UP/DOWN/DEGRADED status, and errors. |
| SSL monitoring | Connects to port 443, reads certificate issuer and expiry, calculates days remaining, and classifies VALID/EXPIRING/EXPIRED/ERROR. |
| DNS monitoring | Resolves domain names, tracks IP addresses, nameservers, MX records, detects DNS hijacking, and monitors changes. |
| SEO auditing | Fetches rendered or raw HTML, validates content, extracts page signals, scores SEO, stores issues and recommendations. |
| Hybrid fetch | Uses fast HTTP first, then Playwright browser fallback for JS-only pages, bot challenge pages, tiny shells, placeholders, or failed HTTP content. |
| Core Web Vitals | Stores server-side estimates plus optional real browser measurements from Playwright Performance APIs. |
| Technology profiling | Detects frameworks, CMS, analytics, CDN, server, and frontend technologies from HTML and response headers. |
| Broken link checking | Extracts page links and checks them concurrently with HEAD/GET fallback. |
| Security audit | Scores HTTP security headers, CSP, CORS, mixed content, and malware/injection signatures. |
| Incident management | Opens incidents on DOWN transitions, tracks timeline events, classifies root cause, and resolves on recovery. |
| Alerting | Sends Microsoft Teams alerts for downtime, recovery, SSL invalid/expiry, DNS hijacking, and SEO regression with cooldown controls. |
| Analytics | Builds uptime trends, SEO trends, latency distribution, average response time, and incident counts. |
| Retention | Aggregates raw logs into daily summaries and deletes old raw logs, resolved incidents, and alert history. |
| Reports | Exports a structured JSON report per monitored site. |

## Technology Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.12 compatible codebase |
| Web framework | Flask 3.0 |
| Templates | Jinja2 |
| CSS | Custom dashboard CSS |
| Database ORM | SQLAlchemy 2.0 and Flask-SQLAlchemy 3.1 |
| Migrations | Alembic |
| Background jobs | Celery 5.3 |
| Broker/result backend | Redis |
| HTTP client | HTTPX |
| HTML parsing | BeautifulSoup4 and lxml |
| Browser automation | Playwright Chromium |
| SSL inspection | Python ssl/socket modules |
| DNS inspection | dnspython |
| Auth password hashing | Werkzeug password hash helpers |
| CSRF | Flask-WTF CSRFProtect for web forms |
| Testing | pytest |
| Production DB option | PostgreSQL via psycopg2-binary |
| Development DB option | SQLite |

## Quick Start

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy environment defaults:

```powershell
Copy-Item .env.example .env
```

Run database migrations:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Install Playwright Chromium if Lighthouse/browser SEO is enabled:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

Start Redis, then run the web app:

```powershell
python run.py
```

Start a Celery worker:

```powershell
celery -A app.workers.tasks.celery worker --loglevel=info

python -m celery -A app.workers.tasks.celery worker --loglevel=info
```

Start Celery Beat:

```powershell
celery -A app.workers.tasks.celery beat --loglevel=info

python -m celery -A app.workers.tasks.celery beat --loglevel=info
```

Run tests:

```powershell
pytest
```

## Deployment

For production deployment:

1. Use PostgreSQL instead of SQLite by setting `DATABASE_URL` to a PostgreSQL connection string (e.g., `postgresql://user:pass@host:port/db`).
2. Ensure Redis is running and accessible via `REDIS_URL`.
3. Set `FLASK_DEBUG=false` and configure `SECRET_KEY` securely.
4. Use a production WSGI server like Gunicorn: `gunicorn -w 4 -b 0.0.0.0:8000 run:app`.
5. Run Celery workers with appropriate concurrency: `celery -A app.workers.tasks.celery worker --loglevel=info`.
6. Run Celery Beat: `celery -A app.workers.tasks.celery beat --loglevel=info`.
7. For SSL verification in production, ensure certificates are valid.
8. Monitor logs and use the operational notes for troubleshooting.

## Environment Variables Details

The `.env.example` file contains:

```
SECRET_KEY=dev-secret-key
FLASK_DEBUG=false
DATABASE_URL=sqlite:///website_monitor.db
REDIS_URL=redis://localhost:6379/0
RESPONSE_TIME_THRESHOLD=3.0
SSL_EXPIRY_WARNING_DAYS=7
SSL_CHECK_INTERVAL_SECONDS=21600
SEO_CHECK_INTERVAL_SECONDS=21600
ALERT_COOLDOWN_MINUTES=15
LOG_RETENTION_DAYS=30
LIGHTHOUSE_ENABLED=true
HTTP_VERIFY_SSL=true
MAX_RETRIES=2
RETRY_DELAY=2
LOG_LEVEL=INFO
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
ALERT_EMAIL=alerts@example.com
```

Copy this to `.env` and adjust values as needed.

## Environment Variables

The configuration is loaded in `app/config/settings.py` through `python-dotenv`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | `dev-secret-key` | Flask session signing and CSRF signing. |
| `FLASK_DEBUG` | `false` | Enables Flask debug mode. In debug mode, the app creates `dev@localhost.test` / `devpassword123` on first boot if no users exist. |
| `DATABASE_URL` | `sqlite:///website_monitor.db` | SQLAlchemy database URL. Relative SQLite paths are resolved under Flask instance storage. |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker and result backend. |
| `RESPONSE_TIME_THRESHOLD` | `3.0` | Seconds above which a reachable site becomes DEGRADED. |
| `SSL_EXPIRY_WARNING_DAYS` | `7` | Days before SSL expiry where warnings begin. |
| `SSL_CHECK_INTERVAL_SECONDS` | `21600` | Global default used by configuration; per-site intervals are stored on `Site`. |
| `SEO_CHECK_INTERVAL_SECONDS` | `21600` | Global default used by configuration; per-site intervals are stored on `Site`. |
| `ALERT_COOLDOWN_MINUTES` | `15` | Prevents repeated alerts for the same site/event/incident. |
| `LOG_RETENTION_DAYS` | `30` | Raw log retention window before aggregation and deletion. |
| `LIGHTHOUSE_ENABLED` | `true` | Enables Playwright-based browser performance audits during SEO checks. |
| `HTTP_VERIFY_SSL` | `true` | Controls SSL verification for outbound HTTP requests. |
| `MAX_RETRIES` | `2` | Retry count used by HTTP utility configuration. |
| `RETRY_DELAY` | `2` | Retry delay used by HTTP utility configuration. |
| `LOG_LEVEL` | `INFO` | Application logging level. |
| `TEAMS_WEBHOOK_URL` | hardcoded fallback URL in settings | Microsoft Teams or Power Automate webhook endpoint. Prefer setting this in `.env`. |
| `ALERT_EMAIL` | example only | Present in `.env.example`; current alert transport uses Teams. |

## Runtime Architecture

```text
Browser / API Client
        |
        v
Flask app factory: app/__init__.py
        |
        +-- Web routes: app/api/routes.py, templates, static CSS
        +-- JSON API: app/api/routes.py
        +-- SQLAlchemy models: app/models/*
        |
        v
Service layer: app/services/*
        |
        +-- HTTP/SSL/SEO/Security/Analytics/Reports/Alerts
        |
        v
Database

Celery Beat
        |
        v
Celery tasks: app/workers/tasks.py
        |
        +-- find due sites
        +-- lock per check type
        +-- run service
        +-- schedule next run
        +-- release lock
```

The app uses the application factory pattern. `create_app()` configures Flask, checks SQLite writability, initializes SQLAlchemy and CSRF, imports models, creates tables for development safety, registers the web and API blueprints, and returns the Flask app.

## Application Flow

### Adding a Site

1. User submits a URL through `POST /sites/new` or `POST /api/sites`.
2. `normalize_url()` canonicalizes the input and builds `normalized_url`.
3. A `Site` record is created with owner, intervals, status fields, and first due timestamps.
4. `prepare_site()` sets missing display name and initializes `next_uptime_check_at`, `next_ssl_check_at`, `next_seo_check_at`, and `next_check_at`.
5. The app commits the site.
6. Uptime, SSL, and SEO Celery tasks are queued immediately.
7. The dashboard/detail view shows `checking` until tasks finish.

### Scheduled Checks

1. Celery Beat triggers due-check dispatcher tasks on fixed schedules.
2. `get_due_site_ids(check_type)` finds sites whose `next_*_check_at` timestamp is due.
3. Each due site receives a task for that check type.
4. The task acquires a database lock by changing `{check_type}_status` to `running`.
5. The service performs the check and writes log rows.
6. `schedule_next_run()` updates last and next timestamps.
7. The task releases the lock and refreshes the site-level `app_status`.

### Manual Checks

Manual checks can be triggered from the UI or API:

- `POST /site/<id>/run/uptime`
- `POST /site/<id>/run/ssl`
- `POST /site/<id>/run/seo`
- `POST /site/<id>/run/all`
- `POST /api/sites/<id>/check`
- `GET /api/check/<id>`
- `GET /api/check-ssl/<id>`
- `GET /api/check-seo/<id>`

Manual SEO checks honor the post-recovery cooldown so a freshly recovered site is not scored from temporary warm-up or placeholder content.

## Data Model

### `User`

File: `app/models/user.py`

Stores user identity and password hash.

Important fields:

- `id`
- `email`
- `password_hash`
- `created_at`
- `is_active`

Relationships:

- `sites`: one user owns many sites.

### `Site`

File: `app/models/site.py`

The central model. It stores configuration, current state, denormalized latest metrics, scheduling timestamps, processing locks, and relationships to all logs.

Important groups:

- Identity: `id`, `user_id`, `name`, `url`, `normalized_url`
- Intervals: `check_interval`, `uptime_check_interval`, `ssl_check_interval`, `seo_check_interval`
- Scheduling: `last_*_check_at`, `next_*_check_at`, `next_check_at`
- SaaS state: `app_status`, `is_processing`, `last_started_at`, `uptime_status`, `ssl_status`, `seo_status`
- Uptime snapshot: `current_status`, `last_status_code`, `last_response_time`, `last_ttfb`, `last_error_message`
- Incident snapshot: `incident_opened_at`, `last_incident_resolved_at`, `last_downtime_ended_at`
- SSL snapshot: `ssl_state`, `ssl_issuer`, `ssl_expiry_date`, `ssl_days_remaining`, `ssl_last_error`
- DNS snapshot: `dns_resolved`, `dns_resolution_time_ms`, `dns_last_ips`, `dns_last_ns`, `dns_hijack_suspected`, `dns_ns_changed`, `dns_last_error`
- SEO snapshot: `seo_state`, `seo_score`, `seo_last_error`, `last_seo_fetch_valid`
- Lighthouse snapshot: `lh_performance_score`, `lh_lcp_ms`, `lh_cls`

Status values:

- `app_status`: `pending`, `checking`, `ready`, `partial`, `initializing`
- granular task statuses: `pending`, `running`, `done`, `failed`
- uptime status: `PENDING`, `UP`, `DOWN`, `DEGRADED`
- SSL state: `UNKNOWN`, `VALID`, `EXPIRING`, `EXPIRED`, `ERROR`
- DNS state: `UNKNOWN`, `RESOLVED`, `HIJACK_SUSPECTED`, `ERROR`
- SEO state: `UNKNOWN`, `GOOD`, `FAIR`, `POOR`, `INVALID`

Important methods:

- `display_name()`
- `to_dict()`
- `refresh_app_status()`
- `rescue_stuck_tasks()`

### `UptimeLog`

File: `app/models/uptime_log.py`

One row per uptime check.

Fields:

- `site_id`
- `status_code`
- `response_time`
- `ttfb`
- `is_up`
- `status`
- `error_message`
- `checked_at`

### `DNSLog`

File: `app/models/dns_log.py`

One row per DNS check.

Fields:

- `site_id`
- `checked_at`
- `resolved`
- `resolution_time_ms`
- `ip_addresses`
- `nameservers`
- `mx_records`
- `hijack_suspected`
- `new_ips`
- `removed_ips`
- `ns_changed`
- `added_ns`
- `removed_ns`
- `error_message`

### `SEOLog`

File: `app/models/seo_log.py`

One row per SEO audit. This is the largest model and stores raw extracted signals, score output, fetch validation metadata, Core Web Vitals, technology profile, link report, security report, and Playwright Lighthouse data.

Main field groups:

- Core: `score`, `status`, `checked_at`
- On-page: `title`, `title_length`, `meta_description`, `meta_length`, `h1_list`, `h1_count`, `h2_count`, `h3_count`, `word_count`, `keyword_density`
- Content: `image_count`, `missing_alt_count`, `internal_link_count`, `external_link_count`
- Technical: `has_robots`, `has_sitemap`, `canonical`, `has_favicon`, `has_hreflang`, `robots_meta`, `html_lang`
- Performance: `page_size_kb`, `js_blocking_count`, `css_blocking_count`, `ttfb`
- Mobile/security SEO: `has_viewport`, `mobile_friendly`, `https_redirect`, `mixed_content_count`
- Scoring output: `score_breakdown`, `issues`, `recommendations`, `signals`, `error_message`
- Fetch validation: `fetch_valid`, `fetch_html_preview`, `fetch_page_size_kb`, `fetch_status`, `invalidation_reason`
- Hybrid fetch: `render_mode`, `used_fallback`, `fallback_reason`
- CWV estimates: `cwv_lcp_estimate_s`, `cwv_fid_estimate_ms`, `cwv_cls_estimate`, ratings, `cwv_data`
- Technology profile: `tech_stack`, `tech_flat`, `tech_diff`
- Broken links: `broken_links`, `broken_link_count`, `links_checked`
- Security: `security_score`, `security_grade`, `security_headers`, `security_issues`, `malware_flags`, `security_categories`, `cors_issues`, `csp_issues`, `mixed_content_detail`
- Real browser performance: `lh_lcp_ms`, `lh_fcp_ms`, `lh_tbt_ms`, `lh_cls`, `lh_ttfb_ms`, `lh_tti_ms`, `lh_si_ms`, `lh_page_load_ms`, `lh_performance_score`, ratings, `lh_audit_method`, `lh_audited_at`, `lh_error`

### `Incident`

File: `app/models/incident.py`

Tracks downtime lifecycle.

Fields:

- `site_id`
- `status`: `OPEN` or `RESOLVED`
- `opened_at`, `resolved_at`
- opened and resolved status code/response/error fields
- `root_cause`: `TIMEOUT`, `DNS`, `SERVER`, `CLIENT`, `CONNECTION`, `UNKNOWN`
- `timeline`: JSON list of check events

### `AlertHistory`

File: `app/models/alert_history.py`

Stores each attempted Teams alert.

Fields:

- `site_id`
- `incident_id`
- `event_type`
- `recipient`
- `subject`
- `body`
- `delivery_status`: `PENDING`, `SENT`, `FAILED`
- `error_message`
- `sent_at`

### Daily Summary Models

Files:

- `app/models/daily_uptime_summary.py`
- `app/models/daily_ssl_summary.py`
- `app/models/daily_seo_summary.py`

These models preserve aggregate history after raw logs are deleted.

Daily uptime summary:

- uptime percentage
- average response time
- average TTFB
- outage count
- total/up/down/degraded check counts

Daily SSL summary:

- total checks
- valid count
- average days remaining

Daily SEO summary:

- total valid checks
- average/min/max SEO score

## Service Layer

### `monitoring_service.py`

Coordinates per-site scheduling.

Key functions:

- `prepare_site(site)`: normalizes URL, sets default name, initializes due timestamps.
- `refresh_next_check_at(site)`: sets `next_check_at` to the earliest next check.
- `get_interval_seconds(site, check_type)`: returns the correct per-check interval with minimums.
- `schedule_next_run(site, check_type, checked_at)`: updates last/next timestamps after a check.
- `get_due_site_ids(check_type, now=None, limit=100)`: returns due sites for Celery dispatch.

### `monitor_service.py`

Runs uptime checks.

Logic:

1. Fetch URL with `fetch_url()`.
2. Classify result as `DOWN`, `DEGRADED`, or `UP`.
3. Create `UptimeLog`.
4. Update denormalized `Site` uptime fields.
5. Schedule the next uptime run.
6. If recovering from DOWN, mark `last_downtime_ended_at` for SEO cooldown.
7. Pass status transition to alert/incident logic.

### `dns_service.py`

Runs DNS checks.

Logic:

1. Extract hostname from URL.
2. Resolve A, NS, and MX records.
3. Compare current IPs/nameservers with previous check.
4. Detect DNS hijacking by comparing against expected IPs.
5. Create `DNSLog`.
6. Update `Site` DNS snapshot.
7. Schedule next DNS run.
8. Trigger DNS hijacking alerts.

### `seo_service.py`

Orchestrates the full SEO intelligence flow.

Logic:

1. Respect recovery cooldown.
2. Fetch HTML with `fetch_html_for_seo()`.
3. Validate fetched HTML using `validate_seo_fetch()`.
4. Parse SEO signals with `parse_seo_intelligence()`.
5. Check `/robots.txt` and `/sitemap.xml`.
6. Score with `analyze_seo()`.
7. Estimate Core Web Vitals with `estimate_cwv()`.
8. Detect technologies with `detect_technologies()`.
9. Compare technology stack with previous valid SEO log.
10. Extract and check broken links.
11. Run security audit.
12. Save `SEOLog`.
13. Update denormalized `Site` SEO fields.
14. Trigger SEO regression alerts.
15. If `LIGHTHOUSE_ENABLED=true`, run Playwright performance audit and persist browser metrics.

Invalid fetches are logged but not scored. This prevents fake scores for empty pages, placeholders, HTTP errors, timeout bodies, hosting default pages, and cold-start content.

### `security_service.py`

Runs a five-part audit:

- HTTP security headers, worth roughly 30 points.
- Content Security Policy quality, worth 20 points.
- CORS misconfiguration check, worth 15 points.
- Mixed content scan, worth 15 points.
- Malware and injection signature scan, worth 20 points.

The final output includes:

- `score`: normalized 0-100
- `grade`: `A`, `B`, `C`, `D`, or `F`
- category-level details
- flat `security_headers`
- flat `security_issues`
- `malware_flags`
- `cors_issues`
- `csp_issues`
- `mixed_content_detail`

### `alert_service.py`

Central alert policy and incident transition handler.

Public functions:

- `check_uptime_alerts()`
- `check_ssl_alerts()`
- `check_seo_alerts()`
- `handle_uptime_transition()`

Important behavior:

- Opens an incident when a site transitions into DOWN.
- Appends timeline events while a site remains DOWN.
- Resolves incident when the site leaves DOWN.
- Sends Teams notifications through `teams_service.py`.
- Applies cooldown based on `ALERT_COOLDOWN_MINUTES`.
- Rate-limits SSL expiry/expired alerts to once per day.

### `incident_service.py`

Handles incident root cause and timeline updates.

Root cause rules:

- Timeout text -> `TIMEOUT`
- DNS/name resolution text -> `DNS`
- HTTP 5xx -> `SERVER`
- HTTP 4xx -> `CLIENT`
- Connection refused/connect error -> `CONNECTION`
- Else -> `UNKNOWN`

### `teams_service.py`

Sends Adaptive Card payloads to `TEAMS_WEBHOOK_URL` using HTTPX.

### `analytics_service.py`

Builds read-only analytics:

- uptime trend from daily uptime summaries
- SEO trend from daily SEO summaries
- latency distribution from raw uptime logs
- average response time in milliseconds
- total incidents in the period

The `days` parameter is clamped to 1-90 days.

### `summary_service.py`

Creates daily rollups for uptime, SSL, and SEO.

Default target date is yesterday. Each summary is upserted per site/date.

### `retention_service.py`

Deletes old raw data after summary backfill.

Deletes:

- old uptime logs
- old SSL logs
- old SEO logs
- old resolved incidents
- old alert history

Open incidents are preserved.

### `report_service.py`

Generates a site-level JSON report with:

- site identity
- current status
- latest uptime/SSL/SEO logs
- recent histories
- intervals and next check timestamps

## Route and Request Flow Details

### API and Authentication

- `csrf.exempt(api_bp)` is used so JSON API routes can be called by clients without CSRF tokens.
- `_effective_user_id()` returns the logged-in `user_id` from the session; unauthenticated requests are rejected by `login_required`.
- `_owned_sites_query()` restricts site queries to the effective user.
- `_get_owned_site_or_404(site_id)` enforces ownership and returns 404 for unauthorized access.

### Web route flow

- `dashboard()` loads all owned sites and recent logs, builds metrics using `_build_dashboard_metrics()`, and renders `dashboard.html`.
- `site_detail(site_id)` loads the site, recent uptime/SSL/SEO logs, incidents, and analytics payload via `get_site_analytics()` before rendering `site_detail.html`.
- `download_report(site_id)` calls `generate_site_report()` and returns file content in JSON, CSV, or PDF.
- `create_site()` handles form submission, validates the URL, creates the site, initializes monitoring state, and queues initial checks.
- `run_check(site_id, check_type)` queues manual checks from the UI for `uptime`, `ssl`, `seo`, `security`, or `all`.
- `site_analytics(site_id)` renders analytics details and passes the `analytics` payload to `site_analytics.html`.

### JSON API route flow

- `register()` and `login()` create and verify users, storing `user_id` and `user_email` in the Flask session.
- `logout()` clears the session.
- `add_site()` validates JSON payload, normalizes URL, creates a `Site`, calls `prepare_site()`, and queues uptime/ssl/seo/security tasks.
- `list_sites()` returns owned site summaries and supports `since` filtering.
- `get_site(site_id)` returns the site plus latest uptime/SSL/SEO values and lighthouse payload.
- `delete_site(site_id)` removes the site and associated records.
- `update_site(site_id)` updates allowed interval settings and refreshes the next due check timestamp.
- `run_all_checks(site_id)` queues all eligible checks while honoring SEO cooldown rules.
- History endpoints return raw logs for uptime, SSL, and SEO.
- `uptime_summary(site_id)` returns daily uptime summaries.
- Check endpoints queue individual tasks and respond with queue status.
- Diagnostic endpoints provide recent logs, broken link summaries, technology stack reports, lighthouse/CWV data, and security audit results.
- Incident endpoints return incident details and lists filtered by site.

### Background check dispatch

- API and web routes do not perform checks directly; they queue Celery tasks using `_safe_delay()`.
- `_safe_delay()` returns `queued` or `queue_failed` to indicate whether the Celery task was successfully enqueued.

### Result and state propagation

- Each Celery task updates the `Site` record with detailed status fields and denormalized summary values.
- The `Site` model stores the latest health snapshot for quick dashboard rendering.
- `refresh_app_status()` recomputes `app_status` from individual check states and processing flags.

## Worker and Scheduling Logic

File: `app/workers/tasks.py`

Celery is configured with Redis broker/result backend from `Config`. On Windows, the worker pool is `solo`; on Linux/Mac, the default is `prefork`.

### Scheduled Beat Jobs

| Job | Task | Schedule |
| --- | --- | --- |
| Due uptime checks | `tasks.run_due_uptime_checks` | every 30 seconds |
| Due SSL checks | `tasks.run_due_ssl_checks` | hourly at minute 0 |
| Due SEO checks | `tasks.run_due_seo_checks` | hourly at minute 5 |
| Due security checks | `tasks.run_due_security_checks` | hourly at minute 10 |
| Due DNS checks | `tasks.run_due_dns_checks` | every 60 seconds |
| Stuck task rescue | `tasks.run_zombie_rescue` | every 300 seconds |
| Daily summaries | `tasks.run_daily_summary` | 00:05 UTC |
| Data retention | `tasks.run_retention_cycle` | 03:00 UTC |

### Task Locking

`acquire_check_lock(site_id, check_type)` performs a database update only when the current status is not already `running`. This prevents duplicate workers from running the same check type for the same site at the same time.

Lock fields:

- `uptime_status`, `uptime_started_at`
- `ssl_status`, `ssl_started_at`
- `seo_status`, `seo_started_at`
- `dns_status`, `dns_started_at`
- `last_started_at`
- `is_processing`
- `app_status`

`release_check_lock(site, check_type)` clears the started timestamp and refreshes aggregate app state.

### Stuck Task Rescue

`run_zombie_rescue_task()` marks old running checks as failed:

- uptime running longer than 10 minutes
- SSL running longer than 30 minutes
- SEO running longer than 90 minutes
- DNS running longer than 5 minutes

## SEO Logic

### Fetch Strategy

File: `app/utils/hybrid_fetch.py`

The SEO flow uses `fetch_html_for_seo(url)`:

1. Try HTTPX with a realistic browser user agent.
2. Check whether the response needs browser rendering.
3. If needed, use Playwright headless Chromium.
4. If Playwright fails, return the HTTP result with `render_mode="HTTP_BROWSER_FAILED"`.

Browser fallback triggers include:

- network error with no HTML
- empty response body
- HTTP status >= 400
- page smaller than the real-content threshold
- bot protection signatures
- placeholder/default hosting signatures

Render modes:

- `HTTP`
- `BROWSER`
- `HTTP_BROWSER_FAILED`

### Fetch Validation

File: `app/utils/seo_validator.py`

Validation ensures content is meaningful before scoring. Invalid content is saved with:

- `fetch_valid=false`
- `fetch_status`
- `invalidation_reason`
- HTML preview
- page size

Invalid fetches do not receive a normal SEO score.

### Parser

File: `app/utils/parser.py`

`parse_seo_intelligence()` extracts:

- title and title length
- meta description and length
- heading counts and H1 list
- word count and top keywords
- image count and missing alt count
- internal/external links
- canonical URL
- favicon
- hreflang
- robots meta
- HTML lang
- JS/CSS blocking counts
- viewport/mobile friendliness
- mixed content counts
- page size

### Scoring

File: `app/utils/seo_engine.py`

SEO score is 0-100 with these weighted categories:

| Category | Internal score inputs | Weight |
| --- | --- | --- |
| On-page | title presence/range, meta description presence/range, H1 presence | 40% |
| Technical | robots, sitemap, canonical, lang, noindex absence | 25% |
| Content | word count threshold, heading hierarchy, image alt coverage | 15% |
| Performance | TTFB, page size, blocking JS/CSS | 10% |
| Security/mobile | HTTPS redirect, viewport, no mixed content | 10% |

Status thresholds:

- `GOOD`: score >= 80
- `FAIR`: score >= 60
- `POOR`: score < 60

### Core Web Vitals

There are two performance paths:

1. `app/utils/cwv_estimator.py`: fast server-side estimates for LCP, FID, and CLS.
2. `app/utils/lighthouse_runner.py`: real browser metrics through Playwright Performance APIs when `LIGHTHOUSE_ENABLED=true`.

Playwright metrics:

- LCP
- FCP
- TBT
- CLS
- TTFB
- TTI
- Speed Index proxy
- page load time
- weighted performance score

Ratings:

- `good`
- `needs_improvement`
- `poor`
- `unknown`

### Technology Profiling

File: `app/utils/tech_profiler.py`

The profiler detects technologies from headers and HTML. It returns a grouped `detected` object and a flat list. The SEO service compares the current flat list with the previous valid SEO scan and stores `tech_diff` with added/removed/unchanged technologies.

### Broken Links

File: `app/utils/broken_link_checker.py`

The link checker:

- extracts links from anchors/resources
- normalizes against the base URL
- avoids unsupported schemes
- checks unique links
- tries HEAD and falls back to GET
- stores total checked count and broken link details

## Security Logic

Security runs inside the SEO check so the page HTML and headers are reused.

### Header Checks

Important headers:

- `Strict-Transport-Security`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `X-XSS-Protection`
- `Referrer-Policy`
- `Permissions-Policy`

HSTS can receive extra credit for long `max-age` and `includeSubDomains`.

### CSP Checks

The CSP audit checks whether a policy exists and whether `script-src` allows:

- `unsafe-inline`
- `unsafe-eval`
- wildcard sources

### CORS Checks

The CORS audit classifies:

- no CORS exposure
- wildcard public CORS
- wildcard with credentials
- null origin
- specific origin
- dangerous methods exposed to wildcard origins

### Mixed Content Checks

The scanner counts HTTP resources:

- scripts
- images
- iframes
- stylesheets
- fonts/inline URL references
- other embedded resources

### Malware and Injection Checks

The malware scanner flags suspicious signatures such as:

- obfuscated eval/base64 patterns
- suspicious external script paths
- hidden iframes
- crypto-miner references
- document/window redirect patterns
- JavaScript obfuscation patterns

High severity findings can force the malware category score to zero.

## Uptime, SSL, Incidents, and Alerts

### Uptime Classification

Uptime checks use:

- `DOWN` when request fails or HTTP result is not up.
- `DEGRADED` when reachable but response time exceeds `RESPONSE_TIME_THRESHOLD`.
- `UP` when reachable and within threshold.

### Incident State Machine

```text
PENDING/UP/DEGRADED
        |
        | current check is DOWN
        v
OPEN incident
        |
        | later checks are still DOWN
        v
append timeline events
        |
        | later check is UP or DEGRADED
        v
RESOLVED incident
```

### Alert Events

Alert event types include:

- `DOWN`
- `RECOVERY`
- `SSL_INVALID`
- `SSL_EXPIRY_WARNING`
- `SSL_EXPIRED`
- `DNS_HIJACK`
- `SEO_REGRESSION`

Every alert attempt is saved in `alert_history`, even if delivery fails.

## API Reference

All API routes live in `app/api/routes.py` and are registered under `/api`.

### Auth

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create user and start session. |
| POST | `/api/auth/login` | Authenticate user and start session. |
| POST | `/api/auth/logout` | Clear current session. |

### Sites

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/sites` | Add site and queue uptime/SSL/SEO checks. |
| GET | `/api/sites` | List current user's sites. Supports `?since=<iso8601>`. |
| GET | `/api/sites/<site_id>` | Get site plus latest uptime/SSL/SEO data. |
| DELETE | `/api/sites/<site_id>` | Delete site and cascaded logs. |
| GET | `/api/site/<site_id>/status` | Get current site status snapshot. |

### Check Dispatch

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/sites/<site_id>/check` | Queue uptime, SSL, and SEO checks. |
| GET | `/api/check/<site_id>` | Queue uptime check. |
| GET | `/api/check-ssl/<site_id>` | Queue SSL check. |
| GET | `/api/check-seo/<site_id>` | Queue SEO check, respecting cooldown. |
| GET | `/api/check-dns/<site_id>` | Queue DNS check. |

### Histories and Summaries

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/sites/<site_id>/history/uptime?days=7` | Recent uptime logs. |
| GET | `/api/sites/<site_id>/history/ssl?limit=10` | Recent SSL logs. |
| GET | `/api/sites/<site_id>/history/seo?limit=5` | Recent SEO logs. |
| GET | `/api/sites/<site_id>/history/dns?limit=10` | Recent DNS logs. |
| GET | `/api/sites/<site_id>/uptime-summary?days=30` | Daily uptime summaries. |
| GET | `/api/logs/<site_id>` | Last 10 uptime logs. |
| GET | `/api/seo-logs/<site_id>` | Last 10 SEO logs. |

### SEO Intelligence

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/sites/<site_id>/broken-links` | Latest valid SEO broken-link report. |
| GET | `/api/sites/<site_id>/tech-stack` | Latest valid technology profile. |
| GET | `/api/sites/<site_id>/lighthouse` | Latest valid Playwright performance audit. |
| GET | `/api/sites/<site_id>/security` | Latest valid security audit. |
| GET | `/api/sites/<site_id>/dns` | Latest valid DNS resolution report. |

### Analytics and Incidents

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/sites/<site_id>/analytics?days=30` | Trend analytics for a site. |
| GET | `/api/sites/<site_id>/incidents?status=OPEN&limit=20` | List site incidents. |
| GET | `/api/incidents/<incident_id>` | Incident detail with timeline and root cause. |

## Web UI

Web routes are also defined in `app/api/routes.py`, but registered without the `/api` prefix.

| Method | Path | Template/Action |
| --- | --- | --- |
| GET | `/` | Dashboard using `app/templates/dashboard.html`. |
| GET | `/site/<site_id>` | Site detail using `app/templates/site_detail.html`. |
| GET | `/site/<site_id>/download-report` | Download JSON site report. |
| POST | `/sites/new` | Add a site from web form. |
| POST | `/site/<site_id>/run/<check_type>` | Queue `uptime`, `ssl`, `seo`, or `all`. |

Templates:

- `base.html`: shared layout, topbar, flash messages.
- `dashboard.html`: fleet overview, add-site form, site cards, recent logs.
- `site_detail.html`: individual site history, metrics, analytics, incidents, SEO data.

Static assets:

- `app/static/dashboard.css`: custom dark UI theme and components.

## File and Folder Guide

```text
.
|-- README.md
|-- requirements.txt
|-- run.py
|-- alembic.ini
|-- .env.example
|-- app/
|   |-- __init__.py
|   |-- extensions.py
|   |-- api/
|   |   `-- routes.py
|   |-- config/
|   |   `-- settings.py
|   |-- models/
|   |   |-- __init__.py
|   |   |-- alert_history.py
|   |   |-- dns_log.py
|   |   |-- daily_ssl_summary.py
|   |   |-- daily_uptime_summary.py
|   |   |-- incident.py
|   |   |-- seo_log.py
|   |   |-- site.py
|   |   |-- ssl_log.py
|   |   |-- uptime_log.py
|   |   `-- user.py
|   |-- services/
|   |   |-- alert_service.py
|   |   |-- analytics_service.py
|   |   |-- incident_service.py
|   |   |-- monitor_service.py
|   |   |-- monitoring_service.py
|   |   |-- report_service.py
|   |   |-- retention_service.py
|   |   |-- security_service.py
|   |   |-- seo_service.py
|   |   |-- ssl_service.py
|   |   |-- summary_service.py
|   |   `-- teams_service.py
|   |-- utils/
|   |   |-- broken_link_checker.py
|   |   |-- cwv_estimator.py
|   |   |-- http.py
|   |   |-- hybrid_fetch.py
|   |   |-- lighthouse_runner.py
|   |   |-- parser.py
|   |   |-- seo_engine.py
|   |   |-- seo_validator.py
|   |   |-- tech_profiler.py
|   |   |-- time.py
|   |   `-- urls.py
|   |-- workers/
|   |   `-- tasks.py
|   |-- templates/
|   |   |-- base.html
|   |   |-- dashboard.html
|   |   `-- site_detail.html
|   `-- static/
|       `-- dashboard.css
|-- migrations/
|   |-- env.py
|   `-- versions/
|       |-- 20260430_add_seo_fetch_validation_fields.py
|       |-- 20260430_add_cwv_tech_broken_links.py
|       |-- 20260430_add_hybrid_fetch_columns.py
|       |-- 20260430_add_incident_rca_and_security.py
|       |-- 20260430_expand_security_scanning_columns.py
|       `-- 20260501_add_playwright_cwv_columns.py
`-- tests/
    |-- test_lighthouse_runner.py
    |-- test_security_service.py
    |-- test_seo_cooldown.py
    |-- test_seo_guards.py
    |-- test_seo_service.py
    `-- test_seo_validator.py
```

### Important Files

| File | Responsibility |
| --- | --- |
| `run.py` | Creates the Flask app and starts development server. |
| `app/__init__.py` | Application factory, DB setup, CSRF setup, blueprint registration, SQLite fallback. |
| `app/extensions.py` | Shared `db = SQLAlchemy()` instance. |
| `app/config/settings.py` | All central configuration and Celery Beat schedule. |
| `app/api/routes.py` | JSON API and web routes. |
| `app/workers/tasks.py` | Celery app, task locking, due dispatch, check tasks, summaries, retention, rescue. |
| `app/services/monitor_service.py` | Uptime check execution. |
| `app/services/ssl_service.py` | SSL certificate inspection. |
| `app/services/seo_service.py` | Full SEO/security/performance/link/tech orchestration. |
| `app/services/security_service.py` | Security score engine. |
| `app/services/dns_service.py` | DNS resolution and hijacking detection. |
| `app/services/alert_service.py` | Alert and incident transition policy. |
| `app/services/teams_service.py` | Teams webhook transport. |
| `app/services/analytics_service.py` | Trend analytics. |
| `app/services/report_service.py` | Downloadable JSON report generation. |
| `app/services/summary_service.py` | Daily aggregate summary creation. |
| `app/services/retention_service.py` | Summary backfill and old raw-data deletion. |
| `app/utils/http.py` | Shared HTTP fetch helper with TTFB support. |
| `app/utils/hybrid_fetch.py` | HTTP plus Playwright fallback for SEO HTML. |
| `app/utils/lighthouse_runner.py` | Playwright browser performance metrics. |
| `app/utils/parser.py` | HTML SEO signal extraction. |
| `app/utils/seo_engine.py` | SEO scoring and recommendations. |
| `app/utils/seo_validator.py` | Fetch validity guardrails. |
| `app/utils/tech_profiler.py` | Technology detection and diffing. |
| `app/utils/broken_link_checker.py` | Link extraction and status checking. |
| `app/utils/cwv_estimator.py` | Server-side Core Web Vitals estimates. |
| `app/utils/time.py` | UTC helpers. |
| `app/utils/urls.py` | URL normalization. |

## Migrations

Alembic is configured by `alembic.ini` and `migrations/env.py`.

Migration scripts currently cover:

- SEO fetch validation fields.
- Core Web Vitals, technology stack, and broken-link columns.
- Hybrid fetch metadata.
- Incident root cause and security fields.
- Expanded security scanning fields.
- Playwright Lighthouse/Core Web Vitals fields.
- Security fields added to site model.
- DNS monitoring with logs and site fields.

Use:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Development note: `create_app()` also calls `db.create_all()` to make local setup forgiving, but migrations remain the correct path for schema evolution.

## Tests

The test suite focuses on the riskier logic:

| Test file | Coverage |
| --- | --- |
| `tests/test_auth.py` | Registration, login, logout, session behavior, API auth guard, user-isolated site listing, and cross-user 404 behavior. |
| `tests/test_dns_service.py` | DNS resolution, IP tracking, nameserver monitoring, MX record checking, and hijacking detection. |
| `tests/test_lighthouse_runner.py` | Playwright metric mapping, ratings, scoring, timeout/error behavior. |
| `tests/test_security_service.py` | Security header checks, CSP, CORS, mixed content, malware, grade integration. |
| `tests/test_seo_cooldown.py` | Post-recovery SEO cooldown logic. |
| `tests/test_seo_guards.py` | Fetch guardrails and scoring preconditions. |
| `tests/test_seo_service.py` | SEO service invalid fetch behavior. |
| `tests/test_seo_validator.py` | Empty/tiny/placeholder/error fetch validation. |

Run all tests:

```powershell
pytest
```

Run a focused file:

```powershell
pytest tests/test_security_service.py -v
```

## Contributing

To contribute to Website Monitor:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Make changes and ensure tests pass.
4. Add tests for new functionality.
5. Submit a pull request with a clear description.

Guidelines:

- Follow PEP 8 for Python code.
- Add docstrings to new functions.
- Update the README if adding new features.
- Ensure compatibility with Python 3.12+.

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Recent Implementation Notes

### User isolation and authentication hardening

The app now enforces full session-based user isolation for both web and JSON API routes:

- `login_required` protects all non-auth web/API routes and returns JSON `401` for unauthenticated API requests.
- Site access uses the logged-in `session["user_id"]` ownership boundary, so guessing another user's integer `site_id` returns `404`.
- API auth endpoints are:
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
- Web auth endpoints are:
  - `GET/POST /register`
  - `GET/POST /login`
  - `POST /logout`
- Email is the user identity. Emails are lowercased and stripped before lookup/creation.
- Registration rejects duplicate emails with `An account with this email already exists`.
- Login uses the same error message for unknown email and wrong password: `Invalid email or password`.
- Inactive users are blocked with `This account has been deactivated`.
- Sessions store both `session["user_id"]` and `session["user_email"]`.
- `base.html` shows the logged-in user's email and uses a POST Sign Out form with CSRF protection.
- `login.html` and `register.html` were added for the web auth flow, including CSRF tokens and client-side password confirmation.

### Debug user behavior

The old debug fallback user bypass was removed. Debug mode no longer silently authenticates requests as `local@website-monitor.internal`.

When `FLASK_DEBUG=true`, the app only seeds a real login user if the `users` table is empty:

- Email: `dev@localhost.test`
- Password: `devpassword123`

After that, normal login is still required.

### Session security

The Flask session configuration now includes:

- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = "Lax"`
- `PERMANENT_SESSION_LIFETIME = 86400`
- `SESSION_COOKIE_SECURE = True` outside debug/testing

### Migration status

No auth migration was needed for this implementation because the existing `User` model already has:

- `id`
- `email`
- `password_hash`
- `created_at`
- `is_active`

The existing `Site.user_id` foreign key was also already present.

### Local data repair performed

The existing local SQLite data in `instance/website_monitor.db` had 8 old sites owned by `local@website-monitor.internal`. Those sites were reassigned to:

- `vraj9081354565@gmail.com`

This was a local data repair only; no model or migration change was required.

### Verification

The full test suite was run after the auth changes:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

Result:

```text
106 passed
```

## Operational Notes

- Redis must be running for Celery dispatch to work.
- If Celery is unavailable, web/API site creation can still create records, but queued checks will report `queue_failed`.
- The JSON API blueprint is CSRF-exempt because it uses session auth; web form routes remain CSRF-protected.
- Debug mode never bypasses login; it only seeds `dev@localhost.test` / `devpassword123` when the user table is empty.
- Per-site uniqueness is enforced by `(user_id, normalized_url)`.
- The app stores timestamps in UTC and normalizes datetimes through `app/utils/time.py`.
- Relative SQLite paths are checked for writability; if SQLite is unusable, the app can fall back to in-memory SQLite to avoid hard startup failure.
- `LIGHTHOUSE_ENABLED=true` requires Playwright and Chromium. Disable it on small servers or environments where browser automation is unavailable.
- Teams alert failures are recorded in `alert_history` and do not prevent check logs from being saved.
- The SEO score intentionally refuses to score tiny/invalid pages so operational incidents do not pollute SEO trend data.
- DNS monitoring runs every 60 seconds and can detect IP address changes and nameserver modifications.
- DNS hijacking alerts are triggered when resolved IPs differ from expected baseline IPs.
