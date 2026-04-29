# SaaS SEO Intelligence Engine — Full Architecture Analysis & Perfect Build Prompt

---

## 🔍 PART A: ANALYSIS — Flaws, Logic Mistakes & Flow Problems

---

### 1. Race Condition in Concurrent Guard (Critical Logic Bug)

The `is_processing` flag is a single global boolean on the Site model. But 3 tasks (uptime, ssl, seo) run in parallel. The flow shows:

- Task 1 reads `is_processing = False` → sets it `True` → starts
- Task 2 reads `is_processing = False` (before Task 1 writes) → also sets it `True`

This is a classic **check-then-act race condition** with no atomic lock. SQLite (dev) has no row-level locking; even PostgreSQL needs `SELECT FOR UPDATE` to make this safe. The README claims this prevents duplicate executions but the mechanism is broken.

**Fix needed:** Use database-level `SELECT FOR UPDATE` + transaction, or a Redis-based distributed lock (Redlock), not a simple boolean column.

---

### 2. `refresh_app_status()` Called Per-Task = Wrong Aggregate Logic

Each of the 3 tasks independently calls `refresh_app_status()` after finishing. The logic is:

- If all 3 = `done` → `READY`
- If any = `running` → `CHECKING`
- If any = `failed` → `FAILED`

But consider: Uptime finishes first. It calls `refresh_app_status()`. SSL and SEO are still `running`. So `app_status = CHECKING`. That's fine. But if SSL then fails and SEO is still running — SSL sets `app_status = FAILED`. Then SEO finishes and sets `app_status = READY` (because all are now `done`), **overwriting the FAILED state**. The final status is wrong.

**Fix needed:** The aggregate logic must correctly prioritize `failed` over `done`. If any task is `failed` and the rest are `done`, the final status should be `PARTIAL` or `FAILED`, not `READY`.

---

### 3. 1-Second HTTP Timeout Is Too Aggressive for SEO Fetching

Uptime checks correctly use a 1-second timeout — fast responses matter for uptime. But the SEO task uses the same `http.fetch_url()` utility with the same 1-second timeout to download full HTML pages. Large pages (news sites, e-commerce) routinely take 2–5 seconds. This causes false SEO failures on slow-but-valid pages.

**Fix needed:** The HTTP utility must accept a configurable timeout. Uptime uses 1s; SEO should default to 10–15s.

---

### 4. TTFB Is Measured Wrong for SEO

The SEO flow fetches the full HTML body for parsing, then records that fetch time as TTFB. But TTFB is *Time to First Byte* — the time until the first byte of the response arrives, not the total download time. By measuring full-response time, large pages will always show inflated TTFB scores that penalize them incorrectly.

**Fix needed:** Use `httpx`'s streaming response and capture the timestamp when the first byte of the response body is received, separate from total download time.

---

### 5. Celery Beat Triggers Retention Every 24h — But Zombies Need Rescue Every Few Minutes

Retention identifies "zombie" tasks using `last_started_at > 30 min timeout`. But Celery Beat only runs the retention cycle every **24 hours**. A zombie task created at 00:01 won't be rescued until 00:01 the next day — that's 23h 59min of a stuck site showing `CHECKING`.

**Fix needed:** The rescue/zombie-detection cycle should run every 5–10 minutes, completely separate from the data purge cycle (which can stay at 24h).

---

### 6. `check_interval` Is a Single Field But 3 Checks Have Different Natural Intervals

The schema has one `check_interval` field but the README documents three completely different default intervals: uptime=60s, SSL=24h, SEO=7d. Yet the model only stores one integer. This means either the per-check intervals are hardcoded (not configurable per-site), or one interval value is being reused wrongly for all three checks.

**Fix needed:** The Site model needs `uptime_check_interval`, `ssl_check_interval`, and `seo_check_interval` as separate fields, each with their own defaults and per-site overrides.

---

### 7. SEO Alert Regression Logic Has No Baseline Handling

The SEO alert fires when `current_score < previous_score - 5`. But on the *first ever* SEO check, there is no previous log. The code likely throws a `NoneType` error or silently skips alerting. The README doesn't document this edge case at all.

