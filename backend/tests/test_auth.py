"""
Authentication, JWT and session-security tests.

Everything runs against a fresh in-memory SQLite database per test, with
test-only secrets from conftest.py.
"""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import models  # noqa: F401
from config import get_settings
from models import AuditLog, LoginAttempt, PrintRequest, RefreshSession, User

PASSWORD = "CorrectHorse123"
XRW = {"X-Requested-With": "XMLHttpRequest"}


# ------------------------------------------------------------------ fixtures

@pytest.fixture(autouse=True)
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    from database import get_session
    from main import app

    def override():
        yield session
    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ------------------------------------------------------------------- helpers

def signup(client, email="alice@uni.edu", password=PASSWORD, name="Alice"):
    return client.post("/api/auth/signup", json={"email": email, "full_name": name, "password": password})


def login(client, email="alice@uni.edu", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def refresh_with(client, cookie_value, xrw=True):
    """Call /refresh sending exactly this refresh cookie (nothing from the jar)."""
    client.cookies.clear()
    headers = {"Cookie": f"pp_refresh={cookie_value}"}
    if xrw:
        headers.update(XRW)
    return client.post("/api/auth/refresh", headers=headers)


def logged_in(client, email="alice@uni.edu"):
    """Sign up a user and return (access_token, refresh_cookie)."""
    res = signup(client, email=email)
    assert res.status_code == 201, res.text
    return res.json()["access_token"], res.cookies["pp_refresh"]


def b64url_decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


# ------------------------------------------------------------ signup / login

def test_signup_and_login_success(client):
    res = signup(client, email="Alice@Uni.Edu")
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "alice@uni.edu"  # stored lower-case
    assert body["user"]["role"] == "user"

    cookie_header = res.headers["set-cookie"].lower()
    assert "pp_refresh=" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/api/auth" in cookie_header

    res = login(client, email="alice@uni.edu")
    assert res.status_code == 200
    me = client.get("/api/auth/me", headers=bearer(res.json()["access_token"]))
    assert me.status_code == 200 and me.json()["full_name"] == "Alice"


def test_passwords_and_refresh_tokens_are_never_stored_in_plaintext(client, session):
    res = signup(client)
    raw_cookie = res.cookies["pp_refresh"]
    user = session.exec(select(User)).one()
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    rs = session.exec(select(RefreshSession)).one()
    assert rs.token_hash != raw_cookie
    assert rs.token_hash == hashlib.sha256(raw_cookie.encode()).hexdigest()


def test_duplicate_email_is_rejected_case_insensitively(client):
    assert signup(client, email="bob@uni.edu").status_code == 201
    res = signup(client, email="BOB@uni.edu")
    assert res.status_code == 409
    assert res.json()["detail"] == "Email is already registered"


@pytest.mark.parametrize("weak", ["short1", "onlyletterspassword", "1234567890123", "x" * 129 + "1"])
def test_weak_passwords_are_rejected(client, weak):
    res = signup(client, password=weak)
    assert res.status_code == 422


def test_signup_can_never_create_an_admin(client, session):
    res = client.post("/api/auth/signup", json={
        "email": "sneaky@uni.edu", "full_name": "Sneaky", "password": PASSWORD, "role": "admin",
    })
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "user"
    assert session.exec(select(User)).one().role.value == "user"


def test_wrong_password_returns_generic_401_and_is_recorded(client, session):
    signup(client)
    wrong = login(client, password="WrongPassword999")
    unknown = login(client, email="nobody@uni.edu")
    assert wrong.status_code == unknown.status_code == 401
    # Same message for both -> attackers cannot tell which emails exist.
    assert wrong.json()["detail"] == unknown.json()["detail"] == "Invalid email or password"

    failures = session.exec(select(LoginAttempt).where(LoginAttempt.success == False)).all()  # noqa: E712
    assert {f.failure_reason for f in failures} == {"bad_password", "unknown_email"}
    actions = [a.action for a in session.exec(select(AuditLog)).all()]
    assert actions.count("auth.login_failed") == 2


def test_account_locks_after_five_wrong_passwords(client, session):
    signup(client)
    for _ in range(5):
        assert login(client, password="WrongPassword999").status_code == 401
    res = login(client)  # correct password, but the account is now locked
    assert res.status_code == 429
    assert "locked" in res.json()["detail"].lower()
    assert any(a.action == "auth.account_locked" for a in session.exec(select(AuditLog)).all())


def test_too_many_failures_from_one_ip_returns_429(client, monkeypatch):
    monkeypatch.setenv("LOGIN_IP_FAIL_LIMIT", "3")
    get_settings.cache_clear()
    for i in range(3):
        assert login(client, email=f"ghost{i}@uni.edu").status_code == 401
    res = login(client, email="ghost9@uni.edu")
    assert res.status_code == 429
    assert "Retry-After" in res.headers


# ------------------------------------------------------------ token checks

def test_missing_token_returns_401(client):
    assert client.get("/api/print-requests").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("token", ["abc.def.ghi", "not-a-jwt", ""])
def test_invalid_token_returns_401(client, token):
    res = client.get("/api/auth/me", headers=bearer(token))
    assert res.status_code == 401


def test_tampered_token_returns_401(client):
    access, _ = logged_in(client)
    header, payload, signature = access.split(".")
    claims = json.loads(b64url_decode(payload))
    claims["role"] = "admin"  # try to promote ourselves
    forged = ".".join([header, b64url_encode(json.dumps(claims).encode()), signature])
    res = client.get("/api/auth/me", headers=bearer(forged))
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid access token"


def test_token_signed_with_another_secret_returns_401(client):
    access, _ = logged_in(client)
    claims = jwt.decode(access, options={"verify_signature": False})
    forged = jwt.encode(claims, "attacker-secret-attacker-secret-attacker!!", algorithm="HS256")
    assert client.get("/api/auth/me", headers=bearer(forged)).status_code == 401


def test_expired_access_token_returns_401(client):
    access, _ = logged_in(client)
    claims = jwt.decode(access, options={"verify_signature": False})
    past = datetime.now(timezone.utc) - timedelta(minutes=30)
    claims.update(iat=past, exp=past + timedelta(minutes=15))
    expired = jwt.encode(claims, get_settings().jwt_secret, algorithm="HS256")
    res = client.get("/api/auth/me", headers=bearer(expired))
    assert res.status_code == 401
    assert res.json()["detail"] == "Access token expired"


def test_access_token_contains_user_id_and_role_and_lives_at_most_15_minutes(client):
    access, _ = logged_in(client)
    claims = jwt.decode(access, get_settings().jwt_secret, algorithms=["HS256"])
    assert claims["sub"] and claims["role"] == "user" and claims["type"] == "access"
    assert claims["exp"] - claims["iat"] <= 15 * 60


# ------------------------------------------------------ refresh and rotation

def test_refresh_rotates_the_refresh_token(client):
    _, cookie1 = logged_in(client)
    res = refresh_with(client, cookie1)
    assert res.status_code == 200
    cookie2 = res.cookies["pp_refresh"]
    assert cookie2 != cookie1
    assert client.get("/api/auth/me", headers=bearer(res.json()["access_token"])).status_code == 200
    assert refresh_with(client, cookie2).status_code == 200  # the new token keeps working


def test_refresh_requires_csrf_header(client):
    _, cookie = logged_in(client)
    assert refresh_with(client, cookie, xrw=False).status_code == 403


def test_reusing_an_old_refresh_token_revokes_the_session(client, session):
    access, cookie1 = logged_in(client)
    cookie2 = refresh_with(client, cookie1).cookies["pp_refresh"]

    # Pretend the rotation happened a minute ago (outside the 30 s multi-tab grace window).
    rs = session.exec(select(RefreshSession)).one()
    rs.last_used_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    session.add(rs)
    session.commit()

    assert refresh_with(client, cookie1).status_code == 401   # stolen old token -> rejected
    assert refresh_with(client, cookie2).status_code == 401   # ...and the whole session is dead
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 401
    session.refresh(rs)
    assert rs.revoked_reason == "refresh_token_reuse"
    assert any(a.action == "auth.refresh_reuse_detected" for a in session.exec(select(AuditLog)).all())


def test_revoked_refresh_token_is_rejected(client):
    access, cookie = logged_in(client)
    sessions = client.get("/api/auth/sessions", headers=bearer(access)).json()
    assert client.delete(f"/api/auth/sessions/{sessions[0]['id']}", headers=bearer(access)).status_code == 204
    assert refresh_with(client, cookie).status_code == 401


def test_random_refresh_token_is_rejected(client):
    logged_in(client)
    assert refresh_with(client, "made-up-token").status_code == 401


# ---------------------------------------------------------------------- logout

def test_logout_invalidates_access_and_refresh_tokens(client):
    access, cookie = logged_in(client)
    client.cookies.clear()
    res = client.post("/api/auth/logout",
                      headers={**XRW, **bearer(access), "Cookie": f"pp_refresh={cookie}"})
    assert res.status_code == 204
    # The 15-minute access token is dead immediately, not after it expires.
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 401
    assert refresh_with(client, cookie).status_code == 401


# --------------------------------------------------------------------- sessions

def test_list_and_revoke_sessions(client):
    access1, _ = logged_in(client)
    access2 = login(client).json()["access_token"]  # a second device

    sessions = client.get("/api/auth/sessions", headers=bearer(access1)).json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["current"]]
    other = [s for s in sessions if not s["current"]]
    assert len(current) == 1 and len(other) == 1

    assert client.delete(f"/api/auth/sessions/{other[0]['id']}", headers=bearer(access1)).status_code == 204
    assert client.get("/api/auth/me", headers=bearer(access2)).status_code == 401  # device 2 logged out
    assert client.get("/api/auth/me", headers=bearer(access1)).status_code == 200


