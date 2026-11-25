"""Prompt 8c (staff queue search/filters) and Prompt 9 (admin dashboard) - in-memory SQLite."""

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import models  # noqa: F401
from config import get_settings
from models import AuditLog, PrintRequest, User, UserRole

PASSWORD = "CorrectHorse123"
REQ = {"student_name": "Alice", "document_name": "Thesis", "copies": 1, "print_type": "Color"}


@pytest.fixture(name="session")
def session_fixture():
    get_settings.cache_clear()
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
    def __init__(self, client, session, name, admin=False):
        res = client.post("/api/auth/signup", json={"email": f"{name}@uni.edu", "full_name": name.title(),
                                                     "password": PASSWORD})
        assert res.status_code == 201, res.text
        self.id, self.email = res.json()["user"]["id"], f"{name}@uni.edu"
        self.h = {"Authorization": f"Bearer {res.json()['access_token']}"}
        if admin:
            u = session.get(User, self.id)
            u.role = UserRole.admin
            session.add(u)
            session.commit()


@pytest.fixture
def people(client, session):
    return {n: Actor(client, session, n, admin=n.startswith("admin")) for n in ("alice", "bob", "admin1", "admin2")}


def req(client, actor, **kw):
    res = client.post("/api/print-requests", headers=actor.h, json={**REQ, **kw})
    assert res.status_code == 201, res.text
    return res.json()["id"]


ADMIN_GETS = ["/api/admin/stats", "/api/admin/users", "/api/admin/users/1", "/api/admin/groups",
              "/api/admin/audit-logs", "/api/admin/security/failed-logins", "/api/admin/export/users.csv",
              "/api/admin/export/print-requests.csv", "/api/admin/export/audit-logs.csv"]
ADMIN_POSTS = [("/api/admin/users/bulk-ban", {"user_ids": [1], "reason": "abc"}),
               ("/api/admin/users/bulk-unban", {"user_ids": [1]}),
               ("/api/admin/users/1/revoke-sessions", None),
               ("/api/admin/print-requests/bulk-delete", {"ids": [1]}),
               ("/api/admin/groups/bulk-delete", {"ids": [1]})]


def test_every_admin_endpoint_rejects_students_and_anonymous(client, people):
    for path in ADMIN_GETS:
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers=people["alice"].h).status_code == 403, path
    for path, body in ADMIN_POSTS:
        assert client.post(path, json=body).status_code == 401, path
        assert client.post(path, headers=people["alice"].h, json=body).status_code == 403, path


# ------------------------------------------------------------------ staff queue

def test_staff_queue_search_filters_sort_and_total(client, people):
    alice, bob, staff = people["alice"], people["bob"], people["admin1"]
    a1 = req(client, alice, document_name="Physics lab", print_type="Black & White")
    a2 = req(client, alice, document_name="Thesis final")
    b1 = req(client, bob, student_name="Bob", document_name="Poster")
    client.patch(f"/api/print-requests/{a2}", headers=staff.h, json={"status": "Processing"})

    def ids(qs, who=staff):
        res = client.get(f"/api/print-requests?{qs}", headers=who.h)
        assert res.status_code == 200, res.text
        return [r["id"] for r in res.json()], int(res.headers["X-Total-Count"])

    assert ids("q=physics") == ([a1], 1)
    assert ids(f"q={b1}") == ([b1], 1)                 # by request id
    assert ids(f"q=%23{b1}") == ([b1], 1)              # "#12" style
    assert ids("q=bob@uni") == ([b1], 1)               # by owner email
    assert ids("status=Processing") == ([a2], 1)
    assert ids("print_type=Black%20%26%20White") == ([a1], 1)
    assert ids("has_document=false")[1] == 3 and ids("has_document=true")[1] == 0
    assert ids("sort=oldest")[0] == [a1, a2, b1]
    assert ids("sort=newest&limit=1") == ([b1], 3)     # page of 1, total 3
    assert ids("created_from=2000-01-01T00:00:00&created_to=2000-01-02T00:00:00") == ([], 0)
    # Students searching only see their own requests
    assert ids("q=poster", who=alice) == ([], 0)
    assert ids("q=thesis", who=alice) == ([a2], 1)


