# Project Analysis & Bug Report
**Website Monitor — SaaS SEO Intelligence Engine**
**Date:** 2026-04-30 | **Analyst:** Kiro

---

## Project Overview

A Flask + Celery SaaS website monitoring platform with three independent check types:
- **Uptime** — HTTP availability and response time
- **SSL** — Certificate validity and expiry tracking
- **SEO** — Deep HTML audit with 30+ signals and scoring

**Stack:** Flask 3.0, SQLAlchemy 2.0, Celery 5.3, Redis, HTTPX, BeautifulSoup4, SQLite/PostgreSQL

---

## CRITICAL BUGS

### BUG-01 — Double Cooldown Check in SEO Task (Logic Duplication)
**File:** `app/workers/tasks.py` → `run_seo_check_task()`
**Severity:** HIGH

`run_seo_check_task` calls `should_skip_seo_for_cooldown(site)` before dispatching to `run_seo_service()`. But `run_seo_service()` (`seo_service.run_seo_check`) also calls `should_skip_seo_for_cooldown()` internally at the top. This means the cooldown is evaluated twice per task execution. The second check inside the service will always pass because the task already handled the skip case, but it wastes a DB read and creates confusing log output.

More critically: the task sets `site.seo_status = "running"` and commits **before** calling `run_seo_service()`. If the cooldown is active, the task returns early with `site.seo_status = "pending"` — but `acquire_check_lock()` already set it to `"running"` and committed. The `release_check_lock()` in the `finally` block then calls `refresh_app_status()` which may leave the site in an inconsistent state.

```python
# tasks.py — cooldown check happens AFTER lock is acquired
if not acquire_check_lock(site_id, "seo"):   # sets status="running", commits
    return "Already running"

try:
    should_skip, reason = should_skip_seo_for_cooldown(site)  # checked here
    if should_skip:
        site.seo_status = "pending"   # overrides "running" set by lock
        db.session.commit()
        return "Cooldown active"
    
    site.seo_status = "running"  # redundant — already set by acquire_check_lock
```

**Impact:** Site can get stuck in `"checking"` app_status when cooldown fires, because `release_check_lock` runs `refresh_app_status()` on a site whose `seo_status` was set to `"pending"` but `uptime_status` and `ssl_status` may still be `"done"` — resulting in `app_status = "partial"` instead of `"ready"`.

---

### BUG-02 — `acquire_check_lock` Uses Column Object as Dict Key
**File:** `app/workers/tasks.py` → `acquire_check_lock()`
**Severity:** HIGH

```python
updated = (
    Site.query
    .filter(Site.id == site_id, status_field != "running")
    .update({
        f"{check_type}_status": "running",
        started_name: now_utc(),
        Site.last_started_at: now_utc(),   # ← Column object as key
        Site.app_status: "checking",        # ← Column object as key
        Site.is_processing: True,           # ← Column object as key
    }, synchronize_session=False)
)
```

Mixing string keys (`f"{check_type}_status"`) with SQLAlchemy column objects (`Site.last_started_at`) in the same `.update()` dict is inconsistent and may raise a `CompileError` depending on the SQLAlchemy version and dialect. The correct approach is to use all string keys or all column objects — not both.

**Impact:** `acquire_check_lock` may crash at runtime, causing all Celery tasks to fail silently and return `"Already running"` on the next attempt (since the lock was never acquired).

---

### BUG-03 — `fetch_url` Retry Logic Off-By-One
**File:** `app/utils/http.py` → `fetch_url()`
**Severity:** MEDIUM

```python
RETRY_DELAYS = [1.0, 2.0]

for attempt, delay in enumerate([0] + RETRY_DELAYS):
    # attempt = 0, 1, 2
    ...
    except (...) as e:
        if attempt == len(RETRY_DELAYS):   # len([1.0, 2.0]) = 2
            return _make_error_result(str(e))
```