def test_cannot_revoke_another_users_session(client):
    alice, _ = logged_in(client, email="alice@uni.edu")
    bob, _ = logged_in(client, email="bob@uni.edu")
    bob_session = client.get("/api/auth/sessions", headers=bearer(bob)).json()[0]["id"]
    res = client.delete(f"/api/auth/sessions/{bob_session}", headers=bearer(alice))
    assert res.status_code == 404
    assert client.get("/api/auth/me", headers=bearer(bob)).status_code == 200


def test_revoke_other_sessions_keeps_current(client):
    access1, _ = logged_in(client)
    access2 = login(client).json()["access_token"]
    access3 = login(client).json()["access_token"]
    res = client.post("/api/auth/sessions/revoke-others", headers=bearer(access1))
    assert res.json() == {"revoked": 2}
    assert client.get("/api/auth/me", headers=bearer(access1)).status_code == 200
    assert client.get("/api/auth/me", headers=bearer(access2)).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(access3)).status_code == 401


# ---------------------------------------------------------- profile / password

def test_password_change(client, session):
    access, _ = logged_in(client)
    other_device = login(client).json()["access_token"]

    bad = client.post("/api/users/me/password", headers=bearer(access),
                      json={"current_password": "WrongPassword999", "new_password": "BrandNewPass456"})
    assert bad.status_code == 400
    assert any(a.action == "user.password_change_failed" for a in session.exec(select(AuditLog)).all())

    weak = client.post("/api/users/me/password", headers=bearer(access),
                       json={"current_password": PASSWORD, "new_password": "weak"})
    assert weak.status_code == 422

    ok = client.post("/api/users/me/password", headers=bearer(access),
                     json={"current_password": PASSWORD, "new_password": "BrandNewPass456"})
    assert ok.status_code == 200 and ok.json()["other_sessions_revoked"] == 1

    assert login(client).status_code == 401                                   # old password
    assert login(client, password="BrandNewPass456").status_code == 200       # new password
    assert client.get("/api/auth/me", headers=bearer(other_device)).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 200


