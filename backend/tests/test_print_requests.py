import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite://"


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session):
    from database import get_session
    from main import app

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


SAMPLE_REQUEST = {
    "student_name": "Jannatul Ferdous",
    "document_name": "Assignment_1.pdf",
    "copies": 2,
    "print_type": "Black & White",
    "notes": "Please staple",
}


def test_create_print_request(client):
    response = client.post("/api/print-requests", json=SAMPLE_REQUEST)
    assert response.status_code == 201
    data = response.json()
    assert data["student_name"] == "Jannatul Ferdous"
    assert data["document_name"] == "Assignment_1.pdf"
    assert data["copies"] == 2
    assert data["print_type"] == "Black & White"
    assert data["status"] == "Pending"
    assert "id" in data


def test_create_invalid_copies(client):
    bad = {**SAMPLE_REQUEST, "copies": 0}
    response = client.post("/api/print-requests", json=bad)
    assert response.status_code == 422


def test_create_missing_required_field(client):
    bad = {"copies": 1, "print_type": "Color"}
    response = client.post("/api/print-requests", json=bad)
    assert response.status_code == 422


def test_list_print_requests(client):
    client.post("/api/print-requests", json=SAMPLE_REQUEST)
    client.post("/api/print-requests", json={**SAMPLE_REQUEST, "document_name": "Doc2.pdf"})
    response = client.get("/api/print-requests")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_print_request(client):
    create_response = client.post("/api/print-requests", json=SAMPLE_REQUEST)
    request_id = create_response.json()["id"]
    response = client.get(f"/api/print-requests/{request_id}")
    assert response.status_code == 200
    assert response.json()["id"] == request_id


def test_get_nonexistent(client):
    response = client.get("/api/print-requests/9999")
    assert response.status_code == 404


def test_update_print_request(client):
    create_response = client.post("/api/print-requests", json=SAMPLE_REQUEST)
    request_id = create_response.json()["id"]
    response = client.patch(
        f"/api/print-requests/{request_id}",
        json={"copies": 5, "notes": "Updated notes"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["copies"] == 5
    assert data["notes"] == "Updated notes"


def test_valid_status_transition(client):
    create_response = client.post("/api/print-requests", json=SAMPLE_REQUEST)
    request_id = create_response.json()["id"]
    # Pending -> Processing (valid)
    response = client.patch(
        f"/api/print-requests/{request_id}", json={"status": "Processing"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Processing"


def test_invalid_status_transition(client):
    create_response = client.post("/api/print-requests", json=SAMPLE_REQUEST)
    request_id = create_response.json()["id"]
    # Pending -> Collected (invalid)
    response = client.patch(
        f"/api/print-requests/{request_id}", json={"status": "Collected"}
    )
    assert response.status_code == 422


def test_delete_print_request(client):
    create_response = client.post("/api/print-requests", json=SAMPLE_REQUEST)
    request_id = create_response.json()["id"]
    response = client.delete(f"/api/print-requests/{request_id}")
    assert response.status_code == 204
    # Verify deleted
    get_response = client.get(f"/api/print-requests/{request_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent(client):
    response = client.delete("/api/print-requests/9999")
    assert response.status_code == 404


def test_filter_by_status(client):
    client.post("/api/print-requests", json=SAMPLE_REQUEST)
    client.post("/api/print-requests", json={**SAMPLE_REQUEST, "document_name": "Doc2.pdf"})
    response = client.get("/api/print-requests?status=Pending")
    assert response.status_code == 200
    data = response.json()
    assert all(r["status"] == "Pending" for r in data)