`enumerate([0] + RETRY_DELAYS)` produces attempts `0, 1, 2`. The condition `attempt == len(RETRY_DELAYS)` checks `attempt == 2`, which is the **last** iteration. This means on the final attempt (index 2), the error is returned. However, on attempts 0 and 1, the exception is **silently swallowed** — the loop continues to the next iteration without returning or re-raising. This means a failed attempt 0 will sleep 1 second and retry, and a failed attempt 1 will sleep 2 seconds and retry, which is the intended behavior. But the logic is fragile: if `RETRY_DELAYS` is changed to 3 items, the last attempt (index 3) would never match `len(RETRY_DELAYS) == 3` because enumerate starts at 0 — it would match index 3 which is correct. Actually this is fine as written, but the intent is unclear and the silent swallow on non-final attempts is a code smell that could mask bugs.

More importantly: `fetch_url` can return `None` implicitly if all retries are exhausted without hitting the final `attempt == len(RETRY_DELAYS)` check — specifically if the loop exits normally. This would cause a `TypeError` in callers that do `fetch_result.get(...)`.

**Impact:** Under specific retry exhaustion paths, `fetch_url` returns `None` instead of an error dict, crashing `run_seo_check` with `AttributeError: 'NoneType' object has no attribute 'get'`.

---

### BUG-04 — `report_service.py` Uses Deprecated `Query.get()`
**File:** `app/services/report_service.py` → `generate_site_report()`
**Severity:** MEDIUM

```python
site = Site.query.get(site_id)   # deprecated in SQLAlchemy 2.0
```

`Query.get()` was removed in SQLAlchemy 2.0. The correct call is `db.session.get(Site, site_id)`. This will raise `AttributeError` at runtime in any environment using SQLAlchemy 2.x (which is pinned in `requirements.txt` as `SQLAlchemy==2.0.23`).

**Impact:** Every call to `GET /site/<id>/download-report` will crash with a 500 error.

---

### BUG-05 — `check_seo_alerts` References `db` Before Import
**File:** `app/services/alert_service.py` → `check_seo_alerts()`
**Severity:** HIGH

```python
def check_seo_alerts(site, score: int, status: str, checked_at: datetime) -> None:
    from app.models.seo_log import SEOLog

    with db.session.no_autoflush:   # ← `db` used here
        ...
```

`db` is imported at the **bottom** of the file (line ~100+), after `_send_alert()` and other top-level functions. The `check_seo_alerts` function is defined **before** the `from app.extensions import db` import. In Python, function bodies are not executed at definition time, so this works at runtime — but only because `db` is resolved at call time from the module's global scope. However, the import of `db` is placed after the function definition, which is a structural anti-pattern that will confuse static analyzers and could break if the file is refactored.

More critically: `db` is imported at the bottom alongside `AlertHistory`, `Incident`, `SiteNotification`, and `send_email`. If any of those imports fail (e.g., circular import), `db` will be `undefined` in the module scope and `check_seo_alerts` will raise `NameError: name 'db' is not defined`.

**Impact:** SEO regression alerts will fail with `NameError` if there is any import error in the bottom half of `alert_service.py`.

---

### BUG-06 — SSL `days_remaining` Can Be Negative Without Triggering EXPIRED State Correctly
**File:** `app/services/ssl_service.py` → `_ssl_state()`
**Severity:** LOW

```python
def _ssl_state(days_left: int | None) -> str:
    if days_left is None:
        return "ERROR"
    if days_left < 0:
        return "EXPIRED"
    if days_left < 14:
        return "EXPIRING"
    return "VALID"
```

The `days_remaining` is calculated as:
```python
days_left = (expiry - current_now).days
```

`timedelta.days` truncates toward negative infinity. A cert that expired 1 hour ago returns `days_left = -1`. A cert that expired 23 hours ago also returns `days_left = -1`. This is correct for state classification, but the `check_ssl_alerts` function checks:

```python
event_type = "SSL_EXPIRED" if days_remaining < 0 else "SSL_EXPIRY_WARNING"
if event_type == "SSL_EXPIRY_WARNING" and _daily_alert_sent(site.id, event_type, checked_at):
    return
```