# ------------------------------------------------------------------ dashboard

def test_stats_are_real_counts(client, session, people):
    alice, staff = people["alice"], people["admin1"]
    req(client, alice)
    client.post("/api/groups", headers=alice.h, json={"name": "G"})
    client.post(f"/api/admin/users/{people['bob'].id}/ban", headers=staff.h, json={"reason": "spam"})
    client.post("/api/auth/login", json={"email": alice.email, "password": "WrongPass999"})
    s = client.get("/api/admin/stats", headers=staff.h).json()
    assert s["total_users"] == 4 and s["banned_users"] == 1 and s["admins"] == 2
    assert s["total_requests"] == 1 and s["requests_by_status"]["Pending"] == 1
    assert s["total_groups"] == 1 and s["new_users_7d"] == 4 and s["new_requests_7d"] == 1
    assert s["failed_logins_24h"] == 1


def test_user_list_filters_and_pagination(client, people):
    staff = people["admin1"]
    client.post(f"/api/admin/users/{people['bob'].id}/ban", headers=staff.h, json={"reason": "spam"})
    res = client.get("/api/admin/users?role=admin", headers=staff.h)
    assert {u["email"] for u in res.json()} == {"admin1@uni.edu", "admin2@uni.edu"} and res.headers["X-Total-Count"] == "2"
    assert [u["email"] for u in client.get("/api/admin/users?banned=true", headers=staff.h).json()] == ["bob@uni.edu"]
    page = client.get("/api/admin/users?limit=1&skip=1", headers=staff.h)
    assert len(page.json()) == 1 and page.headers["X-Total-Count"] == "4"


def test_user_detail(client, people):
    alice, staff = people["alice"], people["admin1"]
    rid = req(client, alice)
    gid = client.post("/api/groups", headers=alice.h, json={"name": "Club"}).json()["id"]
    d = client.get(f"/api/admin/users/{alice.id}", headers=staff.h)
    assert d.status_code == 200
    d = d.json()
    assert d["user"]["email"] == alice.email and [r["id"] for r in d["requests"]] == [rid]
    assert d["groups"] == [{"id": gid, "name": "Club", "role": "owner"}]
    assert len(d["sessions"]) == 1 and "token_hash" not in str(d)
    assert {"auth.signup", "request.create"} <= {a["action"] for a in d["activity"]}
    assert client.get("/api/admin/users/9999", headers=staff.h).status_code == 404


def test_revoke_sessions_logs_user_out(client, people):
    alice, staff = people["alice"], people["admin1"]
    res = client.post(f"/api/admin/users/{alice.id}/revoke-sessions", headers=staff.h)
    assert res.status_code == 200 and res.json()["revoked"] == 1
    assert client.get("/api/print-requests", headers=alice.h).status_code == 401
    assert client.post(f"/api/admin/users/{staff.id}/revoke-sessions", headers=staff.h).status_code == 403


def test_bulk_ban_and_unban_respect_safety_rules(client, session, people):
    alice, bob, a1, a2 = people["alice"], people["bob"], people["admin1"], people["admin2"]
    ids = [alice.id, bob.id, a1.id, a2.id, 999]
    assert client.post("/api/admin/users/bulk-ban", headers=a1.h, json={"user_ids": ids}).status_code == 422
    res = client.post("/api/admin/users/bulk-ban", headers=a1.h, json={"user_ids": ids, "reason": "Exam cheating"})
    assert res.status_code == 200
    assert res.json()["done"] == [alice.id, bob.id]
    assert {s["id"] for s in res.json()["skipped"]} == {a1.id, a2.id, 999}   # self, other admin, missing
    assert client.get("/api/print-requests", headers=alice.h).status_code in (401, 403)
    res = client.post("/api/admin/users/bulk-unban", headers=a1.h, json={"user_ids": [alice.id, bob.id, a2.id]})
    assert res.json()["done"] == [alice.id, bob.id] and res.json()["skipped"][0]["id"] == a2.id
    bans = session.exec(select(AuditLog).where(AuditLog.action == "user.ban")).all()
    assert len(bans) == 2 and all(b.details["reason"] == "Exam cheating" for b in bans)


