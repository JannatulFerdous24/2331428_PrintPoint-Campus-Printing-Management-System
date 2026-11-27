"""
OPT-IN integration tests: authentication against the real printpoint-dev
Supabase PostgreSQL database (never Production).

Skipped unless RUN_PG_INTEGRATION=1. Run with:
    RUN_PG_INTEGRATION=1 .venv/Scripts/python.exe -m pytest tests/test_auth_postgres_integration.py -v

Safety:
* Refuses to run unless DATABASE_URL in backend/.env points at the dev project.
* Uses the app's real connection settings (transaction pooler, NullPool,
  prepared statements off, SSL).
* Every account uses a unique, recognisable email: pptest+<run-id>-<name>@uni.edu
* The last test deletes ONLY rows belonging to those accounts and checks that
  every table is back to its row count from before the run.
* JWTs are signed with the test-only secrets from conftest.py, never real ones.
"""

import json
import base64
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from itertools import count

from sqlalchemy import false, func, or_, text
from sqlalchemy.pool import NullPool
from sqlmodel import Session, select

from config import get_settings
from database import build_engine, normalize_database_url
from models import AuditLog, LoginAttempt, PrintRequest, RefreshSession, User

DEV_PROJECT_REF = "vxgubnunysotatnbfpip"  # printpoint-dev (us-east-1)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PG_INTEGRATION") != "1",
    reason="PostgreSQL integration tests are opt-in (set RUN_PG_INTEGRATION=1)",
)

RUN_ID = uuid.uuid4().hex[:10]
EMAIL_LIKE = f"pptest+{RUN_ID}-%@uni.edu"
PASSWORD = "IntegrationPass123"
XRW = {"X-Requested-With": "XMLHttpRequest"}
TABLES = ["users", "refresh_sessions", "login_attempts", "audit_logs",
          "groups", "group_members", "print_requests", "print_request_status_history"]


def email(name: str) -> str:
    return f"pptest+{RUN_ID}-{name}@uni.edu"


# ------------------------------------------------------------------ fixtures

@pytest.fixture(scope="module")
def engine():
    url = dotenv_values(Path(__file__).resolve().parent.parent / ".env").get("DATABASE_URL") or ""
    m = re.match(r"postgresql://postgres\.([a-z0-9]+):", url)
    if not m or m.group(1) != DEV_PROJECT_REF or os.getenv("VERCEL"):
        pytest.exit("SAFETY STOP: DATABASE_URL is not the printpoint-dev project", returncode=2)
    eng = build_engine(normalize_database_url(url))
    yield eng
    eng.dispose()


@pytest.fixture(scope="module")
def baseline(engine):
    with engine.connect() as conn:
        return {t: conn.execute(text(f'select count(*) from public."{t}"')).scalar() for t in TABLES}


@pytest.fixture(scope="module")
def client(engine, baseline):
    from database import get_session
    from main import app

    def override():
        with Session(engine) as s:
            yield s

    get_settings.cache_clear()
    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    cleanup(engine)  # safety net if the final test did not run


@pytest.fixture(autouse=True)
def own_ip(client, request):
    """Give every test its own client IP so per-IP rate limits never interfere."""
    client.headers["X-Forwarded-For"] = f"198.51.100.{next(_ip_counter)}"
    client.cookies.clear()
    yield


_ip_counter = count(1)


def db(engine) -> Session:
    return Session(engine)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def signup(client, name):
    res = client.post("/api/auth/signup", json={"email": email(name), "full_name": f"PG Test {name}",
                                                 "password": PASSWORD})
    assert res.status_code == 201, res.text
    return res.json()["access_token"], res.cookies["pp_refresh"]


def login(client, name, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email(name), "password": password})


def refresh_with(client, cookie):
    client.cookies.clear()
    return client.post("/api/auth/refresh", headers={**XRW, "Cookie": f"pp_refresh={cookie}"})


