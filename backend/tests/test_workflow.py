"""
Prompt 8 (step 8a) - status workflow and mandatory rejection reason (in-memory SQLite).

Approved status model:
    Pending -> Processing -> Ready -> Collected
    Pending -> Rejected
Only staff (role admin) change status. Rejecting needs a reason (5-500 characters),
stored in print_request_status_history.note and shown to the student.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import models  # noqa: F401
from config import get_settings
from models import AuditLog, PrintRequestStatusHistory, User, UserRole

PASSWORD = "CorrectHorse123"
REQ = {"student_name": "S", "document_name": "doc.pdf", "copies": 1, "print_type": "Color"}
STATUSES = ["Pending", "Processing", "Ready", "Collected", "Rejected"]
ALLOWED = {("Pending", "Processing"), ("Pending", "Rejected"),
           ("Processing", "Ready"), ("Ready", "Collected")}
# How to reach each status from Pending using only allowed moves.
PATH_TO = {"Pending": [], "Processing": ["Processing"], "Ready": ["Processing", "Ready"],
           "Collected": ["Processing", "Ready", "Collected"], "Rejected": ["Rejected"]}
REASON = "File is unreadable"


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
def student(client, session):
    return Actor(client, session, "student")


@pytest.fixture
def staff(client, session):
    return Actor(client, session, "staff", admin=True)


def new_request(client, owner):
    res = client.post("/api/print-requests", headers=owner.h, json=REQ)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def set_status(client, staff, rid, status, reason=None):
    body = {"status": status}
    if reason is not None:
        body["reason"] = reason
    return client.patch(f"/api/print-requests/{rid}", headers=staff.h, json=body)


def request_at(client, student, staff, status):
    rid = new_request(client, student)
    for step in PATH_TO[status]:
        res = set_status(client, staff, rid, step, REASON if step == "Rejected" else None)
        assert res.status_code == 200, res.text
    return rid


def history(session, rid):
    session.expire_all()
    return session.exec(select(PrintRequestStatusHistory)
                        .where(PrintRequestStatusHistory.print_request_id == rid)
                        .order_by(PrintRequestStatusHistory.id)).all()


# ------------------------------------------------------------------ transitions

def test_every_status_pair_follows_the_approved_model(client, student, staff):
    """All 20 from->to pairs: the 4 allowed moves succeed, the other 16 return 422."""
    for frm in STATUSES:
        for to in STATUSES:
            if frm == to:
                continue
            rid = request_at(client, student, staff, frm)
            res = set_status(client, staff, rid, to, REASON)
            expected = 200 if (frm, to) in ALLOWED else 422
            assert res.status_code == expected, f"{frm} -> {to}: {res.status_code} {res.text}"
            now = client.get(f"/api/print-requests/{rid}", headers=staff.h).json()["status"]
            assert now == (to if expected == 200 else frm), f"{frm} -> {to} left status {now}"


def test_old_mid_rejections_from_processing_and_ready_are_now_refused(client, student, staff):
    for frm in ("Processing", "Ready"):
        rid = request_at(client, student, staff, frm)
        res = set_status(client, staff, rid, "Rejected", REASON)
        assert res.status_code == 422
        assert "Cannot transition" in res.json()["detail"]


def test_collected_and_rejected_are_final(client, student, staff):
    for final in ("Collected", "Rejected"):
        rid = request_at(client, student, staff, final)
        for to in STATUSES:
            if to != final:
                assert set_status(client, staff, rid, to, REASON).status_code == 422


def test_full_path_records_staff_member_and_timestamps(client, session, student, staff):
    rid = request_at(client, student, staff, "Collected")
    rows = history(session, rid)
    assert [(r.from_status and r.from_status.value, r.to_status.value) for r in rows] == [
        (None, "Pending"), ("Pending", "Processing"), ("Processing", "Ready"), ("Ready", "Collected")]
    assert rows[0].changed_by_id == student.id          # created by the student
    assert all(r.changed_by_id == staff.id for r in rows[1:])  # every status step by staff
    assert all(r.changed_at is not None for r in rows)
    assert [r.changed_at for r in rows] == sorted(r.changed_at for r in rows)
    api = client.get(f"/api/print-requests/{rid}/history", headers=student.h)
    assert api.status_code == 200 and [h["to_status"] for h in api.json()][-1] == "Collected"


# ------------------------------------------------------------- who may change it

def test_students_cannot_change_status_even_on_their_own_request(client, student, staff):
    rid = new_request(client, student)
    for to in ("Processing", "Rejected"):
        res = client.patch(f"/api/print-requests/{rid}", headers=student.h,
                           json={"status": to, "reason": REASON})
        assert res.status_code == 403
    assert client.get(f"/api/print-requests/{rid}", headers=student.h).json()["status"] == "Pending"


def test_group_member_with_every_flag_still_cannot_change_status(client, session, student, staff):
    member = Actor(client, session, "member")
    gid = client.post("/api/groups", headers=student.h, json={"name": "Team"}).json()["id"]
    client.post(f"/api/groups/{gid}/members", headers=student.h, json={
        "email": member.email, "can_create": True, "can_edit": True, "can_assign": True})
    rid = client.post("/api/print-requests", headers=student.h, json={**REQ, "group_id": gid}).json()["id"]
    res = client.patch(f"/api/print-requests/{rid}", headers=member.h, json={"status": "Processing"})
    assert res.status_code == 403


def test_details_locked_once_staff_accepts(client, student, staff):
    rid = new_request(client, student)
    assert client.patch(f"/api/print-requests/{rid}", headers=student.h, json={"copies": 3}).status_code == 200
    assert set_status(client, staff, rid, "Processing").status_code == 200
    res = client.patch(f"/api/print-requests/{rid}", headers=student.h, json={"copies": 4})
    assert res.status_code == 403 and "Pending" in res.json()["detail"]


# ---------------------------------------------------------------- rejection reason

@pytest.mark.parametrize("bad", [None, "", "    ", "abc", "  ab  "])
def test_rejecting_without_a_proper_reason_is_refused(client, session, student, staff, bad):
    rid = new_request(client, student)
    res = set_status(client, staff, rid, "Rejected", bad)
    assert res.status_code == 422
    assert "reason" in str(res.json()["detail"]).lower()
    assert client.get(f"/api/print-requests/{rid}", headers=staff.h).json()["status"] == "Pending"
    assert len(history(session, rid)) == 1  # nothing recorded


def test_reason_longer_than_500_characters_is_refused(client, student, staff):
    rid = new_request(client, student)
    assert set_status(client, staff, rid, "Rejected", "x" * 501).status_code == 422


def test_rejection_reason_is_stored_audited_and_shown_to_the_student(client, session, student, staff):
    rid = new_request(client, student)
    res = set_status(client, staff, rid, "Rejected", "   " + REASON + "  ")
    assert res.status_code == 200
    assert res.json()["status"] == "Rejected" and res.json()["rejection_reason"] == REASON  # trimmed
    # The student sees why, both on the single request and in their list.
    mine = client.get(f"/api/print-requests/{rid}", headers=student.h).json()
    assert mine["rejection_reason"] == REASON
    listed = {r["id"]: r for r in client.get("/api/print-requests", headers=student.h).json()}
    assert listed[rid]["rejection_reason"] == REASON
    last = history(session, rid)[-1]
    assert (last.to_status.value, last.note, last.changed_by_id) == ("Rejected", REASON, staff.id)
    log = session.exec(select(AuditLog).where(AuditLog.action == "request.status_change",
                                              AuditLog.target_id == str(rid))).one()
    assert log.actor_id == staff.id and log.details == {"from": "Pending", "to": "Rejected", "reason": REASON}


def test_optional_note_on_other_status_changes(client, session, student, staff):
    rid = new_request(client, student)
    res = set_status(client, staff, rid, "Processing", "Printing on the colour printer")
    assert res.status_code == 200 and res.json()["rejection_reason"] is None
    assert history(session, rid)[-1].note == "Printing on the colour printer"
    assert set_status(client, staff, rid, "Ready").status_code == 200  # note stays optional
    assert history(session, rid)[-1].note is None


def test_reason_without_a_status_change_is_refused(client, student, staff):
    rid = new_request(client, student)
    res = client.patch(f"/api/print-requests/{rid}", headers=staff.h, json={"reason": REASON})
    assert res.status_code == 422
    res = set_status(client, staff, rid, "Pending", REASON)  # same status = no change
    assert res.status_code == 422


def test_rejection_reason_is_empty_for_requests_that_are_not_rejected(client, student, staff):
    rid = new_request(client, student)
    assert client.get(f"/api/print-requests/{rid}", headers=student.h).json()["rejection_reason"] is None