def test_moderation_lists_and_bulk_delete(client, session, people):
    alice, staff = people["alice"], people["admin1"]
    r1, r2 = req(client, alice), req(client, alice)
    g = client.post("/api/groups", headers=alice.h, json={"name": "Robotics"}).json()["id"]
    groups = client.get("/api/admin/groups?q=robot", headers=staff.h)
    assert [x["name"] for x in groups.json()] == ["Robotics"] and groups.json()[0]["owner_email"] == alice.email
    res = client.post("/api/admin/print-requests/bulk-delete", headers=staff.h, json={"ids": [r1, r2, 999]})
    assert res.json()["done"] == [r1, r2] and res.json()["skipped"] == [{"id": 999, "reason": "Not found"}]
    assert session.exec(select(PrintRequest)).all() == []
    assert client.post("/api/admin/groups/bulk-delete", headers=staff.h, json={"ids": [g]}).json()["done"] == [g]
    actions = [a.action for a in session.exec(select(AuditLog)).all()]
    assert actions.count("moderation.request_delete") == 2 and "moderation.group_delete" in actions


def test_audit_log_filters_and_security_view(client, people):
    alice, staff = people["alice"], people["admin1"]
    for ip in ("203.0.113.5", "203.0.113.5", "198.51.100.7"):
        client.post("/api/auth/login", headers={"X-Forwarded-For": ip},
                    json={"email": alice.email, "password": "WrongPass999"})
    client.post("/api/auth/login", headers={"X-Forwarded-For": "203.0.113.5"},
                json={"email": "ghost@uni.edu", "password": "WrongPass999"})
    logs = client.get("/api/admin/audit-logs?action=auth.login_failed", headers=staff.h)
    assert logs.status_code == 200 and logs.headers["X-Total-Count"] == "4"
    assert all(l["action"] == "auth.login_failed" and l["ip_address"] for l in logs.json())
    assert client.get("/api/admin/audit-logs?action=auth.&ip=198.51.100.7", headers=staff.h).headers["X-Total-Count"] == "1"
    assert all(l["actor_email"] == staff.email for l in
               client.get("/api/admin/audit-logs?actor=admin1", headers=staff.h).json())
    sec = client.get("/api/admin/security/failed-logins?hours=24", headers=staff.h).json()
    assert sec["total_failed"] == 4
    by_ip = {r["ip_address"]: r for r in sec["by_ip"]}
    assert by_ip["203.0.113.5"]["failures"] == 3 and by_ip["203.0.113.5"]["accounts_tried"] == 2
    by_acc = {r["email"]: r for r in sec["by_account"]}
    assert by_acc[alice.email]["failures"] == 3 and by_acc[alice.email]["known_account"]
    assert by_acc["ghost@uni.edu"]["known_account"] is False


def read_csv(res):
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    return list(csv.reader(io.StringIO(res.content.decode("utf-8-sig"))))


def test_csv_exports_respect_filters_and_are_audited(client, session, people):
    alice, bob, staff = people["alice"], people["bob"], people["admin1"]
    req(client, alice, document_name="=HYPERLINK(evil)")
    req(client, bob, student_name="Bob", document_name="Poster")
    users = read_csv(client.get("/api/admin/export/users.csv?role=admin", headers=staff.h))
    assert users[0][:2] == ["id", "email"] and {r[1] for r in users[1:]} == {"admin1@uni.edu", "admin2@uni.edu"}
    reqs = read_csv(client.get("/api/admin/export/print-requests.csv?q=alice@uni", headers=staff.h))
    assert len(reqs) == 2 and reqs[1][3] == "'=HYPERLINK(evil)"   # formula neutralised
    logs = read_csv(client.get("/api/admin/export/audit-logs.csv?action=request.create", headers=staff.h))
    assert len(logs) == 3 and all(r[2] == "request.create" for r in logs[1:])
    exports = session.exec(select(AuditLog).where(AuditLog.action == "data.export")).all()
    assert [e.target_type for e in exports] == ["users", "print-requests", "audit-logs"]
    assert exports[1].details == {"rows": 1, "filters": {"q": "alice@uni"}}
