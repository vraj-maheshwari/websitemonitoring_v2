from unittest.mock import patch

from app import create_app
from app.config.settings import Config
from app.extensions import db
from app.models.site import Site
from app.models.user import User
from app.services.seo_service import run_seo_check
from app.utils.hybrid_fetch import HybridFetchResult


def test_invalid_fetch_does_not_produce_score():
    original_uri = Config.SQLALCHEMY_DATABASE_URI
    Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        try:
            db.drop_all()
            db.create_all()
            user = User(email="test@example.com", password_hash="x")
            db.session.add(user)
            db.session.flush()
            site = Site(
                user_id=user.id,
                name="Example",
                url="https://example.com",
                normalized_url="https://example.com",
            )
            db.session.add(site)
            db.session.commit()

            with patch("app.services.seo_service.fetch_html_for_seo") as mock_fetch:
                mock_fetch.return_value = HybridFetchResult(
                    html="<html>Account suspended</html>",
                    render_mode="HTTP",
                    used_fallback=False,
                    page_size_kb=0.5,
                    status_code=200,
                    ttfb=0.1,
                    response_time=0.2,
                    https_redirect=False,
                    is_up=True,
                    error=None,
                )
                result = run_seo_check(site, db.session)

            assert result["fetch_valid"] is False
            assert result["score"] is None
            assert result["fetch_status"] == "invalid_content"
            assert site.last_seo_fetch_valid is False
        finally:
            Config.SQLALCHEMY_DATABASE_URI = original_uri