The `SSL_EXPIRED` event type has **no cooldown check** — it will fire on every SSL check cycle (every 6 hours by default) for an expired cert. This will spam recipients with alerts every 6 hours indefinitely.

**Impact:** Alert spam for expired certificates until the cert is renewed.

---

## LOGIC BUGS

### LOGIC-01 — `refresh_app_status()` Has Incorrect Priority for Mixed States
**File:** `app/models/site.py` → `refresh_app_status()`
**Severity:** HIGH

```python
def refresh_app_status(self):
    statuses = [self.uptime_status, self.ssl_status, self.seo_status]

    if any(s == "running" for s in statuses):
        self.app_status = "checking"
    elif all(s == "pending" for s in statuses):
        self.app_status = "pending"
    elif all(s == "done" for s in statuses):
        self.app_status = "ready"
    elif any(s == "failed" for s in statuses):
        self.app_status = "partial"
    else:
        self.app_status = "partial"
```

**Problem:** If `uptime_status = "done"`, `ssl_status = "done"`, `seo_status = "failed"`, the result is `app_status = "partial"` — correct. But if the SEO task is then retried and succeeds, all three become `"done"` and `app_status = "ready"` — the previous failure is erased from the aggregate status. This is acceptable behavior, but the issue is the **mixed pending/done** case:

If `uptime_status = "done"`, `ssl_status = "pending"`, `seo_status = "pending"` (e.g., right after site creation when only uptime has run), none of the conditions match cleanly:
- Not all `"running"` → skip
- Not all `"pending"` → skip  
- Not all `"done"` → skip
- No `"failed"` → falls to `else: "partial"`

So a site that has completed 1 of 3 checks shows `app_status = "partial"` instead of something like `"checking"` or `"in_progress"`. The UI will show a partial/warning state for a brand-new site that is still initializing.

---

### LOGIC-02 — Retention Service Deletes SSL/SEO Logs Without Aggregation
**File:** `app/services/retention_service.py`
**Severity:** MEDIUM

```python
deleted_ssl = SSLLog.query.filter(SSLLog.checked_at < cutoff).delete(synchronize_session=False)
deleted_seo = SEOLog.query.filter(SEOLog.checked_at < cutoff).delete(synchronize_session=False)
```

Uptime logs are aggregated into `DailyUptimeSummary` by `summary_service.py` before deletion. SSL and SEO logs are simply deleted with no aggregation. After 30 days, all historical SSL certificate data and SEO score trends are permanently lost.

**Impact:** No long-term SSL stability history. No SEO score trend data beyond 30 days. The `DailySSLSummary` and `DailySEOSummary` models exist in the models directory but are never populated.

---

### LOGIC-03 — `_get_domain()` in `parser.py` Uses Naive String Splitting
**File:** `app/utils/parser.py` → `_get_domain()`
**Severity:** LOW

```python
def _get_domain(url: str) -> str:
    if not url: return ""
    return url.replace("https://", "").replace("http://", "").split("/")[0]
```

This is the same naive approach flagged in the existing bug report. For URLs like `https://example.com:8443/path`, this returns `example.com:8443` (with port), which will fail the `domain in href` check for internal link detection. Should use `urlparse(url).netloc` or `urlparse(url).hostname`.

---

### LOGIC-04 — `word_count` Threshold Uses 4+ Character Words Only
**File:** `app/utils/parser.py` → `parse_seo_intelligence()`
**Severity:** LOW

```python
words = re.findall(r"\w{4,}", clean_text.lower())
...
"meets_word_count_threshold": len(words) >= 300,
```

The word count only counts words with 4+ characters. Common words like "the", "a", "is", "to", "in", "of", "and" are excluded. A page with 500 total words but many short words could fail the 300-word threshold. This is an intentional design choice (filtering noise), but the threshold of 300 is calibrated for full words, not 4+ character words. A typical 300-word article has roughly 200 words with 4+ characters. The threshold should be ~200 if using this filter, or the filter should be removed.

---

