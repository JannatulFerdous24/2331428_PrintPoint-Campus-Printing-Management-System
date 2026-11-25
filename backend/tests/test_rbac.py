"""
RBAC, ownership, group-permission and admin-safety tests (in-memory SQLite).

Roles: `user` (Student) and `admin` (Print-Shop Staff / Admin).
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import models  # noqa: F401
from config import get_settings
from models import AuditLog, PrintRequest, PrintRequestStatusHistory, User, UserRole

PASSWORD = "CorrectHorse123"
REQ = {"student_name": "S", "document_name": "doc.pdf", "copies": 1, "print_type": "Color"}


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


class Actor:
    """A logged-in test user: .h are the auth headers, .id the user id."""

    def __init__(self, client, session, name, admin=False):
        res = client.post("/api/auth/signup", json={
            "email": f"{name}@uni.edu", "full_name": name.title(), "password": PASSWORD})
        assert res.status_code == 201, res.text
        self.id = res.json()["user"]["id"]
        self.email = f"{name}@uni.edu"
        self.h = {"Authorization": f"Bearer {res.json()['access_token']}"}
        if admin:
            user = session.get(User, self.id)
            user.role = UserRole.admin
            session.add(user)
            session.commit()


@pytest.fixture
def people(client, session):
    return {n: Actor(client, session, n, admin=n.startswith("admin"))
            for n in ("alice", "bob", "carol", "admin1", "admin2")}


def create_request(client, actor, group_id=None):
    res = client.post("/api/print-requests", headers=actor.h, json={**REQ, "group_id": group_id})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def make_group(client, owner, members=()):
    """members: [(actor, {"can_create": .., "can_edit": .., "can_assign": ..}), ...]"""
    gid = client.post("/api/groups", headers=owner.h, json={"name": "CSE309 Team"}).json()["id"]
    for actor, flags in members:
        res = client.post(f"/api/groups/{gid}/members", headers=owner.h, json={"email": actor.email, **flags})
        assert res.status_code == 201, res.text
    return gid


def actions(session):
    return [a.action for a in session.exec(select(AuditLog)).all()]


# ------------------------------------------------- 1. ownership (required test 1)

def test_student_cannot_access_another_students_request(client, people):
    alice, bob = people["alice"], people["bob"]
    rid = create_request(client, alice)
    # Bob guesses Alice's request id: every route answers 404 ("does not exist").
    assert client.get(f"/api/print-requests/{rid}", headers=bob.h).status_code == 404
    assert client.get(f"/api/print-requests/{rid}/history", headers=bob.h).status_code == 404
    assert client.patch(f"/api/print-requests/{rid}", headers=bob.h, json={"copies": 9}).status_code == 404
    assert client.delete(f"/api/print-requests/{rid}", headers=bob.h).status_code == 404
    assert client.get(f"/api/print-requests/{rid}", headers=alice.h).status_code == 200


def test_list_shows_only_own_requests_but_staff_see_all(client, people):
    a = create_request(client, people["alice"])
    b = create_request(client, people["bob"])
    assert [r["id"] for r in client.get("/api/print-requests", headers=people["alice"].h).json()] == [a]
    staff = {r["id"] for r in client.get("/api/print-requests", headers=people["admin1"].h).json()}
    assert staff == {a, b}


# ---------------------------------------- 2. admin endpoints (required test 2)

@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/admin/users", None),
    ("post", "/api/admin/users/1/ban", {"reason": "spam"}),
    ("post", "/api/admin/users/1/unban", None),
    ("patch", "/api/admin/users/1/role", {"role": "admin"}),
    ("delete", "/api/admin/print-requests/1", None),
    ("delete", "/api/admin/groups/1", None),
])
def test_normal_user_cannot_access_admin_endpoints(client, people, method, path, body):
    kwargs = {"headers": people["alice"].h}
    if body is not None:
        kwargs["json"] = body
    assert getattr(client, method)(path, **kwargs).status_code == 403


# ------------------------------------------------------------ status changes

def test_only_staff_can_change_status_and_it_is_recorded(client, session, people):
    alice, staff = people["alice"], people["admin1"]
    rid = create_request(client, alice)
    res = client.patch(f"/api/print-requests/{rid}", headers=alice.h, json={"status": "Processing"})
    assert res.status_code == 403

    res = client.patch(f"/api/print-requests/{rid}", headers=staff.h, json={"status": "Processing"})
    assert res.status_code == 200 and res.json()["status"] == "Processing"

    history = client.get(f"/api/print-requests/{rid}/history", headers=alice.h).json()
    assert [(h["from_status"], h["to_status"]) for h in history] == [(None, "Pending"), ("Pending", "Processing")]
    assert history[1]["changed_by_id"] == staff.id and history[1]["changed_at"]
    assert "request.status_change" in actions(session)


def test_requests_can_only_be_edited_while_pending(client, people):
    alice, staff = people["alice"], people["admin1"]
    rid = create_request(client, alice)
    assert client.patch(f"/api/print-requests/{rid}", headers=alice.h, json={"copies": 3}).status_code == 200
    client.patch(f"/api/print-requests/{rid}", headers=staff.h, json={"status": "Processing"})
    res = client.patch(f"/api/print-requests/{rid}", headers=alice.h, json={"copies": 4})
    assert res.status_code == 403 and "Pending" in res.json()["detail"]


# --------------------------------- 3. group member permissions (required test 3)

def test_group_member_cannot_act_without_permission(client, people):
    alice, bob = people["alice"], people["bob"]
    gid = make_group(client, alice, [(bob, {})])  # bob: member with NO flags
    rid = create_request(client, alice, gid)

    assert client.get(f"/api/print-requests/{rid}", headers=bob.h).status_code == 200  # can view
    assert client.post("/api/print-requests", headers=bob.h, json={**REQ, "group_id": gid}).status_code == 403
    assert client.patch(f"/api/print-requests/{rid}", headers=bob.h, json={"copies": 2}).status_code == 403
    assert client.patch(f"/api/print-requests/{rid}/assignee", headers=bob.h,
                        json={"assignee_id": bob.id}).status_code == 403

    # Owner grants the flags one by one -> each action becomes allowed.
    for flag in ("can_create", "can_edit", "can_assign"):
        client.patch(f"/api/groups/{gid}/members/{bob.id}", headers=alice.h, json={flag: True})
        if flag == "can_create":
            assert client.post("/api/print-requests", headers=bob.h,
                               json={**REQ, "group_id": gid}).status_code == 201
        if flag == "can_edit":
            # can_edit was granted, but PATCH replaced the flags with only can_edit=True
            assert client.patch(f"/api/print-requests/{rid}", headers=bob.h, json={"copies": 2}).status_code == 200
        if flag == "can_assign":
            assert client.patch(f"/api/print-requests/{rid}/assignee", headers=bob.h,
                                json={"assignee_id": bob.id}).status_code == 200


def test_non_members_get_404_for_group_and_its_requests(client, people):
    alice, carol = people["alice"], people["carol"]
    gid = make_group(client, alice)
    rid = create_request(client, alice, gid)
    assert client.get(f"/api/groups/{gid}", headers=carol.h).status_code == 404
    assert client.get(f"/api/print-requests/{rid}", headers=carol.h).status_code == 404
    assert client.get(f"/api/print-requests?group_id={gid}", headers=carol.h).status_code == 404


def test_assignee_must_be_a_group_member(client, people):
    alice, bob, carol = people["alice"], people["bob"], people["carol"]
    gid = make_group(client, alice, [(bob, {})])
    rid = create_request(client, alice, gid)
    assert client.patch(f"/api/print-requests/{rid}/assignee", headers=alice.h,
                        json={"assignee_id": carol.id}).status_code == 400
    res = client.patch(f"/api/print-requests/{rid}/assignee", headers=alice.h, json={"assignee_id": bob.id})
    assert res.status_code == 200 and res.json()["assignee_id"] == bob.id


# ------------------------- 4. only the owner manages the group (required test 4)

def test_non_owner_cannot_rename_delete_or_manage_group(client, people):
    alice, bob, carol = people["alice"], people["bob"], people["carol"]
    gid = make_group(client, alice, [(bob, {"can_create": True, "can_edit": True, "can_assign": True})])
    assert client.patch(f"/api/groups/{gid}", headers=bob.h, json={"name": "Hijacked"}).status_code == 403
    assert client.delete(f"/api/groups/{gid}", headers=bob.h).status_code == 403
    assert client.post(f"/api/groups/{gid}/members", headers=bob.h, json={"email": carol.email}).status_code == 403
    assert client.patch(f"/api/groups/{gid}/members/{bob.id}", headers=bob.h,
                        json={"can_create": False}).status_code == 403
    assert client.delete(f"/api/groups/{gid}/members/{bob.id}", headers=bob.h).status_code == 403
    # The owner can.
    assert client.patch(f"/api/groups/{gid}", headers=alice.h, json={"name": "Renamed"}).json()["name"] == "Renamed"


def test_admin_has_no_group_owner_powers(client, people):
    alice, staff = people["alice"], people["admin1"]
    gid = make_group(client, alice)
    assert client.get(f"/api/groups/{gid}", headers=staff.h).status_code == 200       # oversight
    assert client.patch(f"/api/groups/{gid}", headers=staff.h, json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/groups/{gid}", headers=staff.h).status_code == 404


def test_only_request_owner_or_group_owner_can_delete_group_request(client, people):
    alice, bob, carol = people["alice"], people["bob"], people["carol"]
    all_flags = {"can_create": True, "can_edit": True, "can_assign": True}
    gid = make_group(client, alice, [(bob, all_flags), (carol, all_flags)])
    r1 = create_request(client, bob, gid)
    r2 = create_request(client, bob, gid)
    assert client.delete(f"/api/print-requests/{r1}", headers=carol.h).status_code == 403  # flags don't matter
    assert client.delete(f"/api/print-requests/{r1}", headers=bob.h).status_code == 204    # request owner
    assert client.delete(f"/api/print-requests/{r2}", headers=alice.h).status_code == 204  # group owner


def test_deleting_a_group_keeps_its_requests(client, session, people):
    alice = people["alice"]
    gid = make_group(client, alice)
    rid = create_request(client, alice, gid)
    assert client.delete(f"/api/groups/{gid}", headers=alice.h).status_code == 204
    res = client.get(f"/api/print-requests/{rid}", headers=alice.h)
    assert res.status_code == 200 and res.json()["group_id"] is None


# ------------------------------------- 5. admin safety rules (required test 5)

def test_admin_cannot_ban_another_admin_or_themselves(client, people):
    a1, a2 = people["admin1"], people["admin2"]
    assert client.post(f"/api/admin/users/{a2.id}/ban", headers=a1.h, json={"reason": "test"}).status_code == 403
    assert client.post(f"/api/admin/users/{a1.id}/ban", headers=a1.h, json={"reason": "test"}).status_code == 403


def test_admin_cannot_change_own_role_and_role_changes_are_audited(client, session, people):
    a1, alice = people["admin1"], people["alice"]
    assert client.patch(f"/api/admin/users/{a1.id}/role", headers=a1.h, json={"role": "user"}).status_code == 403
    assert client.get("/api/admin/users", headers=alice.h).status_code == 403
    res = client.patch(f"/api/admin/users/{alice.id}/role", headers=a1.h, json={"role": "admin"})
    assert res.status_code == 200 and res.json()["role"] == "admin"
    # Takes effect on the next request (role read from the DB, not from the old JWT).
    assert client.get("/api/admin/users", headers=alice.h).status_code == 200
    log = session.exec(select(AuditLog).where(AuditLog.action == "user.role_change")).one()
    assert log.actor_id == a1.id and log.details == {"from": "user", "to": "admin"}


# ------------------------------------------ 6. banned users (required test 6)

def test_banned_user_is_rejected_and_ban_is_audited(client, session, people):
    a1, bob = people["admin1"], people["bob"]
    assert client.get("/api/print-requests", headers=bob.h).status_code == 200
    res = client.post(f"/api/admin/users/{bob.id}/ban", headers=a1.h, json={"reason": "Abusive uploads"})
    assert res.status_code == 200 and res.json()["is_banned"] is True
    assert client.get("/api/print-requests", headers=bob.h).status_code == 403  # very next request
    log = session.exec(select(AuditLog).where(AuditLog.action == "user.ban")).one()
    assert log.actor_id == a1.id and log.details["reason"] == "Abusive uploads"
    assert client.post(f"/api/admin/users/{bob.id}/unban", headers=a1.h).status_code == 200
    assert "user.unban" in actions(session)


# ---------------------------------------------------------------- moderation

def test_admin_moderation_deletes_are_audited(client, session, people):
    alice, staff = people["alice"], people["admin1"]
    gid = make_group(client, alice)
    rid = create_request(client, alice)
    # Normal path: staff are not the owner -> 403; moderation path -> allowed + audited.
    assert client.delete(f"/api/print-requests/{rid}", headers=staff.h).status_code == 403
    assert client.delete(f"/api/admin/print-requests/{rid}", headers=staff.h).status_code == 204
    assert client.delete(f"/api/admin/groups/{gid}", headers=staff.h).status_code == 204
    assert {"moderation.request_delete", "moderation.group_delete"} <= set(actions(session))
    assert session.get(PrintRequest, rid) is None
    assert not session.exec(select(PrintRequestStatusHistory).where(
        PrintRequestStatusHistory.print_request_id == rid)).all()


def test_permissions_field_tells_the_ui_what_is_allowed(client, people):
    alice, staff = people["alice"], people["admin1"]
    rid = create_request(client, alice)
    mine = client.get(f"/api/print-requests/{rid}", headers=alice.h).json()["permissions"]
    assert mine == {"view": True, "edit": True, "delete": True, "change_status": False, "assign": False}
    theirs = client.get(f"/api/print-requests/{rid}", headers=staff.h).json()["permissions"]
    assert theirs["change_status"] is True and theirs["edit"] is False and theirs["delete"] is False
