"""Prompt 8b - document upload/download (in-memory SQLite + in-memory storage, no network)."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import models  # noqa: F401
from config import get_settings
from documents import MAX_UPLOAD_BYTES, safe_filename
from models import AuditLog, User, UserRole
from storage import MemoryStorage, get_optional_storage, get_storage

PASSWORD = "CorrectHorse123"
REQ = {"student_name": "S", "document_name": "doc", "copies": 1, "print_type": "Color"}
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def make_docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


@pytest.fixture(name="store")
def store_fixture():
    return MemoryStorage()


@pytest.fixture(name="session")
def session_fixture():
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session, store):
    from database import get_session
    from main import app

    def override():
        yield session
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_storage] = lambda: store
    app.dependency_overrides[get_optional_storage] = lambda: store
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
    return {n: Actor(client, session, n, admin=(n == "staff")) for n in ("alice", "bob", "staff")}


def new_request(client, actor, **extra):
    res = client.post("/api/print-requests", headers=actor.h, json={**REQ, **extra})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def upload(client, actor, rid, name, data, ctype="application/octet-stream"):
    return client.put(f"/api/print-requests/{rid}/document", headers=actor.h, files={"file": (name, data, ctype)})


def test_pdf_and_docx_upload_and_signed_download(client, store, people):
    alice, staff = people["alice"], people["staff"]
    rid = new_request(client, alice)
    res = upload(client, alice, rid, "Assignment 1.pdf", PDF, "application/pdf")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["has_document"] and body["original_filename"] == "Assignment 1.pdf"
    assert body["content_type"] == "application/pdf" and body["file_size_bytes"] == len(PDF)
    assert "storage_path" not in body  # private key never leaves the server
    assert list(store.objects.values())[0] == (PDF, "application/pdf")
    for who in (alice, staff):  # owner and staff may download
        link = client.get(f"/api/print-requests/{rid}/document", headers=who.h)
        assert link.status_code == 200 and link.json()["expires_in"] == 60
        assert "expires=60" in link.json()["url"]
    rid2 = new_request(client, alice)
    res = upload(client, alice, rid2, "report.docx", make_docx())
    assert res.status_code == 200 and res.json()["content_type"].endswith("wordprocessingml.document")


@pytest.mark.parametrize("name,data,code", [
    ("virus.exe", b"MZ\x90\x00", 415),
    ("notes.txt", b"hello", 415),
    ("fake.pdf", b"MZ this is an exe", 415),           # wrong content for .pdf
    ("fake.docx", b"%PDF-1.4 not a docx", 415),
    ("plain.docx", b"PK\x03\x04" + b"0" * 50, 415),    # zip header but not a real docx
    ("empty.pdf", b"", 400),
    ("big.pdf", b"%PDF-" + b"0" * MAX_UPLOAD_BYTES, 413),  # 4,000,005 bytes
])
def test_bad_files_are_refused(client, store, people, name, data, code):
    rid = new_request(client, people["alice"])
    assert upload(client, people["alice"], rid, name, data).status_code == code
    assert store.objects == {}


def test_exactly_the_limit_is_accepted(client, people):
    rid = new_request(client, people["alice"])
    data = b"%PDF-" + b"0" * (MAX_UPLOAD_BYTES - 5)
    assert upload(client, people["alice"], rid, "max.pdf", data).status_code == 200


def test_safe_filenames():
    assert safe_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert safe_filename("C:\\Users\\x\\My <doc>.pdf") == "My doc.pdf"
    assert safe_filename("   ") == "document"
    assert len(safe_filename("a" * 300 + ".pdf")) == 200


def test_access_rules(client, session, people):
    alice, bob, staff = people["alice"], people["bob"], people["staff"]
    rid = new_request(client, alice)
    assert upload(client, bob, rid, "x.pdf", PDF).status_code == 404       # not visible to bob
    assert upload(client, alice, rid, "x.pdf", PDF).status_code == 200
    assert client.get(f"/api/print-requests/{rid}/document", headers=bob.h).status_code == 404
    assert upload(client, staff, rid, "y.pdf", PDF).status_code == 403     # staff do not edit documents
    client.patch(f"/api/print-requests/{rid}", headers=staff.h, json={"status": "Processing"})
    res = upload(client, alice, rid, "late.pdf", PDF)                       # no longer Pending
    assert res.status_code == 403 and "Pending" in res.json()["detail"]
    no_doc = new_request(client, alice)
    assert client.get(f"/api/print-requests/{no_doc}/document", headers=alice.h).status_code == 404
    # group member without can_edit may view/download but not upload
    gid = client.post("/api/groups", headers=alice.h, json={"name": "T"}).json()["id"]
    client.post(f"/api/groups/{gid}/members", headers=alice.h, json={"email": bob.email})
    grid = new_request(client, alice, group_id=gid)
    upload(client, alice, grid, "g.pdf", PDF)
    assert client.get(f"/api/print-requests/{grid}/document", headers=bob.h).status_code == 200
    assert upload(client, bob, grid, "b.pdf", PDF).status_code == 403
    actions = {a.action for a in session.exec(select(AuditLog)).all()}
    assert {"request.document_upload", "request.document_download"} <= actions


def test_replace_and_delete_remove_old_files(client, store, people):
    alice, staff = people["alice"], people["staff"]
    rid = new_request(client, alice)
    upload(client, alice, rid, "v1.pdf", PDF)
    first = set(store.objects)
    upload(client, alice, rid, "v2.pdf", PDF + b"v2")
    assert len(store.objects) == 1 and set(store.objects) != first        # old file removed
    assert client.delete(f"/api/print-requests/{rid}", headers=alice.h).status_code == 204
    assert store.objects == {}
    rid2 = new_request(client, alice)
    upload(client, alice, rid2, "m.pdf", PDF)
    assert client.delete(f"/api/admin/print-requests/{rid2}", headers=staff.h).status_code == 204
    assert store.objects == {}


def test_storage_not_configured_gives_503(session):
    from database import get_session
    from main import app
    app.dependency_overrides[get_session] = lambda: (yield session)
    try:
        with TestClient(app) as client:
            a = Actor(client, session, "solo")
            rid = new_request(client, a)
            assert upload(client, a, rid, "x.pdf", PDF).status_code == 503
            assert client.delete(f"/api/print-requests/{rid}", headers=a.h).status_code == 204  # delete still works
    finally:
        app.dependency_overrides.clear()