### LOGIC-05 — `has_logical_hierarchy` Check Is Overly Strict
**File:** `app/utils/parser.py` → `parse_seo_intelligence()`
**Severity:** LOW

```python
has_logical_hierarchy = h_counts[0] == 1 and not any(
    h_counts[i] and not any(h_counts[:i]) for i in range(1, 6)
)
```

This checks that no heading level `i` exists unless all levels before it also exist (e.g., no H3 without H2). This is overly strict — many valid pages skip heading levels (e.g., H1 → H3 is common in component-based layouts). This will incorrectly penalize many legitimate pages.

---

### LOGIC-06 — SEO Score Regression Alert Fires After `_save_seo_log`
**File:** `app/services/seo_service.py` → `run_seo_check()`
**Severity:** MEDIUM

```python
previous_log = (
    db_session.query(SEOLog)
    .filter(SEOLog.site_id == site.id, SEOLog.fetch_valid.is_(True))
    .order_by(SEOLog.checked_at.desc())
    .first()
)

_save_seo_log(site, result, db_session, checked_at)  # ← new log saved here

site.seo_score = result["score"] or 0
...

if previous_log is not None and previous_log.score is not None and result["score"] is not None:
    score_drop = previous_log.score - result["score"]
    if score_drop > 5:
        logger.warning(...)   # ← only logs, does NOT call alert_service

try:
    alert_service.check_seo_alerts(...)   # ← alert_service queries DB for previous log
```

There are two separate regression checks:
1. A manual `score_drop > 5` check that only logs a warning — it does NOT send an alert.
2. `alert_service.check_seo_alerts()` which queries the DB for the previous log independently.

After `_save_seo_log()` is called, the new log is in the DB (flushed). When `alert_service.check_seo_alerts()` queries for the previous log, it will find the **newly saved log** as the most recent one (since it was just flushed), not the actual previous baseline. This means the regression comparison in `check_seo_alerts` compares the new score against itself — always showing 0 drop — and **never fires the regression alert**.

**Impact:** SEO regression email alerts never fire.

---

### LOGIC-07 — `run_uptime_check` Does Not Commit After Setting `uptime_status = "failed"`
**File:** `app/services/monitor_service.py` → `run_uptime_check()`
**Severity:** MEDIUM

```python
except Exception as exc:
    logger.exception("Uptime check failed for %s", site.url)
    site.uptime_status = "failed"
    raise   # ← no commit before raise
```

When an exception occurs, `site.uptime_status = "failed"` is set but never committed. The exception propagates to `run_uptime_check_task` in `tasks.py`, which does:

```python
except Exception:
    db.session.rollback()   # ← rolls back the "failed" status set in monitor_service
    site = db.session.get(Site, site_id)
    site.uptime_status = "failed"
    site.refresh_app_status()
    db.session.commit()   # ← this commit saves it
```

The rollback in the task correctly discards the uncommitted change from the service, then re-fetches and re-sets the status. This works, but it's fragile — the service sets a status that is always rolled back, creating misleading code. The service should either commit or not set the status at all (leaving it to the task layer).

---

### LOGIC-08 — `_local_user_id()` Creates a User on Every Unauthenticated Request
**File:** `app/api/routes.py` → `_local_user_id()`
**Severity:** MEDIUM (Security)

```python
def _local_user_id() -> int:
    user = User.query.filter_by(email="local@website-monitor.internal").first()
    if user is None:
        user = User(email="local@website-monitor.internal", password_hash="local-development-user")
        db.session.add(user)
        db.session.commit()
    return user.id
```

This function is called by `_effective_user_id()` whenever no `user_id` is in the session. In production, any unauthenticated request to any API endpoint will silently create or use a shared "local" user account. All sites added without authentication are owned by this shared account, meaning any unauthenticated user can see and delete all sites added by other unauthenticated users.