def cleanup(engine) -> dict:
    """Delete only rows that belong to this run's test accounts."""
    deleted = {}
    with Session(engine) as s:
        ids = list(s.exec(select(User.id).where(User.email.like(EMAIL_LIKE))).all())
        id_strs = [str(i) for i in ids]
        conds = [AuditLog.details["email"].as_string().like(EMAIL_LIKE)]
        if ids:
            conds += [AuditLog.actor_id.in_(ids),
                      (AuditLog.target_type == "user") & AuditLog.target_id.in_(id_strs)]
        for model, cond in [
            (AuditLog, or_(*conds)),
            (LoginAttempt, or_(LoginAttempt.email_attempted.like(EMAIL_LIKE),
                               LoginAttempt.user_id.in_(ids) if ids else false())),
            (PrintRequest, PrintRequest.owner_id.in_(ids) if ids else false()),
            (RefreshSession, RefreshSession.user_id.in_(ids) if ids else false()),
            (User, User.id.in_(ids) if ids else false()),
        ]:
            rows = s.exec(select(model).where(cond)).all()
            for r in rows:
                s.delete(r)
            s.flush()
            deleted[model.__tablename__] = len(rows)
        s.commit()
    return deleted


# --------------------------------------------------------------------- tests

def test_01_target_is_printpoint_dev_with_production_style_engine(engine):
    assert engine.dialect.name == "postgresql"
    assert isinstance(engine.pool, NullPool)
    with engine.connect() as conn:
        assert conn.execute(text("select version_num from alembic_version")).scalar() == "0004_cost_and_payment"


def test_02_signup_and_login_store_correct_postgres_types(client, engine):
    access, _ = signup(client, "alice")
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 200
    assert login(client, "alice").status_code == 200
    with db(engine) as s:
        u = s.exec(select(User).where(User.email == email("alice"))).one()
        assert u.role.value == "user"
        assert u.password_hash.startswith("$argon2id$")
        assert u.created_at.tzinfo is not None  # TIMESTAMPTZ round-trips as aware UTC
        assert len(s.exec(select(RefreshSession).where(RefreshSession.user_id == u.id)).all()) == 2


def test_03_duplicate_email_is_rejected(client):
    signup(client, "dup")
    res = client.post("/api/auth/signup", json={"email": email("dup").upper(), "full_name": "x",
                                                 "password": PASSWORD})
    assert res.status_code == 409


def test_04_wrong_password_lockout_and_timestamp_comparisons(client, engine):
    signup(client, "bob")
    for _ in range(5):
        assert login(client, "bob", "WrongPassword999").status_code == 401
    assert login(client, "bob").status_code == 429  # locked_until > now() compared on PostgreSQL
    with db(engine) as s:
        u = s.exec(select(User).where(User.email == email("bob"))).one()
        assert u.locked_until is not None and u.locked_until > datetime.now(timezone.utc)
        failed = s.exec(select(LoginAttempt).where(LoginAttempt.user_id == u.id,
                                                   LoginAttempt.success == False)).all()  # noqa: E712
        assert len(failed) == 6 and all(a.created_at.tzinfo for a in failed)


def test_05_ip_rate_limit_window_query_on_postgres(client, monkeypatch):
    monkeypatch.setenv("LOGIN_IP_FAIL_LIMIT", "3")
    get_settings.cache_clear()
    try:
        for i in range(3):
            assert login(client, f"ghost{i}").status_code == 401
        assert login(client, "ghost9").status_code == 429
    finally:
        monkeypatch.delenv("LOGIN_IP_FAIL_LIMIT")
        get_settings.cache_clear()


def test_06_jwt_validation(client):
    access, _ = signup(client, "carol")
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    h, p, sig = access.split(".")
    claims = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    claims["role"] = "admin"
    forged = ".".join([h, base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode(), sig])
    assert client.get("/api/auth/me", headers=bearer(forged)).status_code == 401
    real = jwt.decode(access, options={"verify_signature": False})
    past = datetime.now(timezone.utc) - timedelta(minutes=30)
    real.update(iat=past, exp=past + timedelta(minutes=15))
    expired = jwt.encode(real, get_settings().jwt_secret, algorithm="HS256")
    res = client.get("/api/auth/me", headers=bearer(expired))
    assert res.status_code == 401 and res.json()["detail"] == "Access token expired"


def test_07_refresh_rotation_and_reuse_detection(client, engine):
    access, cookie1 = signup(client, "dave")
    res = refresh_with(client, cookie1)
    assert res.status_code == 200
    cookie2 = res.cookies["pp_refresh"]
    assert cookie2 != cookie1
    with db(engine) as s:
        u = s.exec(select(User).where(User.email == email("dave"))).one()
        rs = s.exec(select(RefreshSession).where(RefreshSession.user_id == u.id)).one()
        rs.last_used_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        s.add(rs)
        s.commit()
        rs_id = rs.id
    assert refresh_with(client, cookie1).status_code == 401
    assert refresh_with(client, cookie2).status_code == 401
    with db(engine) as s:
        assert s.get(RefreshSession, rs_id).revoked_reason == "refresh_token_reuse"