**Fix needed:** Explicitly handle the first-run case: if no previous log exists, skip regression comparison. Also document this in the flow.

---

### 8. `DailyUptimeSummary` Is Listed in the Schema But Has No Flow

The model `DailyUptimeSummary` appears in the "Other Models" section but there is zero mention of how or when it gets populated. No Celery task, no service, no flow chart references it. This means either it's dead/unused code, or a critical aggregation job is missing.

**Fix needed:** Add a `run_daily_summary_task()` Celery Beat job (daily at midnight) that aggregates `UptimeLog` records into `DailyUptimeSummary`. Document the flow.

---

### 9. Polling Every 2 Seconds Fetches ALL Sites — No Filtering

`GET /api/sites` returns all sites for every poll. If a user has 50+ monitored sites, every 2-second poll sends the full dataset. For a SaaS platform handling a fleet, this is an unbounded N+1-style payload problem that will degrade UI performance.

**Fix needed:** The polling endpoint should accept a `?since=` ISO8601 timestamp filter and return only sites that have changed since the last poll (using an `updated_at` field).

---

### 10. No Multi-Tenancy / User Isolation

The README describes this as a "SaaS" platform for "fleet management," but there is no `User` model, no authentication, no concept of ownership. All sites are globally visible. This is not a SaaS — it's a single-tenant admin tool.

**Fix needed:** The model layer needs a `User` (or `Organization`) entity. Every `Site` must have a `user_id` foreign key. All API endpoints must enforce ownership checks. This is foundational to any real SaaS product.

---
---

## 📋 PART B: FULL PERFECT BUILD PROMPT

> Copy everything below this line and paste it directly to your AI coding assistant.

---

