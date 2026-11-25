"""
OPT-IN integration tests: RBAC, ownership, groups and admin safety against the
real printpoint-dev Supabase PostgreSQL database (never Production).

Skipped unless RUN_PG_INTEGRATION=1. Same safety rules as
test_auth_postgres_integration.py: dev-project guard, unique test emails
(pprbac+<run-id>-<name>@uni.edu), a TEST-ONLY admin (a test account promoted in
the database), and a final cleanup that removes only this run's rows and checks
every table is back to its starting row count.
"""

import os
import re
import uuid
from itertools import count
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import false, or_, text
from sqlmodel import Session, select

from config import get_settings
from database import build_engine, normalize_database_url
from models import (AuditLog, Group, GroupMember, LoginAttempt, PrintRequest,
                    PrintRequestStatusHistory, RefreshSession, User, UserRole)

DEV_PROJECT_REF = "vxgubnunysotatnbfpip"
pytestmark = pytest.mark.skipif(os.getenv("RUN_PG_INTEGRATION") != "1",
                                reason="PostgreSQL integration tests are opt-in (set RUN_PG_INTEGRATION=1)")

RUN_ID = uuid.uuid4().hex[:10]
EMAIL_LIKE = f"pprbac+{RUN_ID}-%@uni.edu"
PASSWORD = "IntegrationPass123"
REQ = {"student_name": "RBAC test", "document_name": "rbac.pdf", "copies": 1, "print_type": "Color"}
TABLES = ["users", "refresh_sessions", "login_attempts", "audit_logs", "groups", "group_members",
          "print_requests", "print_request_status_history"]
_ip = count(1)


def email(name):
    return f"pprbac+{RUN_ID}-{name}@uni.edu"


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
    cleanup(engine)


@pytest.fixture(autouse=True)
def own_ip(client):
    client.headers["X-Forwarded-For"] = f"192.0.2.{next(_ip)}"


class Actor:
    def __init__(self, client, engine, name, admin=False):
        res = client.post("/api/auth/signup", json={"email": email(name), "full_name": f"RBAC {name}",
                                                     "password": PASSWORD})
        assert res.status_code == 201, res.text
        self.id, self.email = res.json()["user"]["id"], email(name)
        self.h = {"Authorization": f"Bearer {res.json()['access_token']}"}
        if admin:  # TEST-ONLY admin: promote this test account directly
            with Session(engine) as s:
                u = s.get(User, self.id)
                u.role = UserRole.admin
                s.add(u)
                s.commit()


@pytest.fixture(scope="module")
def people(client, engine):
    return {n: Actor(client, engine, n, admin=n.startswith("admin")) for n in ("alice", "bob", "carol", "admin1", "admin2")}


def new_request(client, actor, group_id=None):
    res = client.post("/api/print-requests", headers=actor.h, json={**REQ, "group_id": group_id})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def cleanup(engine) -> dict:
    deleted = {}
    with Session(engine) as s:
        ids = list(s.exec(select(User.id).where(User.email.like(EMAIL_LIKE))).all())
        none = false()
        gids = list(s.exec(select(Group.id).where(Group.owner_id.in_(ids)))) if ids else []
        prids = list(s.exec(select(PrintRequest.id).where(PrintRequest.owner_id.in_(ids)))) if ids else []
        steps = [
            (AuditLog, or_(AuditLog.actor_id.in_(ids) if ids else none,
                           AuditLog.details["email"].as_string().like(EMAIL_LIKE))),
            (PrintRequestStatusHistory, PrintRequestStatusHistory.print_request_id.in_(prids) if prids else none),
            (PrintRequest, PrintRequest.id.in_(prids) if prids else none),
            (GroupMember, or_(GroupMember.group_id.in_(gids) if gids else none,
                              GroupMember.user_id.in_(ids) if ids else none)),
            (Group, Group.id.in_(gids) if gids else none),
            (LoginAttempt, or_(LoginAttempt.email_attempted.like(EMAIL_LIKE),
                               LoginAttempt.user_id.in_(ids) if ids else none)),
            (RefreshSession, RefreshSession.user_id.in_(ids) if ids else none),
            (User, User.id.in_(ids) if ids else none),
        ]
        for model, cond in steps:
            rows = s.exec(select(model).where(cond)).all()
            for r in rows:
                s.delete(r)
            s.flush()
            deleted[model.__tablename__] = len(rows)
        s.commit()
    return deleted


# --------------------------------------------------------------------- tests

def test_01_target_is_dev_at_revision_0003(engine):
    with engine.connect() as conn:
        assert conn.execute(text("select version_num from alembic_version")).scalar() == "0003_owner_required"
        assert conn.execute(text("select is_nullable from information_schema.columns where "
                                 "table_name='print_requests' and column_name='owner_id'")).scalar() == "NO"


def test_02_students_only_see_their_own_requests(client, people):
    alice, bob, staff = people["alice"], people["bob"], people["admin1"]
    a = new_request(client, alice)
    b = new_request(client, bob)
    for method, path in (("get", f"/api/print-requests/{a}"), ("delete", f"/api/print-requests/{a}")):
        assert getattr(client, method)(path, headers=bob.h).status_code == 404
    assert client.patch(f"/api/print-requests/{a}", headers=bob.h, json={"copies": 5}).status_code == 404
    mine = {r["id"] for r in client.get("/api/print-requests", headers=bob.h).json()}
    assert b in mine and a not in mine
    staff_ids = {r["id"] for r in client.get("/api/print-requests?limit=500", headers=staff.h).json()}
    assert {a, b} <= staff_ids