def test_08_logout_invalidates_both_tokens(client):
    access, cookie = signup(client, "erin")
    client.cookies.clear()
    res = client.post("/api/auth/logout", headers={**XRW, **bearer(access), "Cookie": f"pp_refresh={cookie}"})
    assert res.status_code == 204
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 401
    assert refresh_with(client, cookie).status_code == 401


def test_09_session_listing_and_revocation(client):
    a1, _ = signup(client, "frank")
    a2 = login(client, "frank").json()["access_token"]
    sessions = client.get("/api/auth/sessions", headers=bearer(a1)).json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["current"])
    assert client.delete(f"/api/auth/sessions/{other['id']}", headers=bearer(a1)).status_code == 204
    assert client.get("/api/auth/me", headers=bearer(a2)).status_code == 401
    g, _ = signup(client, "grace")
    g_sid = client.get("/api/auth/sessions", headers=bearer(g)).json()[0]["id"]
    assert client.delete(f"/api/auth/sessions/{g_sid}", headers=bearer(a1)).status_code == 404


def test_10_password_change_and_ban(client, engine):
    a1, _ = signup(client, "henry")
    a2 = login(client, "henry").json()["access_token"]
    res = client.post("/api/users/me/password", headers=bearer(a1),
                      json={"current_password": PASSWORD, "new_password": "ChangedPass456"})
    assert res.status_code == 200 and res.json()["other_sessions_revoked"] == 1
    assert client.get("/api/auth/me", headers=bearer(a2)).status_code == 401
    with db(engine) as s:
        u = s.exec(select(User).where(User.email == email("henry"))).one()
        u.is_banned = True
        s.add(u)
        s.commit()
    assert client.get("/api/auth/me", headers=bearer(a1)).status_code == 403


def test_11_print_request_owner_and_enums_on_postgres(client, engine):
    access, _ = signup(client, "ivy")
    res = client.post("/api/print-requests", headers=bearer(access), json={
        "student_name": "PG Test ivy", "document_name": "pg.pdf", "copies": 2, "print_type": "Color"})
    assert res.status_code == 201 and res.json()["print_type"] == "Color"
    with db(engine) as s:
        pr = s.get(PrintRequest, res.json()["id"])
        u = s.exec(select(User).where(User.email == email("ivy"))).one()
        assert pr.owner_id == u.id and pr.created_at.tzinfo is not None


def test_12_audit_log_json_and_timestamps_on_postgres(engine):
    with db(engine) as s:
        ids = s.exec(select(User.id).where(User.email.like(EMAIL_LIKE))).all()
        events = s.exec(select(AuditLog).where(AuditLog.actor_id.in_(ids))).all()
        actions = {e.action for e in events}
        for expected in ("auth.signup", "auth.login", "auth.login_failed", "auth.account_locked",
                         "auth.logout", "auth.refresh_reuse_detected", "session.revoke",
                         "user.password_change"):
            assert expected in actions, f"missing audit event {expected}"
        assert all(e.created_at.tzinfo is not None for e in events)
        # JSONB path query executed by PostgreSQL:
        bad_pw = s.exec(select(func.count()).select_from(AuditLog).where(
            AuditLog.actor_id.in_(ids), AuditLog.details["reason"].as_string() == "bad_password")).one()
        assert bad_pw >= 4
        unknown = s.exec(select(AuditLog).where(
            AuditLog.details["email"].as_string().like(EMAIL_LIKE),
            AuditLog.action == "auth.login_failed")).all()
        assert unknown and all(isinstance(e.details, dict) for e in unknown)
        assert all(e.ip_address and e.ip_address.startswith("198.51.100.") for e in events)


def test_13_cleanup_removes_only_this_runs_data(engine, baseline):
    deleted = cleanup(engine)
    print("\nrows deleted per table:", deleted)
    assert deleted["users"] >= 10
    with engine.connect() as conn:
        after = {t: conn.execute(text(f'select count(*) from public."{t}"')).scalar() for t in TABLES}
    assert after == baseline, f"row counts differ from before the run: {after} vs {baseline}"
