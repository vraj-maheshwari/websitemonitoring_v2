# WebMonitor — SaaS Website Monitoring & SEO Intelligence Platform

A production-grade monitoring platform that continuously tracks **uptime**, **SSL certificate health**, and **SEO quality** for any number of websites. Built with Flask, Celery, Redis, and SQLAlchemy.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Setup & Running](#setup--running)
5. [Environment Variables](#environment-variables)
6. [Architecture Overview](#architecture-overview)
7. [Data Models](#data-models)
8. [Check Flows — Step by Step](#check-flows--step-by-step)
9. [SEO Scoring System](#seo-scoring-system)
10. [Celery Tasks & Scheduling](#celery-tasks--scheduling)
11. [Alert System](#alert-system)
12. [API Reference](#api-reference)
13. [Web UI](#web-ui)
14. [State Machine](#state-machine)
15. [Data Retention & Aggregation](#data-retention--aggregation)

---

## What It Does

| Feature | Detail |
|---|---|
| Uptime monitoring | HTTP GET every 30–60 seconds, tracks status code, response time, TTFB |
| SSL monitoring | Checks certificate validity and days-to-expiry via raw socket/TLS |
| SEO auditing | Deep HTML scan with 30+ signals, 0–100 weighted score |
| Core Web Vitals | Server-side proxy estimates for LCP, FID, and CLS derived from real fetch signals |
| Technology profiler | Detects 40+ technologies (frameworks, CMS, CDN, analytics, servers) from HTML and headers |
| Broken link checker | Concurrent HEAD/GET check of all unique links on the page, reports 4xx/5xx |
| Alerting | Email on DOWN, RECOVERY, SSL expiry, SEO regression |
| Incident tracking | Opens/resolves incident records on status transitions |
| Daily summaries | Aggregates raw logs into daily rollups before deletion |
| JSON export | Download full site report as structured JSON |
| Real-time UI | Dashboard polls `/api/sites?since=` every 5 seconds |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | Flask 3.0 |
| ORM | SQLAlchemy 2.0 + Flask-SQLAlchemy 3.1 |
| Task queue | Celery 5.3 + Redis |
| HTTP client | HTTPX 0.26 (async-capable, streaming TTFB) |
| HTML parsing | BeautifulSoup4 + lxml |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Migrations | Alembic 1.18 |
| CSRF protection | Flask-WTF 1.2 |
| Templates | Jinja2 (server-side rendering) |
| Styling | Custom CSS design system (dark theme, 8px grid) |
| Testing | pytest 9.0 |

---

## Project Structure

```
.
├── run.py                          # Entry point — creates and runs Flask app
├── requirements.txt
├── .env                            # Environment variables (never commit)
├── alembic.ini
│
├── app/
│   ├── __init__.py                 # App factory: create_app(), CSRF, DB init
│   ├── extensions.py               # Shared db = SQLAlchemy() instance
│   │
│   ├── config/
│   │   └── settings.py             # All config from env vars (Config class)
│   │
│   ├── models/
│   │   ├── site.py                 # Core Site model — all check state lives here
│   │   ├── user.py                 # User auth (email + bcrypt hash)
│   │   ├── uptime_log.py           # One row per HTTP check
│   │   ├── ssl_log.py              # One row per SSL check
│   │   ├── seo_log.py              # One row per SEO audit (50+ columns)
│   │   ├── incident.py             # Downtime incident open/resolve records
│   │   ├── alert_history.py        # Every alert email sent, with delivery status
│   │   ├── site_notification.py    # Email recipients per site
│   │   ├── daily_uptime_summary.py # Daily rollup of uptime logs
│   │   ├── daily_ssl_summary.py    # Daily rollup of SSL logs
│   │   └── daily_seo_summary.py    # Daily rollup of SEO logs
│   │
│   ├── services/
│   │   ├── monitoring_service.py   # Scheduling, interval math, due-site queries
│   │   ├── monitor_service.py      # Uptime check execution
│   │   ├── ssl_service.py          # SSL certificate fetch and validation
│   │   ├── seo_service.py          # SEO audit orchestration + cooldown logic
│   │   ├── alert_service.py        # Alert dispatch, incident management, cooldowns
│   │   ├── email_service.py        # SMTP email sending
│   │   ├── report_service.py       # JSON report generation
│   │   ├── retention_service.py    # Log deletion with summary backfill
│   │   └── summary_service.py      # Daily aggregation for all three check types
│   │
│   ├── utils/
│   │   ├── http.py                 # fetch_url() with retry, streaming TTFB
│   │   ├── parser.py               # HTML → 50+ SEO signals (BeautifulSoup)
│   │   ├── seo_engine.py           # Weighted scoring algorithm (0–100)
│   │   ├── seo_validator.py        # Detects placeholder/empty pages
│   │   ├── tech_profiler.py        # Detects 40+ technologies from HTML + headers
│   │   ├── cwv_estimator.py        # Server-side LCP/FID/CLS proxy estimates
│   │   ├── broken_link_checker.py  # Concurrent link checker (HEAD → GET fallback)
│   │   ├── time.py                 # now_utc(), normalize() UTC helpers
│   │   └── urls.py                 # URL canonicalization and normalization
│   │
│   ├── workers/
│   │   └── tasks.py                # All Celery tasks + lock management
│   │
│   ├── api/
│   │   └── routes.py               # JSON API (api_bp) + Web routes (web_bp)
│   │
│   ├── templates/
│   │   ├── base.html               # Layout shell: topbar, flash messages
│   │   ├── dashboard.html          # Fleet overview page
│   │   └── site_detail.html        # Per-site audit report page
│   │
│   └── static/
│       └── dashboard.css           # Full design system (dark theme, components)
│
├── migrations/
│   ├── env.py
│   └── versions/                   # Alembic migration scripts
│
└── tests/
    ├── test_seo_cooldown.py
    ├── test_seo_guards.py
    ├── test_seo_service.py
    └── test_seo_validator.py
```

---

## Setup & Running

### 1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in values (see [Environment Variables](#environment-variables)).

### 3. Start Redis

```bash
redis-server
```

### 4. Run the Flask app

```bash
python run.py
```

The app creates all database tables automatically on first run via `db.create_all()`.

### 5. Start Celery worker

```bash
celery -A app.workers.tasks.celery worker --loglevel=info
```

### 6. Start Celery Beat scheduler

```bash
celery -A app.workers.tasks.celery beat --loglevel=info
```

### 7. Run tests

```bash
pytest tests/ -v
```

---

## Environment Variables

All config lives in `app/config/settings.py` and is loaded from `.env` via `python-dotenv`.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key` | Flask session signing |
| `FLASK_DEBUG` | `false` | Enables debug mode and dev user |
| `DATABASE_URL` | `sqlite:///website_monitor.db` | SQLAlchemy connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker and result backend |
| `RESPONSE_TIME_THRESHOLD` | `3.0` | Seconds above which uptime is DEGRADED |
| `SSL_EXPIRY_WARNING_DAYS` | `7` | Days before expiry to start alerting |
| `ALERT_COOLDOWN_MINUTES` | `15` | Minimum gap between repeat alerts |
| `LOG_RETENTION_DAYS` | `30` | Days to keep raw logs before deletion |
| `HTTP_VERIFY_SSL` | `true` | Whether to verify SSL on outbound requests |
| `SMTP_HOST` | `` | SMTP server for email alerts |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | `` | SMTP auth username |
| `SMTP_PASSWORD` | `` | SMTP auth password |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `SMTP_FROM_EMAIL` | `ALERT_EMAIL` | From address for alert emails |
| `ALERT_EMAIL` | `admin@example.com` | Fallback alert recipient |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Architecture Overview

```
Browser / API Client
        │
        ▼
  Flask (routes.py)
  ┌─────────────────────────────────────────┐
  │  web_bp  →  dashboard.html             │
  │             site_detail.html           │
  │  api_bp  →  JSON responses             │
  └─────────────────────────────────────────┘
        │ .delay() / .apply_async()
        ▼
  Redis (broker)
        │
        ▼
  Celery Worker (tasks.py)
  ┌─────────────────────────────────────────┐
  │  run_uptime_check_task                 │
  │  run_ssl_check_task                    │
  │  run_seo_check_task                    │
  └─────────────────────────────────────────┘
        │                    │
        ▼                    ▼
  monitor_service.py    ssl_service.py
  seo_service.py
        │
        ▼
  SQLAlchemy ORM → SQLite / PostgreSQL
        │
        ▼
  alert_service.py → email_service.py → SMTP
```

**Celery Beat** runs on a separate process and dispatches tasks on schedule:

```
Every 30s  → run_due_uptime_checks  → dispatches run_uptime_check_task per site
Every 1h   → run_due_ssl_checks     → dispatches run_ssl_check_task per site
Every 5m   → run_due_seo_checks     → dispatches run_seo_check_task per site
Every 5m   → run_zombie_rescue      → resets stuck "running" tasks
00:05 UTC  → run_daily_summary      → aggregates logs into daily summaries
03:00 UTC  → run_retention_cycle    → deletes old logs (after backfilling summaries)
```

---

## Data Models

### Site

The central model. Every check type writes its results back to the site row for fast dashboard reads.

```
sites
├── id, user_id, name, url, normalized_url
├── check_interval, uptime_check_interval, ssl_check_interval, seo_check_interval
│
├── Scheduling
│   ├── next_uptime_check_at, next_ssl_check_at, next_seo_check_at
│   ├── last_uptime_check_at, last_ssl_check_at, last_seo_check_at
│   └── next_check_at  (min of the three above)
│
├── Aggregate Status
│   ├── app_status       pending | checking | ready | partial
│   ├── uptime_status    pending | running | done | failed
│   ├── ssl_status       pending | running | done | failed
│   └── seo_status       pending | running | done | failed
│
├── Uptime Metrics (denormalized from latest UptimeLog)
│   ├── current_status   UP | DOWN | DEGRADED | PENDING
│   ├── last_status_code, last_response_time, last_ttfb
│   ├── last_error_message
│   └── incident_opened_at, last_incident_resolved_at
│
├── SSL Metrics (denormalized from latest SSLLog)
│   ├── ssl_state        VALID | EXPIRING | EXPIRED | ERROR | UNKNOWN
│   ├── ssl_issuer, ssl_expiry_date, ssl_days_remaining
│   └── ssl_last_error
│
└── SEO Metrics (denormalized from latest SEOLog)
    ├── seo_state        GOOD | FAIR | POOR | UNKNOWN
    ├── seo_score        0–100
    ├── last_seo_fetch_valid
    ├── last_downtime_ended_at  (used for cooldown logic)
    └── seo_last_error
```

### UptimeLog

One row per HTTP check. Stores raw result, never aggregated in place.

```
uptime_logs
├── site_id, status_code, response_time (s), ttfb (s)
├── is_up (bool), status (UP|DOWN|DEGRADED)
├── error_message, checked_at
```

### SSLLog

One row per SSL check.

```
ssl_logs
├── site_id, expiry_date, days_remaining
├── is_valid (bool), state (VALID|EXPIRING|EXPIRED|ERROR)
├── issuer, error_message, checked_at
```

### SEOLog

One row per SEO audit. Stores all 50+ signals plus the computed score.

```
seo_logs
├── site_id, score (0–100), status (GOOD|FAIR|POOR|UNKNOWN)
│
├── On-Page: title, title_length, meta_description, meta_length
│            h1_count, h2_count, h3_count, word_count, keyword_density
│
├── Content:  image_count, missing_alt_count
│             internal_link_count, external_link_count
│
├── Technical: has_robots, has_sitemap, canonical, has_favicon
│              has_hreflang, robots_meta, html_lang
│
├── Performance: page_size_kb, js_blocking_count, css_blocking_count, ttfb
│
├── Mobile/Security: has_viewport, mobile_friendly, https_redirect, mixed_content_count
│
├── Intelligence: score_breakdown (JSON), signals (JSON)
│                 issues (JSON list), recommendations (JSON list)
│
├── Fetch Validation: fetch_valid, fetch_status, fetch_html_preview
│                     fetch_page_size_kb, invalidation_reason, error_message
│
├── Core Web Vitals (proxy estimates):
│   cwv_lcp_estimate_s, cwv_lcp_rating       — Largest Contentful Paint
│   cwv_fid_estimate_ms, cwv_fid_rating      — First Input Delay
│   cwv_cls_estimate, cwv_cls_rating         — Cumulative Layout Shift
│   cwv_data (JSON)                          — full estimates dict
│
├── Technology Profiler:
│   tech_stack (JSON)   — detected technologies grouped by category
│   tech_flat  (JSON)   — flat list of technology names
│   tech_diff  (JSON)   — {added, removed, unchanged} vs previous scan
│
└── Broken Links:
    broken_links (JSON)  — full report with each broken URL, status, type
    broken_link_count    — count of broken links found
    links_checked        — count of unique URLs checked
```

### Incident

Tracks downtime events. Opened when site transitions to DOWN, resolved on recovery.

```
incidents
├── site_id, status (OPEN|RESOLVED)
├── opened_at, resolved_at
├── opened_status_code, opened_response_time, opened_error_message
└── resolved_status_code, resolved_response_time, resolved_error_message
```

### AlertHistory

Every alert email attempted, with delivery outcome.

```
alert_history
├── site_id, incident_id (nullable)
├── event_type  DOWN | RECOVERY | SSL_INVALID | SSL_EXPIRY_WARNING | SSL_EXPIRED | SEO_REGRESSION
├── recipient, subject, body
├── delivery_status  PENDING | SENT | FAILED
└── error_message, sent_at
```

### Daily Summaries

Three tables aggregate raw logs before deletion:

```
daily_uptime_summaries  → total_checks, up_checks, down_checks, degraded_checks,
                          uptime_percentage, avg_response_time, avg_ttfb, outage_count

daily_ssl_summaries     → total_checks, valid_count, avg_days_remaining

daily_seo_summaries     → total_checks, avg_score, min_score, max_score
```

---

## Check Flows — Step by Step

### Uptime Check Flow

```
Celery Beat (every 30s)
  └─ run_due_uptime_checks()
       └─ get_due_site_ids("uptime")   ← sites where next_uptime_check_at <= now
            └─ run_uptime_check_task.delay(site_id)
                 │
                 ├─ acquire_check_lock(site_id, "uptime")
                 │    └─ UPDATE sites SET uptime_status="running" WHERE uptime_status != "running"
                 │         returns False if already running (prevents duplicates)
                 │
                 ├─ monitor_service.run_uptime_check(site_id)
                 │    ├─ fetch_url(site.url, timeout=5.0)
                 │    │    ├─ GET request with up to 2 retries (1s, 2s delays)
                 │    │    └─ returns {status_code, response_time, ttfb, is_up, error}
                 │    │
                 │    ├─ Determine status:
                 │    │    is_up=False          → DOWN
                 │    │    response_time > 3.0s → DEGRADED
                 │    │    else                 → UP
                 │    │
                 │    ├─ Write UptimeLog row
                 │    ├─ Update site.current_status, last_response_time, last_ttfb
                 │    ├─ schedule_next_run(site, "uptime", checked_at)
                 │    │    └─ site.next_uptime_check_at = checked_at + uptime_check_interval
                 │    │
                 │    ├─ If DOWN→UP transition: set site.last_downtime_ended_at = now
                 │    │    (activates 120s SEO cooldown)
                 │    │
                 │    └─ alert_service.handle_uptime_transition(...)
                 │         ├─ DOWN transition  → _open_incident() + notify recipients
                 │         └─ UP transition    → _resolve_incident() + notify recipients
                 │
                 └─ release_check_lock(site, "uptime")
                      └─ site.refresh_app_status()
```

### SSL Check Flow

```
Celery Beat (every hour, at :00)
  └─ run_due_ssl_checks()
       └─ run_ssl_check_task.delay(site_id)
            │
            ├─ acquire_check_lock(site_id, "ssl")
            │
            ├─ ssl_service.run_ssl_check(site_id)
            │    ├─ _extract_hostname(site.url)  ← urlparse().hostname
            │    ├─ _fetch_certificate(hostname)
            │    │    ├─ socket.create_connection((hostname, 443), timeout=10)
            │    │    ├─ ssl.wrap_socket() → getpeercert()
            │    │    ├─ Parse notAfter → expiry_date (UTC-aware)
            │    │    └─ Extract issuer organizationName
            │    │
            │    ├─ days_remaining = (expiry - now).days
            │    ├─ state = VALID | EXPIRING (<14d) | EXPIRED (<0d) | ERROR
            │    ├─ Write SSLLog row
            │    ├─ Update site.ssl_state, ssl_days_remaining, ssl_expiry_date, ssl_issuer
            │    ├─ schedule_next_run(site, "ssl", checked_at)
            │    │
            │    └─ alert_service.check_ssl_alerts(...)
            │         ├─ is_valid=False → SSL_INVALID alert (immediate)
            │         └─ days_remaining <= SSL_EXPIRY_WARNING_DAYS
            │              → SSL_EXPIRY_WARNING or SSL_EXPIRED
            │                (both rate-limited to once per day)
            │
            └─ release_check_lock(site, "ssl")
```

### SEO Check Flow

```
Celery Beat (every 5 min, at :05)
  └─ run_due_seo_checks()
       └─ run_seo_check_task.delay(site_id)
            │
            ├─ should_skip_seo_for_cooldown(site)
            │    └─ If site recovered from DOWN < 120s ago → reschedule +120s, return early
            │         (prevents false POOR scores from cold-start placeholder pages)
            │
            ├─ acquire_check_lock(site_id, "seo")
            │
            └─ seo_service.run_seo_check(site, db.session)
                 │
                 ├─ fetch_url(site.url, timeout=25.0, stream_for_ttfb=True)
                 │    └─ Streaming GET: captures TTFB when first byte arrives
                 │
                 ├─ validate_seo_fetch(html, page_size_kb, status_code, error, url)
                 │    Checks (in order):
                 │    1. Fetch error with no HTML → fetch_status="error"
                 │    2. Empty response           → fetch_status="empty"
                 │    3. Page < 5 KB              → fetch_status="invalid_content"
                 │    4. HTTP status >= 400        → fetch_status="error"
                 │    5. Known placeholder text    → fetch_status="invalid_content"
                 │       (nginx default, "Account suspended", "Coming Soon", etc.)
                 │    If invalid → save SEOLog with fetch_valid=False, NO score
                 │
                 ├─ parse_seo_intelligence(html, site.url)
                 │    Extracts 50+ signals via BeautifulSoup:
                 │    title, meta description, H1–H6 counts, word count,
                 │    images/alt text, internal/external links, canonical,
                 │    robots.txt presence, sitemap.xml presence, viewport,
                 │    HTTPS redirect, mixed content, blocking JS/CSS, lang attr
                 │
                 ├─ _check_resource_exists(url, "/robots.txt")  ← HEAD request
                 ├─ _check_resource_exists(url, "/sitemap.xml") ← HEAD request
                 │
                 ├─ analyze_seo(signals)  ← scoring engine
                 │    (see SEO Scoring System section)
                 │
                 ├─ Capture old_score = site.seo_score  ← BEFORE updating
                 ├─ Save SEOLog row
                 ├─ Update site.seo_score, seo_state, last_seo_fetch_valid
                 ├─ schedule_next_run(site, "seo", checked_at)
                 │
                 └─ alert_service.check_seo_alerts(site, score, status, old_score=old_score)
                      └─ If score < old_score - 5 → SEO_REGRESSION alert
```

---

## SEO Scoring System

Each category is scored **0–100 internally**, then multiplied by its weight to contribute to the final score.

```
Final Score = (on_page × 0.40) + (technical × 0.25) + (content × 0.15)
            + (performance × 0.10) + (security_mobile × 0.10)
```

### On-Page (weight: 40%)

| Signal | Points |
|---|---|
| Title tag present | +20 |
| Title length 50–60 chars | +20 |
| Meta description present | +20 |
| Meta description 120–160 chars | +20 |
| Exactly one H1 tag | +20 |
| **Max** | **100** |

### Technical (weight: 25%)

| Signal | Points |
|---|---|
| robots.txt accessible | +25 |
| sitemap.xml accessible | +25 |
| Canonical URL set | +25 |
| HTML lang attribute set | +15 |
| No noindex in robots meta | +10 |
| **Max** | **100** |

### Content (weight: 15%)

| Signal | Points |
|---|---|
| Word count ≥ 300 | +40 |
| Logical heading hierarchy | +30 |
| Alt text coverage (proportional) | 0–30 |
| **Max** | **100** |

### Performance (weight: 10%)

| Signal | Points |
|---|---|
| TTFB < 0.8s | +50 |
| TTFB < 1.5s | +30 |
| Page size < 500 KB | +30 |
| Page size < 1000 KB | +15 |
| Zero blocking JS/CSS in `<head>` | +20 |
| ≤ 2 blocking resources | +10 |
| **Max** | **100** |

### Security + Mobile (weight: 10%)

| Signal | Points |
|---|---|
| HTTPS redirect enforced | +40 |
| Viewport meta tag present | +40 |
| No mixed HTTP content | +20 |
| **Max** | **100** |

### Score Grades

| Score | Grade | Status |
|---|---|---|
| 80–100 | Good | `GOOD` |
| 60–79 | Fair | `FAIR` |
| 0–59 | Poor | `POOR` |

### Fetch Validation

Before scoring, the fetched HTML is validated. If any check fails, `fetch_valid=False` is stored and **no score is generated**:

| Rule | Condition | fetch_status |
|---|---|---|
| Fetch error | Network/timeout error with no HTML | `error` / `timeout` |
| Empty response | HTML is empty or whitespace | `empty` |
| Page too small | Page < 5 KB | `invalid_content` |
| HTTP error | Status code ≥ 400 | `error` |
| Placeholder page | Matches known signatures (nginx default, "Account suspended", etc.) | `invalid_content` |

---

## Celery Tasks & Scheduling

### Beat Schedule

| Task | Schedule | Purpose |
|---|---|---|
| `run_due_uptime_checks` | Every 30s | Dispatch uptime checks for all due sites |
| `run_due_ssl_checks` | Every hour (:00) | Dispatch SSL checks for all due sites |
| `run_due_seo_checks` | Every hour (:05) | Dispatch SEO checks for all due sites |
| `run_zombie_rescue` | Every 5 min | Reset tasks stuck in "running" state |
| `run_daily_summary` | 00:05 UTC | Aggregate logs into daily summary tables |
| `run_retention_cycle` | 03:00 UTC | Delete old logs (after backfilling summaries) |

### Concurrency Lock

Every check task uses a database-level lock to prevent duplicate execution:

```python
acquire_check_lock(site_id, check_type)
  → UPDATE sites SET {type}_status="running"
    WHERE id=site_id AND {type}_status != "running"
  → Returns True only if exactly 1 row was updated
```

If the lock returns False (task already running), the new task exits immediately.

### Zombie Rescue

Tasks that get stuck in "running" are automatically reset:

| Check type | Timeout |
|---|---|
| Uptime | 10 minutes |
| SSL | 30 minutes |
| SEO | 90 minutes |

---

## Alert System

### Event Types

| Event | Trigger | Cooldown |
|---|---|---|
| `DOWN` | Site transitions from UP/DEGRADED to DOWN | Per-incident cooldown (15 min default) |
| `RECOVERY` | Site transitions from DOWN to UP/DEGRADED | Per-incident cooldown |
| `SSL_INVALID` | Certificate cannot be fetched or is invalid | Per-incident cooldown |
| `SSL_EXPIRY_WARNING` | Days remaining ≤ `SSL_EXPIRY_WARNING_DAYS` | Once per day |
| `SSL_EXPIRED` | Days remaining < 0 | Once per day |
| `SEO_REGRESSION` | Score drops > 5 points from previous valid scan | Per-incident cooldown |

### Alert Flow

```
alert_service.check_ssl_alerts() / handle_uptime_transition() / check_seo_alerts()
  │
  ├─ _send_alert()          ← logs to stdout (swap for SendGrid/Slack/PagerDuty)
  │
  └─ _notify_site()
       ├─ Query SiteNotification for active recipients
       ├─ Check _cooldown_active() — skip if alert sent recently
       ├─ Create AlertHistory row (PENDING)
       ├─ send_email(recipient, subject, body)
       └─ Update AlertHistory → SENT or FAILED
```

---

## API Reference

All JSON API routes are under `/api/`. CSRF is exempted for the API blueprint (uses session auth). Web form routes require a CSRF token.

### Authentication

| Method | Route | Body | Response |
|---|---|---|---|
| POST | `/api/auth/register` | `{email, password}` | `{message, user}` 201 |
| POST | `/api/auth/login` | `{email, password}` | `{message, user}` 200 |
| POST | `/api/auth/logout` | — | `{message}` 200 |

### Sites

| Method | Route | Description |
|---|---|---|
| POST | `/api/sites` | Add a site. Body: `{url, name?, check_interval?, uptime_check_interval?, ssl_check_interval?, seo_check_interval?, notification_emails?}` |
| GET | `/api/sites` | List all sites for current user. Query: `?since=<ISO8601>` for delta polling |
| GET | `/api/sites/<id>` | Get site with latest logs |
| DELETE | `/api/sites/<id>` | Delete site and all associated data |
| POST | `/api/sites/<id>/check` | Trigger all three checks immediately |

### History & Logs

| Method | Route | Description |
|---|---|---|
| GET | `/api/sites/<id>/history/uptime` | Uptime logs. Query: `?days=7` |
| GET | `/api/sites/<id>/history/ssl` | SSL logs. Query: `?limit=10` |
| GET | `/api/sites/<id>/history/seo` | SEO logs. Query: `?limit=5` |
| GET | `/api/sites/<id>/uptime-summary` | Daily uptime summaries. Query: `?days=30` |
| GET | `/api/logs/<id>` | Last 10 uptime logs |
| GET | `/api/seo-logs/<id>` | Last 10 SEO logs |
| GET | `/api/site/<id>/status` | Current site status dict |

### Manual Check Triggers

| Method | Route | Description |
|---|---|---|
| GET | `/api/check/<id>` | Queue uptime check |
| GET | `/api/check-ssl/<id>` | Queue SSL check |
| GET | `/api/check-seo/<id>` | Queue SEO check (respects cooldown) |

---

## Web UI

### Dashboard (`GET /`)

Rendered by `dashboard.html`. Data passed from `web.dashboard` route:

- `metrics` — `{monitored_sites, sites_up, sites_down, avg_response, health_score}`
- `site_cards` — all Site objects for current user
- `recent_uptime_logs` — last 12 uptime logs across all sites
- `recent_ssl_logs` — last 8 SSL logs
- `recent_seo_logs` — last 8 SEO logs

**Sections:**
1. Global status bar — fleet health %, status label, avg latency
2. Metric cards — Fleet Uptime, SSL Health, Avg SEO Score, Avg Latency
3. Active Issues panel — only shown when sites are DOWN or SSL expiring
4. Site cards grid — per-site mini-dashboard with 4 metrics
5. Add Monitor form — creates site and immediately queues all three checks
6. Intelligence Feed — recent anomalies (failed uptime checks)

The page polls `/api/sites?since=<timestamp>` every 5 seconds and reloads if any site was updated.

### Site Detail (`GET /site/<id>`)

Rendered by `site_detail.html`. Data passed:

- `site` — Site object
- `uptime_logs` — last 20 uptime logs
- `ssl_logs` — last 10 SSL logs
- `seo_logs` — last 10 SEO logs (first entry used as `report`)

**Sections:**
1. Detail header — site name, status pill, Export JSON and Run Full Audit buttons
2. Metric cards — Uptime Status, Response Time, SSL Certificate, SEO Score
3. Invalid fetch alert — shown when `fetch_valid=False`
4. Intelligence Breakdown card with 4 tabs:
   - **On-Page** — title, meta description, H1 count, heading structure, keywords
   - **Technical** — canonical, robots.txt, sitemap.xml, robots meta, lang, favicon, hreflang
   - **Content** — word count, images/alt text, internal/external links
   - **Perf & Mobile** — TTFB, page size, blocking resources, viewport, HTTPS, mixed content
5. Score bar + 5 category tiles (each shows raw score/100 and contribution to final score)
6. SEO scan history table
7. Sidebar: Top Fixes, Raw Signals, SSL Details, Uptime log mini-timeline

---

## State Machine

### app_status

```
                    ┌─────────────────────────────────────┐
                    │                                     │
  Site created  →  pending  →  checking  →  ready        │
                                    │                     │
                                    └──→  partial  ───────┘
                                         (any failed)
```

`refresh_app_status()` is called after every check completes:

| Condition | app_status |
|---|---|
| All three statuses are "pending" | `pending` |
| Any status is "running" | `checking` |
| All three are "done" | `ready` |
| Any is "failed" | `partial` |
| Mixed pending/done | `partial` |

### current_status (uptime)

```
PENDING → UP (first successful check)
UP      → DOWN (HTTP error or non-2xx/3xx)
UP      → DEGRADED (response_time > RESPONSE_TIME_THRESHOLD)
DOWN    → UP (successful check after downtime)
DEGRADED → UP (response time back below threshold)
```

### ssl_state

```
UNKNOWN → VALID (cert fetched, days_remaining >= 14)
VALID   → EXPIRING (days_remaining < 14)
EXPIRING → EXPIRED (days_remaining < 0)
any     → ERROR (socket/SSL exception)
```

---

## Data Retention & Aggregation

The retention cycle runs daily at 03:00 UTC:

```
run_retention_cycle()
  │
  ├─ cutoff = now - LOG_RETENTION_DAYS (default 30 days)
  │
  ├─ _backfill_summaries_before_cutoff(cutoff.date())
  │    ├─ _populate_daily_uptime_summary(date)
  │    │    └─ Aggregates UptimeLog → DailyUptimeSummary
  │    │       (total, up, down, degraded counts, avg response time, avg TTFB)
  │    ├─ _populate_daily_ssl_summary(date)
  │    │    └─ Aggregates SSLLog → DailySSLSummary
  │    │       (total checks, valid count, avg days remaining)
  │    └─ _populate_daily_seo_summary(date)
  │         └─ Aggregates SEOLog (fetch_valid=True only) → DailySEOSummary
  │            (total checks, avg/min/max score)
  │
  └─ DELETE UptimeLog, SSLLog, SEOLog, Incidents, AlertHistory WHERE checked_at < cutoff
```

The daily summary task also runs independently at 00:05 UTC to build summaries for the previous day, ensuring data is available even if retention hasn't run yet.

---

## Design System

`app/static/dashboard.css` implements a complete design system:

**Color palette:**
- `--green: #22c55e` — healthy, passing, good
- `--yellow: #f59e0b` — warning, moderate, expiring
- `--red: #ef4444` — critical, failing, down
- `--blue: #3b82f6` — informational, running, links
- `--bg: #080e1a` — page background
- `--surface: #0d1526` — card background
- `--surface-2: #111d30` — nested elements
- `--surface-3: #162038` — inputs, mini-tiles

**Component classes:**
- `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-sm`
- `.card`, `.card-sm`, `.card-lg`
- `.pill`, `.pill-green`, `.pill-yellow`, `.pill-red`, `.pill-blue`, `.pill-gray`
- `.dot`, `.dot-green`, `.dot-yellow`, `.dot-red`
- `.val-green`, `.val-yellow`, `.val-red`, `.val-muted`, `.val-blue`
- `.label`, `.muted`, `.small`, `.mono`, `.truncate`
- `.spinner` (CSS animation)
- `.score-tile`, `.bar-fill`, `.signal-row`, `.audit-item`, `.rec-item`
- `.tabs-nav`, `.tab-btn`, `.tab-content`


---

## Advanced SEO Features

### Core Web Vitals (Proxy Estimates)

Real Core Web Vitals require JavaScript execution in a browser. We provide **server-side proxy estimates** derived from measurable signals:

| Metric | Proxy Formula | Thresholds |
|---|---|---|
| **LCP** (Largest Contentful Paint) | TTFB + render_delay<br>render_delay = (page_size_kb / 1000 × 0.5) + (js_blocking × 0.08) + (css_blocking × 0.05) | Good: ≤2.5s<br>Needs work: ≤4.0s<br>Poor: >4.0s |
| **FID** (First Input Delay) | js_blocking_count × 80ms | Good: ≤100ms<br>Needs work: ≤300ms<br>Poor: >300ms |
| **CLS** (Cumulative Layout Shift) | missing_alt_count × 0.05<br>(images without alt often lack dimensions) | Good: ≤0.1<br>Needs work: ≤0.25<br>Poor: >0.25 |

Each estimate includes a plain-English note explaining what it's based on. The UI displays a clear disclaimer that these are not real browser measurements. For field data, use [Google PageSpeed Insights](https://pagespeed.web.dev/) or Chrome UX Report.

### Technology Profiler

Detects 40+ technologies from HTML source and HTTP response headers:

**Categories:**
- **JS Frameworks** — React, Next.js, Vue, Nuxt, Angular, Svelte, Ember, Alpine, jQuery, HTMX
- **CMS / Site Builders** — WordPress, Shopify, Wix, Squarespace, Webflow, Ghost, Drupal, Joomla, HubSpot
- **CDN / Hosting** — Cloudflare, Fastly, AWS CloudFront, Vercel, Netlify, GitHub Pages
- **Web Servers** — Nginx, Apache, Caddy, LiteSpeed, IIS
- **Analytics** — Google Analytics, Google Tag Manager, Plausible, Fathom, Hotjar, Mixpanel
- **CSS Frameworks** — Tailwind CSS, Bootstrap, Bulma, Foundation
- **Backend / Language** — PHP, Python/Django, Python/Flask, Ruby on Rails, Node.js/Express, ASP.NET

**Detection is passive** — no extra requests beyond the main page fetch. Each scan compares the current tech stack against the previous scan and reports:
- `added` — new technologies detected (e.g., "This site just started using React")
- `removed` — technologies no longer detected (e.g., "They switched from jQuery to React")
- `unchanged` — technologies present in both scans

### Broken Link Checker

Crawls all `<a href>` links found on the page and checks each one for HTTP errors:

**Features:**
- Concurrent checking via `ThreadPoolExecutor` (12 workers)
- Deduplicates URLs — 266 anchor tags → 184 unique URLs checked
- Uses HEAD first, falls back to GET if HEAD returns 405
- 8-second timeout per link
- Max 3 redirects per link
- Skips `mailto:`, `tel:`, `javascript:`, `data:`, `ftp:`, and fragment-only `#` links
- Checks up to 500 unique links per audit (configurable)

**Results grouped by:**
- Broken (4xx/5xx or connection error)
- OK (2xx/3xx)
- Internal vs external classification

Each broken link includes: URL, status code, error message, link type, and anchor text.

---
