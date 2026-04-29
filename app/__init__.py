import os
import sqlite3
from urllib.parse import unquote

from flask import Flask
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.config.settings import Config
from app.models.site import Site
from app.services.monitoring_service import prepare_site

def create_app():
    flask_app = Flask(__name__)   # ✅ NEVER use name 'app' here

    flask_app.config.from_object(Config)
    _fallback_sqlite_if_unusable(flask_app)

    db.init_app(flask_app)

    # ✅ load models
    with flask_app.app_context():
        import app.models.site
        import app.models.user
        import app.models.uptime_log
        import app.models.ssl_log
        import app.models.seo_log
        import app.models.incident
        import app.models.alert_history
        import app.models.site_notification
        import app.models.daily_uptime_summary
        import app.models.daily_ssl_summary
        import app.models.daily_seo_summary

        # db.drop_all()  # ✅ Clean reset (commented out after first run)
        try:
            db.create_all()
            db.session.commit()
        except OperationalError as exc:
            raise RuntimeError(
                "Database initialization failed. If you are using SQLite, check "
                "that the configured database file is not locked or corrupt."
            ) from exc

    # ✅ import routes AFTER app creation
    from app.api.routes import api_bp, web_bp

    flask_app.register_blueprint(web_bp)
    flask_app.register_blueprint(api_bp, url_prefix="/api")

    return flask_app


def _fallback_sqlite_if_unusable(flask_app: Flask) -> None:
    uri = flask_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not uri.startswith("sqlite:///") or uri == "sqlite:///:memory:":
        return

    db_path = unquote(uri.removeprefix("sqlite:///"))
    if not os.path.isabs(db_path):
        db_path = os.path.join(flask_app.instance_path, db_path)

    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS __sqlite_write_probe (id INTEGER)")
        conn.execute("DROP TABLE IF EXISTS __sqlite_write_probe")
        conn.commit()
        conn.close()
    except sqlite3.Error:
        flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