The `password_hash` is set to the plaintext string `"local-development-user"` — not a real hash. If someone calls `user.check_password("local-development-user")`, `werkzeug.security.check_password_hash` will return `False` (since it's not a valid hash), but the account still exists and is used for all unauthenticated requests.

**Impact:** No multi-tenancy isolation in production. All unauthenticated users share one account.

---

### LOGIC-09 — `run_seo_check_task` Sets `seo_status = "running"` Redundantly
**File:** `app/workers/tasks.py` → `run_seo_check_task()`
**Severity:** LOW

```python
# acquire_check_lock already sets seo_status = "running" and commits
if not acquire_check_lock(site_id, "seo"):
    return "Already running"

try:
    ...
    site.seo_status = "running"   # ← redundant, already set by lock
    site.last_seo_check_at = now_utc()
    db.session.commit()
```

`acquire_check_lock` already sets `seo_status = "running"` via a bulk UPDATE and commits. Setting it again is redundant and causes an extra commit. More importantly, `last_seo_check_at` is set here in the task but also set inside `run_seo_service` via `schedule_next_run`. The task's value will be overwritten by the service, but the intermediate commit creates a brief window where `last_seo_check_at` is set to the task start time rather than the actual check time.

---

## MISSING FEATURES / GAPS

### GAP-01 — `DailySSLSummary` and `DailySEOSummary` Models Are Never Populated
**Files:** `app/models/daily_ssl_summary.py`, `app/models/daily_seo_summary.py`
**Severity:** MEDIUM

Both model files exist but `summary_service.py` only populates `DailyUptimeSummary`. The SSL and SEO summary tables are created in the DB but always empty.

---

### GAP-02 — No Email Validation on Notification Recipients
**File:** `app/api/routes.py` → `add_site()`, `create_site()`
**Severity:** LOW

Notification emails are accepted and stored without any format validation. Invalid email addresses (e.g., `"not-an-email"`, `""`) will be stored and cause `send_email()` to fail silently (the error is caught and logged but not surfaced to the user).

---

### GAP-03 — `check_interval` Field Is Redundant
**File:** `app/models/site.py`
**Severity:** LOW

The `Site` model has both `check_interval` (generic) and `uptime_check_interval`, `ssl_check_interval`, `seo_check_interval` (specific). The `get_interval_seconds()` function in `monitoring_service.py` uses the specific fields with a fallback to `check_interval` only for uptime. The generic `check_interval` field is set in `add_site()` and `create_site()` but never used for SSL or SEO scheduling. It's a dead field that adds confusion.

---

### GAP-04 — No CSRF Protection on Web Form Routes
**File:** `app/api/routes.py` → `create_site()`, `run_check()`
**Severity:** MEDIUM (Security)

The web blueprint form routes (`POST /sites/new`, `POST /site/<id>/run/<check_type>`) have no CSRF token validation. Any page on the internet can submit a form to these endpoints and trigger checks or add sites on behalf of a logged-in user.

---

### GAP-05 — `http.py` Global Client Does Not Respect Runtime Config Changes
**File:** `app/utils/http.py`
**Severity:** LOW

The `httpx.Client` singleton is initialized once with `Config.HTTP_VERIFY_SSL` and `Config.HTTP_USER_AGENT`. If these values change at runtime (e.g., via environment variable reload), the client is not refreshed. `refresh_http_client()` exists but is never called anywhere in the codebase.

---

### GAP-06 — No Pagination on Log History Endpoints
**File:** `app/api/routes.py`
**Severity:** LOW

`/sites/<id>/history/uptime` returns up to 500 logs. For a site checked every 30 seconds, 7 days of logs = ~20,000 records. The hard limit of 500 is applied but there is no pagination (no `page`/`offset` parameter), so older data beyond the 500-record window is inaccessible via the API.

---

## DEPENDENCY ISSUES

### DEP-01 — `celery[redis]` Listed Twice in `requirements.txt`
**File:** `requirements.txt`
**Severity:** LOW

```
celery==5.3.6
...
celery[redis]==5.3.6
```

`celery` is listed twice — once without extras and once with `[redis]`. This is harmless (pip deduplicates) but is a maintenance smell.

---

### DEP-02 — `requests` Library Is Imported but Never Used
**File:** `requirements.txt`
**Severity:** LOW

`requests==2.31.0` is in requirements but the codebase uses `httpx` exclusively for HTTP. `requests` is never imported in any source file. It's dead weight.

---

### DEP-03 — `flask-cors` Is in Requirements but Never Configured
**File:** `requirements.txt`, `app/__init__.py`
**Severity:** LOW

`flask-cors==4.0.0` is installed but `CORS` is never imported or applied in `create_app()`. Either CORS is not needed (remove the dependency) or it needs to be configured (add `CORS(flask_app)` to `create_app()`).

---

## SUMMARY TABLE

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-01 | HIGH | tasks.py | Double cooldown check causes inconsistent seo_status after lock release |
| BUG-02 | HIGH | tasks.py | Mixed string/column keys in `.update()` dict may crash acquire_check_lock |
| BUG-03 | MEDIUM | http.py | fetch_url can return None implicitly on retry exhaustion |
| BUG-04 | MEDIUM | report_service.py | Uses deprecated SQLAlchemy 1.x `Query.get()` — crashes on SQLAlchemy 2.x |
| BUG-05 | HIGH | alert_service.py | `db` imported after function definition — NameError risk on import failure |
| BUG-06 | LOW | ssl_service.py | SSL_EXPIRED alert has no cooldown — spams recipients every check cycle |
| LOGIC-01 | HIGH | site.py | refresh_app_status() shows "partial" for new sites still initializing |
| LOGIC-02 | MEDIUM | retention_service.py | SSL/SEO logs deleted without aggregation — historical data lost after 30 days |
| LOGIC-03 | LOW | parser.py | _get_domain() uses naive string split — fails on ports and complex URLs |
| LOGIC-04 | LOW | parser.py | word_count threshold calibrated for full words but counts 4+ char words only |
| LOGIC-05 | LOW | parser.py | has_logical_hierarchy too strict — penalizes valid pages that skip heading levels |
| LOGIC-06 | MEDIUM | seo_service.py | SEO regression alert compares new score against itself — never fires |
| LOGIC-07 | MEDIUM | monitor_service.py | uptime_status="failed" set but not committed before raise — always rolled back |
| LOGIC-08 | MEDIUM | routes.py | _local_user_id() creates shared dev account for all unauthenticated requests |
| LOGIC-09 | LOW | tasks.py | seo_status="running" set redundantly after acquire_check_lock already set it |
| GAP-01 | MEDIUM | summary_service.py | DailySSLSummary and DailySEOSummary models exist but are never populated |
| GAP-02 | LOW | routes.py | No email format validation on notification recipients |
| GAP-03 | LOW | site.py | check_interval field is redundant dead code |
| GAP-04 | MEDIUM | routes.py | No CSRF protection on web form POST routes |
| GAP-05 | LOW | http.py | Global HTTP client never refreshed when config changes at runtime |
| GAP-06 | LOW | routes.py | No pagination on log history endpoints |
| DEP-01 | LOW | requirements.txt | celery listed twice (with and without [redis] extra) |
| DEP-02 | LOW | requirements.txt | requests library installed but never used |
| DEP-03 | LOW | requirements.txt | flask-cors installed but never configured in create_app() |

---

## Priority Fix Order

**Fix immediately (breaks functionality):**
1. BUG-04 — `Query.get()` crash on report download
2. LOGIC-06 — SEO regression alerts never fire
3. BUG-02 — Mixed key types in `.update()` may crash all Celery tasks
4. BUG-01 — Double cooldown check leaves sites in inconsistent state

**Fix before production:**
5. LOGIC-08 — Shared dev user account in production
6. GAP-04 — CSRF protection on form routes
7. BUG-06 — SSL expired alert spam
8. LOGIC-02 — SSL/SEO historical data loss

**Fix when time allows:**
9. BUG-03 — fetch_url None return path
10. BUG-05 — alert_service.py import ordering
11. LOGIC-01 — app_status shows "partial" during initialization
12. All LOW severity items
