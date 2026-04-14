# 🌐 Website Monitor

A professional-grade website monitoring solution built with Flask, Celery, and SQLAlchemy. It provides real-time tracking of uptime, SSL certificate status, and basic SEO health.

---

## 🚀 Features

### ⏱️ Uptime Monitoring
- **Automatic Checks:** Periodically pings your websites to verify availability.
- **Performance Tracking:** Measures response times and tracks status codes.
- **Incident Management:** Automatically opens and resolves incidents during downtime.
- **Transitions:** Smart monitoring of status changes (UP, DOWN, DEGRADED).

### 🔒 SSL Certificate Monitoring
- **Expiry Alerts:** Tracks certificate expiration dates.
- **Validation:** Verifies certificate chains and common name matches.
- **Issuer Details:** Reports certificate issuer info.

### 🔍 SEO Health Audit
- **Tag Inspection:** Scrapes homepages for `<title>`, `<meta description>`, and `<h1>` tags.
- **SEO Scoring:** Provides a simple health score based on best practices.

### 🔔 Smart Alerting
- **Email Notifications:** Customizable recipient lists for each site.
- **Cooldown Logic:** Prevents notification spam by enforcing a cooldown period between alerts.
- **History:** Keeps a full history of all sent alerts and their delivery status.

### 🛠️ Backend & Performance
- **Asynchronous Tasks:** Uses Celery to perform checks in the background without slowing down the UI.
- **Clean DB:** Automatic log retention policy to prune old data.

---

## 🛠️ Tech Stack

- **Framework:** [Flask](https://flask.palletsprojects.com/)
- **Database:** [SQLAlchemy](https://www.sqlalchemy.org/) (PostgreSQL/SQLite)
- **Task Queue:** [Celery](https://docs.celeryq.dev/) with [Redis](https://redis.io/)
- **Scraping:** [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) & [httpx](https://www.python-httpx.org/)
- **Crypto:** [pyOpenSSL](https://www.pyopenssl.org/) for certificate analysis

---

## 📂 Project Structure

```text
├── app/
│   ├── api/          # REST API endpoints
│   ├── config/       # Centralized configuration (settings.py)
│   ├── models/       # Database schemas (Site, Logs, Incidents)
│   ├── services/     # Core business logic (Monitoring, Alerts, Retention)
│   ├── utils/        # Networking and parsing helpers
│   ├── workers/      # Celery task definitions
│   └── templates/    # Web dashboard UI
├── run.py            # Application entry point
└── requirements.txt  # Project dependencies
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Redis (for Celery)

### 2. Installation
```bash
# Clone the repository
git clone <repo-url>
cd website-monitor

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory:
```env
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///monitor.db  # or postgresql://...
REDIS_URL=redis://localhost:6379/0
RESPONSE_TIME_THRESHOLD=3.0
LOG_RETENTION_DAYS=30

# SMTP for Alerts
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-email
SMTP_PASSWORD=your-password
ALERT_EMAIL=admin@example.com
```

### 4. Running the Application
You need to run three components simultaneously:

**Main App:**
```bash
python run.py
```

**Celery Worker:**
```bash
celery -A app.workers.tasks worker --loglevel=info
```

**Celery Beat (Scheduler):**
```bash
celery -A app.workers.tasks beat --loglevel=info
```

---

## 📡 API Reference (Summary)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/sites` | Add a new website for monitoring |
| `GET` | `/api/sites` | List all monitored sites |
| `GET` | `/api/check/<id>` | Trigger manual uptime check |
| `GET` | `/api/check-ssl/<id>`| Trigger manual SSL check |
| `GET` | `/api/logs/<id>` | Fetch recent uptime logs |

---

## 📝 License
MIT License. Free to use and modify.