def test_profile_view_and_update(client):
    access, _ = logged_in(client, email="alice@uni.edu")
    logged_in(client, email="taken@uni.edu")

    assert client.get("/api/users/me", headers=bearer(access)).json()["full_name"] == "Alice"
    res = client.patch("/api/users/me", headers=bearer(access), json={"full_name": "Alice Smith"})
    assert res.status_code == 200 and res.json()["full_name"] == "Alice Smith"

    no_pw = client.patch("/api/users/me", headers=bearer(access), json={"email": "new@uni.edu"})
    assert no_pw.status_code == 400
    dup = client.patch("/api/users/me", headers=bearer(access),
                       json={"email": "taken@uni.edu", "current_password": PASSWORD})
    assert dup.status_code == 409
    ok = client.patch("/api/users/me", headers=bearer(access),
                      json={"email": "New@Uni.Edu", "current_password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["email"] == "new@uni.edu"


# ---------------------------------------------------------------- banned users

def test_banned_user_is_rejected_on_next_request(client, session):
    access, cookie = logged_in(client)
    assert client.get("/api/print-requests", headers=bearer(access)).status_code == 200

    user = session.exec(select(User)).one()
    user.is_banned = True
    user.ban_reason = "test"
    session.add(user)
    session.commit()

    # Same, still-unexpired token -> rejected at once, because the ban is read from the DB.
    res = client.get("/api/print-requests", headers=bearer(access))
    assert res.status_code == 403 and res.json()["detail"] == "Account is banned"
    assert refresh_with(client, cookie).status_code == 403
    assert login(client).status_code == 403


# ------------------------------------------------------------- print requests

def test_new_print_requests_record_their_owner(client, session):
    access, _ = logged_in(client)
    res = client.post("/api/print-requests", headers=bearer(access), json={
        "student_name": "Alice", "document_name": "a.pdf", "copies": 1, "print_type": "Color",
    })
    assert res.status_code == 201
    user = session.exec(select(User)).one()
    assert session.get(PrintRequest, res.json()["id"]).owner_id == user.id


# ------------------------------------------------------------- configuration

def test_settings_refuse_weak_secrets(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "too-short")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_settings()


def test_settings_refuse_access_tokens_longer_than_15_minutes(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "60")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="ACCESS_TOKEN_MINUTES"):
        get_settings()


def test_cookies_are_always_secure_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()
    assert get_settings().cookie_secure is True
