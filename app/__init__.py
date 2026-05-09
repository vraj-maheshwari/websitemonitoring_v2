import os
import sqlite3
from urllib.parse import unquote

from flask import Flask, jsonify
from flask_wtf.csrf import CSRFProtect, generate_csrf
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.config.settings import Config

csrf = CSRFProtect()

def create_app(test_config: dict | None = None):
    flask_app = Flask(__name__)   # ✅ NEVER use name 'app' here

    flask_app.config.from_object(Config)
    if test_config:
        flask_app.config.update(test_config)
    if not flask_app.config.get("DEBUG") and not flask_app.config.get("TESTING"):
        flask_app.config["SESSION_COOKIE_SECURE"] = True
    _fallback_sqlite_if_unusable(flask_app)

    db.init_app(flask_app)
    csrf.init_app(flask_app)
    flask_app.jinja_env.globals['csrf_token'] = generate_csrf

    # Add time filters
    from app.utils.time import to_local
    flask_app.jinja_env.filters['localtime'] = to_local
    flask_app.jinja_env.filters['strftime'] = lambda dt, fmt: dt.strftime(fmt) if dt is not None else ''

    # ✅ load models
    with flask_app.app_context():
        import app.models.site
        import app.models.user
        import app.models.uptime_log
        import app.models.ssl_log
        import app.models.seo_log
        import app.models.dns_log
        import app.models.incident
        import app.models.alert_history
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
        _ensure_dev_user(flask_app)

    # ✅ import routes AFTER app creation
    from app.api.routes import api_bp, web_bp

    flask_app.register_blueprint(web_bp)
    flask_app.register_blueprint(api_bp, url_prefix="/api")
    csrf.exempt(api_bp)

    @flask_app.errorhandler(500)
    def handle_500(e):
        import traceback
        error_details = traceback.format_exc()
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e),
            "traceback": error_details
        }), 500

    return flask_app


def _ensure_dev_user(flask_app: Flask) -> None:
    if not flask_app.config.get("DEBUG"):
        return

    from app.models.user import User

    if User.query.filter_by(email="dev@localhost.test").first() is not None:
        return
    user = User(email="dev@localhost.test", is_active=True)
    user.set_password("devpassword123")
    db.session.add(user)
    db.session.commit()


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
