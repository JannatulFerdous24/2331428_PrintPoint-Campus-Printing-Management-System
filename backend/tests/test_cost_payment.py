"""
Printing cost and payment tracking (in-memory SQLite).

    total_cost = pages x copies x rate     B&W Tk 2 / page, Color Tk 10 / page
The server always calculates the cost. Only staff (PAYMENT_UPDATE) mark a request
Paid; a paid request can no longer be edited; every change is in the audit log.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import models  # noqa: F401
from config import get_settings
from models import AuditLog, PrintType, User, UserRole
from pricing import calculate_cost

PASSWORD = "CorrectHorse123"
REQ = {"student_name": "S", "document_name": "doc.pdf", "copies": 2, "pages": 5,
       "print_type": "Black & White"}


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


def actor(client, session, name, admin=False) -> dict:
    res = client.post("/api/auth/signup", json={
        "email": f"{name}@uni.edu", "full_name": name.title(), "password": PASSWORD})
    assert res.status_code == 201, res.text
    if admin:
        user = session.get(User, res.json()["user"]["id"])
        user.role = UserRole.admin
        session.add(user)
        session.commit()
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def people(client, session):
    return {"alice": actor(client, session, "alice"), "bob": actor(client, session, "bob"),
            "staff": actor(client, session, "staff", admin=True)}


def create(client, headers, **kw) -> dict:
    res = client.post("/api/print-requests", headers=headers, json={**REQ, **kw})
    assert res.status_code == 201, res.text
    return res.json()


# ----------------------------------------------------------------------- cost

def test_calculate_cost_uses_agreed_rates():
    assert calculate_cost(5, 2, PrintType.black_and_white) == 20   # 5 x 2 x Tk 2
    assert calculate_cost(3, 4, PrintType.color) == 120            # 3 x 4 x Tk 10


def test_pricing_endpoint_returns_rates(client, people):
    res = client.get("/api/print-requests/pricing", headers=people["alice"])
    assert res.status_code == 200
    assert res.json() == {"currency": "BDT", "rates_per_page": {"Black & White": 2, "Color": 10}}


def test_cost_is_calculated_and_stored_on_create(client, people):
    pr = create(client, people["alice"])
    assert (pr["pages"], pr["total_cost"], pr["payment_status"], pr["paid_at"]) == (5, 20, "Pending", None)
    color = create(client, people["alice"], print_type="Color", pages=3, copies=4)
    assert color["total_cost"] == 120


def test_client_cannot_set_its_own_price(client, people):
    pr = create(client, people["alice"], total_cost=1, payment_status="Paid")
    assert pr["total_cost"] == 20 and pr["payment_status"] == "Pending"


def test_cost_is_recalculated_when_pages_copies_or_type_change(client, people):
    pr = create(client, people["alice"])
    res = client.patch(f"/api/print-requests/{pr['id']}", headers=people["alice"],
                       json={"pages": 10, "print_type": "Color"})
    assert res.status_code == 200 and res.json()["total_cost"] == 10 * 2 * 10


@pytest.mark.parametrize("pages", [0, -1, 1001])
def test_invalid_page_count_rejected(client, people, pages):
    res = client.post("/api/print-requests", headers=people["alice"], json={**REQ, "pages": pages})
    assert res.status_code == 422


# -------------------------------------------------------------------- payment

def test_staff_marks_paid_and_it_is_audited(client, session, people):
    pr = create(client, people["alice"])
    res = client.patch(f"/api/print-requests/{pr['id']}/payment", headers=people["staff"],
                       json={"payment_status": "Paid"})
    assert res.status_code == 200
    assert res.json()["payment_status"] == "Paid" and res.json()["paid_at"] is not None
    log = session.exec(select(AuditLog).where(AuditLog.action == "request.payment")).one()
    assert log.details == {"from": "Pending", "to": "Paid", "amount": 20}
    # staff can correct a mistake
    back = client.patch(f"/api/print-requests/{pr['id']}/payment", headers=people["staff"],
                        json={"payment_status": "Pending"})
    assert back.json()["payment_status"] == "Pending" and back.json()["paid_at"] is None


def test_student_cannot_mark_paid_even_own_request(client, people):
    pr = create(client, people["alice"])
    res = client.patch(f"/api/print-requests/{pr['id']}/payment", headers=people["alice"],
                       json={"payment_status": "Paid"})
    assert res.status_code == 403
    assert client.get(f"/api/print-requests/{pr['id']}", headers=people["alice"]).json()["payment_status"] == "Pending"


def test_payment_requires_login(client, people):
    pr = create(client, people["alice"])
    assert client.patch(f"/api/print-requests/{pr['id']}/payment",
                        json={"payment_status": "Paid"}).status_code == 401


def test_paid_request_cannot_be_edited(client, people):
    pr = create(client, people["alice"])
    client.patch(f"/api/print-requests/{pr['id']}/payment", headers=people["staff"], json={"payment_status": "Paid"})
    got = client.get(f"/api/print-requests/{pr['id']}", headers=people["alice"]).json()
    assert got["permissions"]["edit"] is False
    res = client.patch(f"/api/print-requests/{pr['id']}", headers=people["alice"], json={"pages": 1})
    assert res.status_code == 403 and "Paid" in res.json()["detail"]


def test_rejected_request_cannot_be_marked_paid(client, people):
    pr = create(client, people["alice"])
    client.patch(f"/api/print-requests/{pr['id']}", headers=people["staff"],
                 json={"status": "Rejected", "reason": "Wrong file"})
    res = client.patch(f"/api/print-requests/{pr['id']}/payment", headers=people["staff"],
                       json={"payment_status": "Paid"})
    assert res.status_code == 409


def test_invalid_payment_status_rejected(client, people):
    pr = create(client, people["alice"])
    res = client.patch(f"/api/print-requests/{pr['id']}/payment", headers=people["staff"],
                       json={"payment_status": "Refunded"})
    assert res.status_code == 422


def test_filter_by_payment_status_and_permission_flag(client, people):
    a = create(client, people["alice"])
    create(client, people["alice"])
    client.patch(f"/api/print-requests/{a['id']}/payment", headers=people["staff"], json={"payment_status": "Paid"})
    res = client.get("/api/print-requests?payment_status=Paid", headers=people["staff"])
    assert [r["id"] for r in res.json()] == [a["id"]] and res.headers["X-Total-Count"] == "1"
    assert res.json()[0]["permissions"]["update_payment"] is True
    mine = client.get("/api/print-requests", headers=people["alice"]).json()
    assert all(r["permissions"]["update_payment"] is False for r in mine)