```
You are a senior backend architect building a production-grade SaaS SEO &
Uptime Intelligence Engine in Python (Flask). I will describe the complete
system. You must implement it with zero shortcuts, correct logic, and
production-safe patterns. Follow every instruction precisely.

════════════════════════════════════════════════════════
PART 1: TECHNOLOGY STACK
════════════════════════════════════════════════════════

- Language: Python 3.12
- Web Framework: Flask (App Factory pattern, Blueprints)
- Database: SQLAlchemy ORM. SQLite for dev, PostgreSQL for prod.
  Use Alembic for migrations.
- Task Queue: Celery with Redis as broker AND result backend
- Scheduler: Celery Beat for periodic tasks
- HTTP Client: HTTPX with explicit per-call timeout configuration
  (NOT a shared global timeout)
- HTML Parsing: BeautifulSoup4 with lxml backend
- SSL Validation: Python standard ssl module
- Templating: Jinja2
- Auth: Flask-Login with bcrypt password hashing

════════════════════════════════════════════════════════
PART 2: DATABASE SCHEMA — EXACT MODELS
════════════════════════════════════════════════════════

### User (Multi-Tenancy Root)
- id: Integer, primary key
- email: String(255), unique, not null
- password_hash: String(255), not null
- created_at: DateTime, server_default=now
- is_active: Boolean, default=True

### Organization (optional, for team SaaS)
- id: Integer, primary key
- name: String(255), not null
- owner_id: ForeignKey(User.id)

### Site (Core entity — one per monitored URL)
- id: Integer, primary key
- user_id: ForeignKey(User.id), NOT NULL — every site MUST belong to a user
- url: String(2048) — original user-provided URL
- normalized_url: String(2048), unique per user — canonical form
- name: String(255), default=domain extracted from URL

--- Per-check interval fields (DO NOT use a single check_interval) ---
- uptime_check_interval: Integer, default=60        (seconds)
- ssl_check_interval: Integer, default=86400        (seconds, 24h)
- seo_check_interval: Integer, default=604800       (seconds, 7 days)

--- Scheduling timestamps ---
- next_uptime_check_at: DateTime, nullable
- next_ssl_check_at: DateTime, nullable
- next_seo_check_at: DateTime, nullable
- last_uptime_check_at: DateTime, nullable
- last_ssl_check_at: DateTime, nullable
- last_seo_check_at: DateTime, nullable

--- Granular per-check status (each is independent) ---
- uptime_status: String(20), default='pending'
  Allowed values: 'pending', 'running', 'done', 'failed'
- ssl_status: String(20), default='pending'
  Allowed values: 'pending', 'running', 'done', 'failed'
- seo_status: String(20), default='pending'
  Allowed values: 'pending', 'running', 'done', 'failed'

--- Aggregate status (derived, not set manually) ---
- app_status: String(20), default='pending'
  Allowed values: 'pending', 'checking', 'ready', 'partial', 'failed'

  Derived logic (CRITICAL — read carefully):
    IF all three statuses == 'done' AND none == 'failed' → 'ready'
    IF all three statuses == 'done' AND any == 'failed' → 'partial'
    IF any status == 'failed' AND others are 'done' or 'failed' (none 'running') → 'partial'
    IF any status == 'running' → 'checking'
    IF all == 'pending' → 'pending'
    DEFAULT fallback → 'partial'

  This logic MUST correctly handle the case where one task fails and
  another finishes later — the final status must NEVER be 'ready' if
  any task is 'failed'.

--- Uptime result fields ---
- current_status: String(20), default='PENDING'
  Allowed: 'UP', 'DOWN', 'DEGRADED', 'PENDING'
- last_status_code: Integer, nullable
- last_response_time: Float, nullable (seconds, total download time)
- last_ttfb: Float, nullable (seconds, time to first byte only)

--- SSL result fields ---
- ssl_state: String(20), default='UNKNOWN'
  Allowed: 'VALID', 'EXPIRING', 'EXPIRED', 'ERROR', 'UNKNOWN'
- ssl_expiry_date: DateTime, nullable
- ssl_days_remaining: Integer, nullable
- ssl_issuer: String(500), nullable

--- SEO result fields ---
- seo_score: Integer, default=0 (0–100)
- seo_state: String(20), default='UNKNOWN'
  Allowed: 'GOOD', 'FAIR', 'POOR', 'UNKNOWN'

--- Concurrency control ---
  DO NOT use is_processing boolean. Instead, use per-check optimistic
  locking via the individual status fields. See Concurrency section.

- updated_at: DateTime, onupdate=now — used for delta polling

### UptimeLog
- id, site_id (FK), status_code, response_time (total),
  ttfb (time to first byte), is_up (bool), status (UP/DOWN/DEGRADED),
  error_message, checked_at

### SSLLog
- id, site_id (FK), issuer, expiry_date, days_remaining,
  state (VALID/EXPIRING/EXPIRED/ERROR), error_message, checked_at

### SEOLog
- id, site_id (FK), score (0-100), status (GOOD/FAIR/POOR),
  score_breakdown (JSON: {on_page, technical, content, performance,
  security_mobile}), signals (JSON: all 30+ raw signals),
  issues (JSON: list of dicts {check, message, impact}),
  recommendations (JSON: list of dicts {priority, action, detail}),
  checked_at

### Incident
- id, site_id (FK), started_at, resolved_at (nullable),
  previous_status, new_status, is_active (bool)

### AlertHistory
- id, site_id (FK), alert_type (DOWNTIME/SSL_EXPIRY/SEO_REGRESSION),
  message, sent_at, recipients (JSON: list of emails), success (bool)

### SiteNotification
- id, site_id (FK), email, is_active (bool)

### DailyUptimeSummary
- id, site_id (FK), date (Date, not DateTime),
  total_checks (int), up_checks (int), down_checks (int),
  degraded_checks (int), uptime_percentage (Float),
  avg_response_time (Float), avg_ttfb (Float)
  Unique constraint on (site_id, date)

════════════════════════════════════════════════════════
PART 3: HTTP CLIENT — CRITICAL RULES
════════════════════════════════════════════════════════

Implement app/utils/http.py with a function:
  fetch_url(url, timeout, stream_for_ttfb=False)

- The timeout parameter is REQUIRED and has NO default. Every caller
  must explicitly pass a timeout. Never use a module-level global timeout.
- Uptime checks call: fetch_url(url, timeout=5.0)
- SEO checks call: fetch_url(url, timeout=20.0, stream_for_ttfb=True)

TTFB measurement (when stream_for_ttfb=True):
  1. Start timer BEFORE request
  2. Open HTTPX streaming response
  3. Record ttfb = time elapsed when the FIRST chunk of response body
     is received (use httpx streaming: async for chunk in response.aiter_bytes(),
     record time on first iteration, then consume the rest)
  4. Record total_response_time = time when full body is consumed
  5. Return: { html_content, ttfb, total_response_time,
               status_code, is_up, error, final_url, https_redirect }

Retry logic: 2 retries with exponential backoff (1s, 2s), only on
network errors (not on HTTP 4xx/5xx — those are valid responses).

════════════════════════════════════════════════════════
PART 4: CONCURRENCY — CORRECT RACE CONDITION PREVENTION
════════════════════════════════════════════════════════

DO NOT use a single is_processing boolean flag. That creates a race
condition when multiple tasks read it before any writes it.

CORRECT approach — use database row-level locking:

  def acquire_check_lock(site_id, check_type, db_session):
      """
      Atomically checks and sets the status to 'running'.
      check_type is one of: 'uptime', 'ssl', 'seo'
      Returns True if lock acquired, False if already running.
      """
      status_field = f"{check_type}_status"
      site = db_session.query(Site).filter(
          Site.id == site_id,
          getattr(Site, status_field) != 'running'
      ).with_for_update().first()

      if site is None:
          return False  # Already running or not found

      setattr(site, status_field, 'running')
      db_session.commit()
      return True

For SQLite (dev): Use a Redis-based distributed lock as the atomic
primitive (since SQLite has no row-level locking):

  def acquire_check_lock_redis(site_id, check_type, timeout=300):
      lock_key = f"lock:site:{site_id}:{check_type}"
      return r.set(lock_key, '1', nx=True, ex=timeout)

  def release_check_lock_redis(site_id, check_type):
      lock_key = f"lock:site:{site_id}:{check_type}"
      r.delete(lock_key)

Each task MUST:
  1. Acquire the lock (Redis OR db lock depending on environment)
  2. If lock not acquired: log and return immediately
  3. Use try/finally to ALWAYS release the lock, even on exceptions

════════════════════════════════════════════════════════
PART 5: CELERY TASKS — CORRECT FLOW
════════════════════════════════════════════════════════

### Task: run_uptime_check_task(site_id)
1. Create Flask app context
2. Fetch site from DB
3. Attempt to acquire uptime lock (see Part 4). If fails, return.
4. try:
   a. Call monitor_service.run_uptime_check(site)
      - fetch_url(site.url, timeout=5.0)
      - Determine status:
          DOWN if not is_up
          DEGRADED if response_time > site.degraded_threshold (default 2.0s)
          else UP
      - Create UptimeLog(ttfb=ttfb, response_time=total_time, ...)
      - Compare to previous UptimeLog:
          IF previous was UP and current is DOWN:
            create Incident(is_active=True)
          IF previous was DOWN and current is UP:
            close active Incident (resolved_at=now, is_active=False)
          IF status changed (any direction):
            trigger alert_service
      - Update site.current_status, site.last_response_time, site.last_ttfb
      - Schedule: site.next_uptime_check_at = now + site.uptime_check_interval
      - Set site.uptime_status = 'done'
   b. Call site.refresh_app_status()
   c. Commit
5. except Exception:
   a. Set site.uptime_status = 'failed'
   b. Call site.refresh_app_status()
   c. Commit
   d. Log error
6. finally:
   a. Release uptime lock

### Task: run_ssl_check_task(site_id)
1-3. Same as uptime (acquire ssl lock)
4. try:
   a. Call ssl_service.run_ssl_check(site)
      - Extract hostname, connect to port 443
      - Get peer certificate, parse expiry, issuer
      - Calculate days_remaining = (expiry_date - now).days
      - Determine state:
          days_remaining < 0  → 'EXPIRED'
          days_remaining < 14 → 'EXPIRING'
          else                → 'VALID'
      - IMPORTANT: If SSL connection fails entirely, state = 'ERROR',
        error_message = str(exception). Do NOT let exception propagate
        uncaught — catch ssl.SSLError and socket errors.
      - Create SSLLog
      - If state in ('EXPIRING', 'EXPIRED'): trigger alert_service
      - Update site ssl fields
      - Schedule: site.next_ssl_check_at = now + site.ssl_check_interval
      - Set site.ssl_status = 'done'
   b. refresh_app_status(), commit
5. except: set ssl_status='failed', refresh, commit
6. finally: release ssl lock

### Task: run_seo_check_task(site_id)
1-3. Same (acquire seo lock)
4. try:
   a. Call seo_service.run_seo_check(site)
      Step 1: fetch_url(site.url, timeout=20.0, stream_for_ttfb=True)
              Record ttfb separately from total_response_time.
              If fetch fails: raise exception → task goes to 'failed'
      Step 2: parser.parse_seo_intelligence(html_content)
              Extract 30+ signals (see Part 6)
      Step 3: check robots.txt and sitemap.xml existence
              (separate HEAD requests with timeout=5.0 each)
      Step 4: seo_engine.analyze_seo(signals)
              Apply weighted scoring (see Part 6)
      Step 5: Fetch previous SEOLog for this site
              IF previous exists AND (current_score < previous_score - 5):
                trigger alert_service (SEO_REGRESSION)
              IF no previous SEOLog: skip regression check entirely
              (first-run edge case — log at DEBUG level, no exception)
      Step 6: Create SEOLog
      Step 7: Update site.seo_score, site.seo_state
      Step 8: Schedule: site.next_seo_check_at = now + site.seo_check_interval
      Step 9: Set site.seo_status = 'done'
   b. refresh_app_status(), commit
5. except: set seo_status='failed', refresh, commit
6. finally: release seo lock

════════════════════════════════════════════════════════
PART 6: SEO SCORING ENGINE — EXACT ALGORITHM
════════════════════════════════════════════════════════

Signals to extract (parser.py):

ON-PAGE signals:
  title_text: str
  title_length: int
  title_present: bool (True if <title> exists and non-empty)
  title_in_optimal_range: bool (50-60 characters)
  meta_description_text: str
  meta_description_length: int
  meta_description_present: bool
  meta_description_in_optimal_range: bool (120-160 characters)

HEADER signals:
  h1_count: int
  h1_text: list[str]
  h1_present: bool (True if exactly 1 H1)
  h2_count, h3_count, h4_count, h5_count, h6_count: int
  has_logical_hierarchy: bool (H1 exists before H2, H2 before H3, etc.)

CONTENT signals:
  word_count: int (visible text words only)
  meets_word_count_threshold: bool (>= 300 words)
  keyword_density: float (0.0-1.0)
  img_count: int
  img_with_alt: int
  img_without_alt: int
  alt_text_coverage: float (0.0-1.0)

LINK signals:
  internal_link_count: int
  external_link_count: int
  links_with_anchor_text: int

TECHNICAL signals:
  canonical_url: str or None
  has_canonical: bool
  lang_attribute: str or None
  has_lang: bool
  robots_meta_content: str or None
  has_noindex: bool
  has_robots_txt: bool (from HEAD request)
  has_sitemap_xml: bool (from HEAD request)
  hreflang_count: int

PERFORMANCE signals:
  ttfb: float (seconds — TRUE TTFB from streaming response)
  total_response_time: float (seconds)
  page_size_kb: float (len(html_content) / 1024)
  ttfb_acceptable: bool (ttfb < 1.5)

SECURITY & MOBILE signals:
  https_redirect: bool
  has_mixed_content: bool
  has_viewport_meta: bool

--- Scoring Algorithm ---

on_page_score (max 100):
  + 20 if title_present
  + 20 if title_in_optimal_range
  + 20 if meta_description_present
  + 20 if meta_description_in_optimal_range
  + 20 if h1_present (exactly one H1)

technical_score (max 100):
  + 25 if has_robots_txt
  + 25 if has_sitemap_xml
  + 25 if has_canonical
  + 15 if has_lang
  + 10 if NOT has_noindex

content_score (max 100):
  + 40 if meets_word_count_threshold
  + 30 if has_logical_hierarchy
  + 30 * alt_text_coverage (proportional, 0–30 points)

performance_score (max 100):
  TTFB component (award highest applicable):
    + 50 if ttfb < 0.8
    + 30 if ttfb < 1.5
    + 0  if ttfb >= 1.5
  Page size component (award highest applicable):
    + 30 if page_size_kb < 500
    + 15 if page_size_kb < 1000
    + 0  if page_size_kb >= 1000
  Remaining 20 points: split evenly from TTFB/size as bonus
  Normalize to 0–100.

security_mobile_score (max 100):
  + 40 if https_redirect
  + 40 if has_viewport_meta
  + 20 if NOT has_mixed_content

Final composite score:
  composite = (
    on_page_score     * 0.40 +
    technical_score   * 0.25 +
    content_score     * 0.15 +
    performance_score * 0.10 +
    security_mobile_score * 0.10
  )
  Round to nearest integer. Clamp to [0, 100].

Status thresholds:
  >= 80 → 'GOOD'
  >= 60 → 'FAIR'
  <  60 → 'POOR'

Issues format:
  { "check": "<signal_name>", "category": "<category>",
    "message": "<human-readable problem>", "impact": "high|medium|low" }

Recommendations format:
  { "priority": 1-10 (lower = fix first), "action": "<verb phrase>",
    "detail": "<specific guidance with examples>" }

Sort recommendations by priority ascending.

════════════════════════════════════════════════════════
PART 7: CELERY BEAT PERIODIC TASKS — CORRECT SCHEDULES
════════════════════════════════════════════════════════

Define these in celeryconfig.py beat_schedule:

1. run_due_uptime_checks — every 30 seconds
   Query: SELECT sites WHERE next_uptime_check_at <= now()
   Dispatch run_uptime_check_task for each

2. run_due_ssl_checks — every 1 hour
   Query: SELECT sites WHERE next_ssl_check_at <= now()

3. run_due_seo_checks — every 1 hour
   Query: SELECT sites WHERE next_seo_check_at <= now()

4. run_zombie_rescue — every 5 MINUTES (NOT 24 hours)
   Logic:
   - Find sites where uptime_status='running' AND
     last_uptime_check_at < (now - 10 minutes)
     → Set uptime_status='failed'
   - Same for ssl_status (timeout threshold = 30 minutes)
   - Same for seo_status (timeout threshold = 60 minutes)
   - For each rescued site: call refresh_app_status()
   - Commit and log each rescue with site_id and check_type

5. run_daily_summary — daily at 00:05 UTC
   For each site:
   - Query UptimeLog for previous full calendar day (UTC midnight to midnight)
   - Aggregate: total, up_count, down_count, degraded_count
   - uptime_percentage = (up_count / total * 100) if total > 0 else None
   - avg_response_time = AVG(response_time)
   - avg_ttfb = AVG(ttfb)
   - Upsert into DailyUptimeSummary (INSERT OR REPLACE on site_id + date)
   - Commit (task is idempotent — safe to re-run)

6. run_data_retention — daily at 03:00 UTC
   Config: RETENTION_DAYS (default 90)
   - Delete UptimeLog, SSLLog, SEOLog, Incident, AlertHistory
     where checked_at/sent_at < (now - RETENTION_DAYS)
   - Do NOT delete DailyUptimeSummary (keep for long-term trend charts)
   - Log count of deleted records per table

════════════════════════════════════════════════════════
PART 8: REST API — ENDPOINTS AND RULES
════════════════════════════════════════════════════════

All endpoints require authentication (Flask-Login session or API key header).
All site endpoints enforce ownership: site.user_id == current_user.id.
Return JSON. Use HTTP status codes correctly.

POST   /auth/register
       Body: { email, password }
       Returns: 201

POST   /auth/login
       Body: { email, password }
       Returns: 200

POST   /auth/logout
       Returns: 200

GET    /api/sites
       Returns all sites for current_user.
       Query param: ?since=<ISO8601 datetime>
       If provided: return only sites where updated_at > since
       This enables efficient delta polling from frontend.

POST   /api/sites
       Body: { url, name?, uptime_check_interval?,
               ssl_check_interval?, seo_check_interval?,
               notification_emails: [] }
       Validate URL. Normalize. Check uniqueness per user.
       Create site. Dispatch 3 tasks.
       Returns: 201 { id, message }

GET    /api/sites/<id>
       Returns full site detail with latest log summaries.

DELETE /api/sites/<id>
       Soft delete (set is_active=False)

POST   /api/sites/<id>/check
       Manually trigger all 3 checks.
       Each check attempts lock. If already running, include in response:
       { "uptime": "skipped (already running)", "ssl": "dispatched", ... }

GET    /api/sites/<id>/history/uptime?days=7
       Paginated uptime logs.

GET    /api/sites/<id>/history/ssl?limit=10
       Recent SSL logs.

GET    /api/sites/<id>/history/seo?limit=5
       Recent SEO logs.

GET    /api/sites/<id>/uptime-summary?days=30
       DailyUptimeSummary data for charts.

════════════════════════════════════════════════════════
PART 9: DASHBOARD UI — DELTA POLLING
════════════════════════════════════════════════════════

The dashboard JS MUST use delta polling:

  let lastPolledAt = null;

  async function pollUpdates() {
    const url = lastPolledAt
      ? `/api/sites?since=${lastPolledAt}`
      : '/api/sites';

    const res = await fetch(url);
    const sites = await res.json();

    lastPolledAt = new Date().toISOString();

    // Only re-render cards for sites that were returned
    sites.forEach(site => updateSiteCard(site));
  }

  // Poll every 3 seconds
  setInterval(pollUpdates, 3000);

Status badge display rules:
  'pending'  → grey badge,    "Never Checked"
  'checking' → animated spinner badge, "Checking..."
  'ready'    → green badge,   "All Systems OK"
  'partial'  → amber badge,   "Partial Results"
  'failed'   → red badge,     "Check Failed"

Per-check status icons (uptime / ssl / seo row):
  'pending'  → grey circle
  'running'  → pulsing spinner
  'done'     → green checkmark
  'failed'   → red X

SEO score ring color:
  80–100 → green
  60–79  → amber
  0–59   → red

════════════════════════════════════════════════════════
PART 10: ALERT SERVICE
════════════════════════════════════════════════════════

alert_service.py must:
  1. Accept: site, alert_type, context_data dict
  2. Fetch active SiteNotification emails for the site
  3. Render appropriate email template (Jinja2)
  4. Send via email_service (SMTP)
  5. Record AlertHistory regardless of send success
  6. Never raise exceptions to caller — catch all, log errors

Alert types and triggers:
  DOWNTIME:
    Uptime transitions to DOWN (only on transition, not every DOWN check)
  RECOVERY:
    Uptime transitions back to UP from DOWN
  SSL_EXPIRY_WARNING:
    ssl_days_remaining < 14
    Deduplicate: check AlertHistory — only send once per day per site
  SSL_EXPIRED:
    ssl_days_remaining < 0
  SEO_REGRESSION:
    seo_score drops more than 5 points vs previous check
    AND a previous SEOLog exists
    (handle first-run: no alert if no baseline — log DEBUG, skip silently)

════════════════════════════════════════════════════════
PART 11: DIRECTORY STRUCTURE
════════════════════════════════════════════════════════

app/
├── __init__.py               # App factory: create_app()
├── extensions.py             # db, celery, login_manager
├── config.py                 # Config classes: Dev, Prod, Test
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── site.py               # Site model + refresh_app_status() method
│   ├── logs.py               # UptimeLog, SSLLog, SEOLog
│   ├── incident.py
│   ├── summary.py            # DailyUptimeSummary
│   └── notifications.py      # SiteNotification, AlertHistory
├── services/
│   ├── monitor_service.py
│   ├── ssl_service.py
│   ├── seo_service.py
│   ├── alert_service.py
│   ├── email_service.py
│   ├── retention_service.py
│   └── summary_service.py    # Daily aggregation logic
├── workers/
│   ├── tasks.py              # Celery task definitions
│   └── celeryconfig.py       # Beat schedule definition
├── utils/
│   ├── http.py               # fetch_url with per-call timeout + TTFB streaming
│   ├── parser.py             # parse_seo_intelligence()
│   ├── seo_engine.py         # analyze_seo() scoring algorithm
│   ├── urls.py               # normalize_url(), validate_url()
│   └── time_utils.py         # timezone-aware datetime helpers (UTC always)
├── api/
│   ├── __init__.py
│   ├── auth.py               # /auth/* endpoints
│   └── sites.py              # /api/sites/* endpoints
└── templates/
    ├── base.html
    ├── auth/
    │   ├── login.html
    │   └── register.html
    ├── dashboard/
    │   └── index.html
    ├── site/
    │   └── detail.html
    └── email/
        ├── downtime.html
        ├── recovery.html
        ├── ssl_warning.html
        └── seo_regression.html

migrations/                   # Alembic migration files
celeryconfig.py
run.py
requirements.txt
.env.example

════════════════════════════════════════════════════════
PART 12: NON-NEGOTIABLE IMPLEMENTATION RULES
════════════════════════════════════════════════════════

1. ALL datetimes MUST be UTC-aware. Use datetime.now(timezone.utc).
   NEVER use naive datetimes anywhere in the codebase.

2. ALL HTTP fetch calls MUST pass an explicit timeout parameter.
   The http.py module MUST raise TypeError if timeout is not provided.

3. refresh_app_status() MUST implement priority-correct aggregate logic:
   - 'failed' is sticky — if any check is failed and others are done,
     result is 'partial', never 'ready'
   - 'ready' requires all three statuses to be 'done' with zero 'failed'

4. Celery tasks MUST use try/finally for lock release.
   A task that crashes mid-execution MUST still release its lock.

5. Zombie rescue task runs every 5 MINUTES.
   Data retention task runs once daily at 03:00 UTC.
   These are two SEPARATE Celery Beat entries — never combine them.

6. Daily summary task aggregates the previous calendar day only.
   It MUST use upsert semantics (idempotent — safe to re-run).

7. The /api/sites polling endpoint MUST support ?since= delta filtering.

8. SEO regression alert MUST check if a previous SEOLog exists before
   comparing scores. If no previous log: log at DEBUG, skip alert,
   do not raise exception.

9. TTFB for SEO MUST use streaming response to measure actual
   time to first byte, NOT total download time.

10. SSL error handling: ALWAYS catch ssl.SSLError, socket.timeout,
    ConnectionRefusedError separately and map to state='ERROR' with
    descriptive error_message. Never let SSL task fail silently.

════════════════════════════════════════════════════════
IMPLEMENTATION ORDER (follow this sequence exactly)
════════════════════════════════════════════════════════

Step 1:  Models + Alembic migrations
Step 2:  Config + extensions + app factory
Step 3:  http.py utility (TTFB streaming, explicit timeout)
Step 4:  parser.py + seo_engine.py (signal extraction + scoring)
Step 5:  monitor_service, ssl_service, seo_service
Step 6:  alert_service + email_service
Step 7:  Celery tasks + celeryconfig (beat schedule)
Step 8:  REST API endpoints (auth + sites)
Step 9:  Flask-Login authentication
Step 10: Jinja2 templates + dashboard JS (delta polling)
Step 11: retention_service + summary_service
Step 12: requirements.txt + .env.example + README

Begin with Step 1. After completing each step, confirm what was built
before proceeding. Do not skip steps or combine them unless explicitly asked.
```

---

*Analysis & Prompt authored for SaaS SEO Intelligence Engine v2.0 — Antigravity SaaS Engineering Platform.*
