# 🕵️ Website Monitor: Analysis Report

This report details the bugs, logic mistakes, and missing features identified during the codebase audit.

---

## 🐞 Identified Bugs

### 1. Incomplete Alert Triggers [Priority: CRITICAL]
The worker tasks for SSL and SEO checks are incomplete.
- **Location**: `app/services/ssl_service.py` and `app/services/seo_service.py`.
- **Description**: Both services have a comment placeholder `# ── Alert evaluation ───────────────────────────────────────────────────` but **fail to call the alert service**.
- **Impact**: Users will never receive notifications for invalid SSL certificates or SEO failures, even if they have recipients configured.

### 2. Timezone Inconsistency [Priority: HIGH]
The application mixes naive and UTC-aware datetimes.
- **Location**: Throughout the models and services.
- **Description**: Most services use `datetime.utcnow()`, but `ssl_service.py` uses `datetime.now(timezone.utc)`.
- **Impact**: This can cause comparison errors in SQLAlchemy (especially with PostgreSQL backends) and potential "Database is locked" or "Type mismatch" errors. It can also lead to off-by-one errors in `days_remaining` calculations.

### 3. Naive Hostname Extraction [Priority: MEDIUM]
- **Location**: `app/services/ssl_service.py` (`_extract_hostname`).
- **Description**: The function uses simple string replacement: `url.replace("https://", "").replace("http://", "").split("/")[0]`.
- **Impact**: It fails to correctly identify the hostname for URLs with non-standard ports (e.g., `https://example.com:8443`) or complex subdomains. This will cause SSL checks to fail or check the wrong host.

---

## 🧠 Logic Mistakes

### 1. Data Aggregation Gap [Priority: MEDIUM]
- **Location**: `app/services/retention_service.py`.
- **Description**: While Uptime logs are aggregated into `DailyUptimeSummary` before deletion, **SSL and SEO logs are simply deleted**.
- **Impact**: Historical data for certificate stability and SEO improvements is permanently lost after the retention period (default 30 days).

### 2. Static HTTP Client Config [Priority: LOW]
- **Location**: `app/utils/http.py`.
- **Description**: The `httpx.Client` is a global singleton initialized once.
- **Impact**: Any runtime changes to environment variables (like `HTTP_TIMEOUT` or `HTTP_VERIFY_SSL`) will not take effect until the process is restarted.

### 3. Missing Schema Abstraction [Priority: MEDIUM]
- **Location**: `app/services/schema_service.py`.
- **Description**: Columns are added using hardcoded SQL strings like `DATETIME` and `VARCHAR(255)`.
- **Impact**: This makes the application fragile when switching between database engines (e.g., from SQLite to PostgreSQL), as data types vary significantly between engines.

---

## 🏗️ Missing Features (Gaps)

### 1. Unified Incident Management
The `Incident` model and logic are tightly coupled to **Uptime** status.
- **Missing**: Critical SSL failures (Invalid Cert) do not open an "Incident" record. This means there is no audit trail of when an SSL issue started or was resolved, only transient logs.

### 2. Security & Authentication
- **Missing**: The application lacks any form of Authentication (AuthN) or Authorization (AuthZ).
- **Impact**: Any user with network access to the dashboard can add, delete, or modify monitoring targets and notification emails.

### 3. Advanced SEO Signal Checking
The current SEO check is extremely rudimentary.
- **Missing**:
  - `robots.txt` and `sitemap.xml` presence.
  - Canonical tag verification.
  - Image `alt` tag checks.
  - Page load speed analysis.

### 4. Custom Notification Channels
- **Missing**: The system only supports SMTP/Email. Modern monitoring tools typically require Slack, Microsoft Teams, Discord, or Webhook integrations.

---

## 🏁 Final Evaluation
The system has a **solid foundation** with a clear separation of concerns (models, services, workers). However, the **missing alert triggers** in SSL/SEO and the **timezone inconsistencies** are significant functional bugs that must be addressed before production use.
