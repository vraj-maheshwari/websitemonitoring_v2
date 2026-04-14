from sqlalchemy import inspect, text

from app.extensions import db


SITE_COLUMN_DEFINITIONS = {
    "name": "VARCHAR(255)",
    "normalized_url": "VARCHAR(2048)",
    "last_uptime_check_at": "DATETIME",
    "last_ssl_check_at": "DATETIME",
    "last_seo_check_at": "DATETIME",
    "next_uptime_check_at": "DATETIME",
    "next_ssl_check_at": "DATETIME",
    "next_seo_check_at": "DATETIME",
    "next_check_at": "DATETIME",
    "current_status": "VARCHAR(32) DEFAULT 'PENDING'",
    "last_status_code": "INTEGER",
    "last_response_time": "FLOAT",
    "last_error_message": "TEXT",
    "incident_opened_at": "DATETIME",
    "last_incident_resolved_at": "DATETIME",
    "ssl_status": "VARCHAR(32) DEFAULT 'PENDING'",
    "ssl_issuer": "VARCHAR(512)",
    "ssl_expiry_date": "DATETIME",
    "ssl_days_remaining": "INTEGER",
    "ssl_last_error": "TEXT",
    "seo_status": "VARCHAR(32) DEFAULT 'PENDING'",
    "seo_title": "VARCHAR(512)",
    "seo_meta_description": "TEXT",
    "seo_has_meta": "BOOLEAN DEFAULT 0",
    "seo_has_h1": "BOOLEAN DEFAULT 0",
    "seo_h1_text": "VARCHAR(512)",
    "seo_score": "INTEGER DEFAULT 0",
    "seo_last_error": "TEXT",
}

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_sites_next_check_at ON sites (next_check_at)",
    "CREATE INDEX IF NOT EXISTS ix_sites_current_status ON sites (current_status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_sites_normalized_url ON sites (normalized_url)",
    "CREATE INDEX IF NOT EXISTS ix_uptime_logs_site_checked_at ON uptime_logs (site_id, checked_at)",
    "CREATE INDEX IF NOT EXISTS ix_ssl_logs_site_checked_at ON ssl_logs (site_id, checked_at)",
    "CREATE INDEX IF NOT EXISTS ix_seo_logs_site_checked_at ON seo_logs (site_id, checked_at)",
]


def upgrade_schema() -> None:
    inspector = inspect(db.engine)

    if "sites" in inspector.get_table_names():
        _ensure_site_columns(inspector)

    for statement in INDEX_STATEMENTS:
        db.session.execute(text(statement))

    db.session.commit()


def _ensure_site_columns(inspector) -> None:
    existing_columns = {column["name"] for column in inspector.get_columns("sites")}

    for column_name, column_sql in SITE_COLUMN_DEFINITIONS.items():
        if column_name in existing_columns:
            continue
        db.session.execute(text(f"ALTER TABLE sites ADD COLUMN {column_name} {column_sql}"))

