# 🛡️ SaaS Website Monitoring Platform v2

A high-performance, production-grade website monitoring and intelligence platform. This system provides real-time visibility into site uptime, SSL security, SEO health, network integrity (DNS), and technical performance (Core Web Vitals).

---

## 🚀 Core Functionality

### 1. **Availability & Uptime Monitoring**
*   **High-Frequency Checks**: Multi-threaded HTTP(S) monitoring with configurable intervals (default 60s).
*   **Performance Tracking**: Captures TTFB (Time to First Byte) and total response latency for every check.
*   **Incident Management**: Automatically opens incidents on failure and tracks resolution times.

### 2. **Security & Fleet Intelligence**
*   **SSL/TLS Audit**: Monitors certificate validity, issuer trust, and expiry dates. Provides warnings 14 days before expiry.
*   **Security Header Audit**: Deep scan for hardening headers (`CSP`, `HSTS`, `X-Frame-Options`, `CORS` policy).
*   **DNS Integrity Engine**: Detects DNS hijacking, unauthorized nameserver changes, and resolution failures.
*   **Malware & Mixed Content**: Scans for insecure assets and known malware signatures.

### 3. **SEO & Performance Intelligence**
*   **Deep SEO Audit**: Scans metadata (Title, H1-H3, Meta Desc), image alt tags, robots.txt, and sitemaps.
*   **Real Core Web Vitals**: Uses a headless Chromium engine (Playwright) to collect **real lab data** (LCP, TBT, CLS, FCP) instead of simple proxy estimates.
*   **Technology Fingerprinting**: Identifies the tech stack (Frameworks, CMS, Analytics, CDN) and tracks changes over time.

---

## 🛠️ Technology Stack

### **Backend (Python/Flask)**
*   **Flask 3.x**: Lightweight, modular API and Web interface.
*   **SQLAlchemy**: Robust ORM with migrations and complex relationship management.
*   **Celery + Redis**: Distributed task queue for non-blocking monitoring audits.
*   **Playwright**: Headless browser automation for high-fidelity performance metrics.

### **Frontend (React/TypeScript)**
*   **Vite**: Next-generation frontend tooling for instant HMR.
*   **Tailwind CSS**: Modern utility-first styling for premium aesthetics.
*   **Framer Motion**: Smooth micro-animations and page transitions.
*   **Recharts**: Dynamic visualization of fleet metrics and availability trends.
*   **Lucide React**: Clean, consistent iconography.

---

## 📁 System Architecture

### **Data Flow Cycle**
1.  **Ingestion**: User adds a site URL. The system normalizes the URL and seeds monitoring schedules.
2.  **Scheduling**: `Celery Beat` periodically triggers check tasks based on individual site intervals.
3.  **Execution**: Workers perform multi-layer audits:
    *   `Uptime`: Raw HTTP fetch.
    *   `SSL/DNS`: Network-level socket and resolver checks.
    *   `SEO/Security`: Content parsing and header analysis.
    *   `Performance`: Headless browser navigation (Playwright).
4.  **Persistence**: Results are stored in historical logs; site "Current State" is denormalized for instant dashboard performance.
5.  **Intelligence**: Alerts are dispatched if regressions are detected (e.g., score drop > 5 points or DNS change).

---

## ⚙️ Setup & Installation

### **Prerequisites**
*   Python 3.10+
*   Node.js 18+
*   Redis Server (for Celery)

### **1. Backend Setup**
```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env  # Configure your database and Redis URLs

# Initialize Database
flask db upgrade

# Start Backend
python run.py
```

### **2. Frontend Setup**
```bash
cd frontend
npm install
npm run dev
```

### **3. Worker Setup**
```bash
# Run Celery Worker
celery -A app.workers.tasks.celery worker --loglevel=info -P solo

# Run Celery Beat (Scheduler)
celery -A app.workers.tasks.celery beat --loglevel=info
```

---

## 🧪 Verification & Health Checks

The system includes a self-monitoring dashboard accessible at `/dashboard`. You can verify full functionality by:
1.  Adding a new monitor.
2.  Triggering a **Manual Full Audit** from the Site Detail page.
3.  Monitoring the **Incidents Log** for real-time failure captures.
4.  Exporting a **PDF/JSON Report** for stakeholders.

---
*Created with ❤️ by the Antigravity AI Engineering Team.*
