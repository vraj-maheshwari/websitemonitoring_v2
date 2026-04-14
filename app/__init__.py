from flask import Flask
from app.extensions import db
from app.config.settings import Config
from app.models.site import Site
from app.services.monitoring_service import prepare_site
from app.services.schema_service import upgrade_schema

def create_app():
    flask_app = Flask(__name__)   # ✅ NEVER use name 'app' here

    flask_app.config.from_object(Config)

    db.init_app(flask_app)

    # ✅ load models
    with flask_app.app_context():
        import app.models.site
        import app.models.uptime_log
        import app.models.ssl_log
        import app.models.seo_log
        import app.models.incident
        import app.models.alert_history
        import app.models.site_notification
        import app.models.daily_uptime_summary

        db.create_all()
        upgrade_schema()
        for site in Site.query.all():
            prepare_site(site)
        db.session.commit()

    # ✅ import routes AFTER app creation
    from app.api.routes import api_bp, web_bp

    flask_app.register_blueprint(web_bp)
    flask_app.register_blueprint(api_bp, url_prefix="/api")

    return flask_app