def test_03_only_staff_change_status_and_history_is_recorded(client, engine, people):
    alice, staff = people["alice"], people["admin1"]
    rid = new_request(client, alice)
    assert client.patch(f"/api/print-requests/{rid}", headers=alice.h, json={"status": "Processing"}).status_code == 403
    assert client.patch(f"/api/print-requests/{rid}", headers=staff.h, json={"status": "Processing"}).status_code == 200
    assert client.patch(f"/api/print-requests/{rid}", headers=alice.h, json={"copies": 2}).status_code == 403  # not Pending
    with Session(engine) as s:
        rows = s.exec(select(PrintRequestStatusHistory).where(
            PrintRequestStatusHistory.print_request_id == rid).order_by(PrintRequestStatusHistory.id)).all()
        assert [(r.from_status, r.to_status.value) for r in rows] == [(None, "Pending"), (rows[1].from_status, "Processing")]
        assert rows[1].changed_by_id == staff.id and rows[1].changed_at.tzinfo is not None


def test_04_group_flags_on_postgres(client, people):
    alice, bob, carol = people["alice"], people["bob"], people["carol"]
    gid = client.post("/api/groups", headers=alice.h, json={"name": f"RBAC group {RUN_ID}"}).json()["id"]
    assert client.post(f"/api/groups/{gid}/members", headers=alice.h, json={"email": bob.email}).status_code == 201
    rid = new_request(client, alice, gid)
    assert client.get(f"/api/print-requests/{rid}", headers=bob.h).status_code == 200
    assert client.post("/api/print-requests", headers=bob.h, json={**REQ, "group_id": gid}).status_code == 403
    assert client.patch(f"/api/print-requests/{rid}", headers=bob.h, json={"copies": 2}).status_code == 403
    assert client.get(f"/api/groups/{gid}", headers=carol.h).status_code == 404
    client.patch(f"/api/groups/{gid}/members/{bob.id}", headers=alice.h,
                 json={"can_create": True, "can_edit": True, "can_assign": True})
    assert client.post("/api/print-requests", headers=bob.h, json={**REQ, "group_id": gid}).status_code == 201
    assert client.patch(f"/api/print-requests/{rid}", headers=bob.h, json={"copies": 2}).status_code == 200
    assert client.patch(f"/api/print-requests/{rid}/assignee", headers=bob.h,
                        json={"assignee_id": bob.id}).status_code == 200
    # Only the group owner manages the group; flags do not grant it.
    assert client.patch(f"/api/groups/{gid}", headers=bob.h, json={"name": "x"}).status_code == 403
    assert client.delete(f"/api/groups/{gid}", headers=bob.h).status_code == 403
    assert client.delete(f"/api/print-requests/{rid}", headers=bob.h).status_code == 403  # not request/group owner
    assert client.delete(f"/api/groups/{gid}", headers=alice.h).status_code == 204
    res = client.get(f"/api/print-requests/{rid}", headers=alice.h)
    assert res.status_code == 200 and res.json()["group_id"] is None  # request kept


def test_05_admin_safety_and_ban_on_postgres(client, engine, people):
    a1, a2, carol = people["admin1"], people["admin2"], people["carol"]
    assert client.get("/api/admin/users", headers=carol.h).status_code == 403
    assert client.post(f"/api/admin/users/{a2.id}/ban", headers=a1.h, json={"reason": "test"}).status_code == 403
    assert client.patch(f"/api/admin/users/{a1.id}/role", headers=a1.h, json={"role": "user"}).status_code == 403
    assert client.post(f"/api/admin/users/{carol.id}/ban", headers=a1.h, json={"reason": "RBAC test ban"}).status_code == 200
    assert client.get("/api/print-requests", headers=carol.h).status_code == 403
    with Session(engine) as s:
        log = s.exec(select(AuditLog).where(AuditLog.action == "user.ban",
                                            AuditLog.target_id == str(carol.id))).one()
        assert log.actor_id == a1.id and log.details["reason"] == "RBAC test ban"


def test_06_moderation_is_audited(client, engine, people):
    alice, staff = people["alice"], people["admin1"]
    rid = new_request(client, alice)
    assert client.delete(f"/api/print-requests/{rid}", headers=staff.h).status_code == 403
    assert client.delete(f"/api/admin/print-requests/{rid}", headers=staff.h).status_code == 204
    with Session(engine) as s:
        assert s.get(PrintRequest, rid) is None
        assert s.exec(select(AuditLog).where(AuditLog.action == "moderation.request_delete",
                                             AuditLog.target_id == str(rid))).one().actor_id == staff.id


def test_07_cleanup_removes_only_this_runs_data(engine, baseline):
    deleted = cleanup(engine)
    print("\nrows deleted per table:", deleted)
    assert deleted["users"] == 5
    with engine.connect() as conn:
        after = {t: conn.execute(text(f'select count(*) from public."{t}"')).scalar() for t in TABLES}
    assert after == baseline, f"row counts differ from before the run: {after} vs {baseline}"
