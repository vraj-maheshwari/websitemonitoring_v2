from app.extensions import db
from app.models.site import Site
from app.models.user import User


def _create_user(email="user@example.com", password="password123"):
    user = User(email=email.lower(), is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _create_site(user, url):
    site = Site(user_id=user.id, url=url, normalized_url=url.lower())
    db.session.add(site)
    db.session.commit()
    return site


def test_register_valid_email_and_password_creates_user(client, app):
    response = client.post(
        "/register",
        data={
            "email": "NewUser@Example.com ",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(email="newuser@example.com").first()
        assert user is not None
        assert user.check_password("password123")


def test_register_duplicate_email_returns_error(client, app):
    with app.app_context():
        _create_user("dupe@example.com")

    response = client.post(
        "/register",
        data={
            "email": "DUPE@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
    )

    assert response.status_code == 409
    assert b"An account with this email already exists" in response.data
    with app.app_context():
        assert User.query.filter_by(email="dupe@example.com").count() == 1


def test_register_invalid_email_format_returns_error(client):
    response = client.post(
        "/register",
        data={
            "email": "not-an-email",
            "password": "password123",
            "confirm_password": "password123",
        },
    )

    assert response.status_code == 400
    assert b"Invalid email format" in response.data


def test_register_mismatched_passwords_returns_error(client):
    response = client.post(
        "/register",
        data={
            "email": "mismatch@example.com",
            "password": "password123",
            "confirm_password": "different123",
        },
    )

    assert response.status_code == 400
    assert b"Passwords do not match" in response.data


def test_login_correct_credentials_sets_session(client, app):
    with app.app_context():
        user = _create_user("login@example.com", "password123")
        user_id = user.id

    response = client.post(
        "/login",
        data={"email": " LOGIN@example.com ", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == user_id
        assert sess["user_email"] == "login@example.com"


def test_login_wrong_password_returns_error_without_session(client, app):
    with app.app_context():
        _create_user("wrong@example.com", "password123")

    response = client.post(
        "/api/auth/login",
        json={"email": "wrong@example.com", "password": "badpassword"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid email or password"
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_unknown_email_returns_error(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid email or password"


def test_logout_clears_session(client, app):
    with app.app_context():
        user = _create_user("logout@example.com", "password123")
        user_id = user.id
        user_email = user.email
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_email"] = user_email

    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert "user_email" not in sess


def test_api_sites_without_session_returns_401(client):
    response = client.get("/api/sites")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Authentication required"


def test_api_sites_with_session_returns_only_owned_sites(client, app):
    with app.app_context():
        owner = _create_user("owner@example.com")
        other = _create_user("other@example.com")
        owned = _create_site(owner, "https://owned.example")
        _create_site(other, "https://other.example")
        owned_id = owned.id
        owner_id = owner.id
        owner_email = owner.email
    with client.session_transaction() as sess:
        sess["user_id"] = owner_id
        sess["user_email"] = owner_email

    response = client.get("/api/sites")

    assert response.status_code == 200
    payload = response.get_json()
    assert [site["id"] for site in payload] == [owned_id]


def test_direct_access_to_another_users_site_returns_404(client, app):
    with app.app_context():
        owner = _create_user("owner@example.com")
        other = _create_user("other@example.com")
        other_site = _create_site(other, "https://other.example")
        other_site_id = other_site.id
        owner_id = owner.id
        owner_email = owner.email
    with client.session_transaction() as sess:
        sess["user_id"] = owner_id
        sess["user_email"] = owner_email

    response = client.get(f"/api/sites/{other_site_id}")

    assert response.status_code == 404
