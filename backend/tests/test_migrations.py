"""
Migration safety tests.

Each test runs the real Alembic migrations against a brand-new SQLite file in
pytest's temporary folder (tmp_path). They never touch printpoint.db,
printpoint_dev.db, Supabase or any other real database.
"""

import io
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlmodel import SQLModel

import models  # noqa: F401  (registers every table on SQLModel.metadata)

BACKEND_DIR = Path(__file__).resolve().parent.parent
NEW_TABLES = {
    "users", "refresh_sessions", "login_attempts", "audit_logs",
    "groups", "group_members", "print_request_status_history",
}
NEW_PRINT_REQUEST_COLUMNS = {
    "owner_id", "group_id", "assignee_id", "storage_path",
    "original_filename", "content_type", "file_size_bytes", "uploaded_at",
}


def make_config(url: str, monkeypatch, buffer: io.StringIO | None = None) -> Config:
    monkeypatch.setenv("MIGRATION_DATABASE_URL", url)
    cfg = Config(output_buffer=buffer) if buffer else Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "migration_test.db"
    url = f"sqlite:///{path.as_posix()}"
    return url, make_config(url, monkeypatch)


def table_names(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


# --------------------------------------------------------------------------

def test_migrations_match_models_exactly(temp_db):
    """After `upgrade head`, the database must be exactly what models.py describes."""
    url, cfg = temp_db
    command.upgrade(cfg, "head")

    engine = sa.create_engine(url)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": False})
        diff = compare_metadata(ctx, SQLModel.metadata)
    engine.dispose()
    assert diff == [], f"models.py and migrations disagree: {diff}"


def test_upgrade_keeps_existing_print_requests_data(temp_db):
    """Rows created by the Mid Project schema (0001) survive 0002 unchanged."""
    url, cfg = temp_db
    command.upgrade(cfg, "0001_create_print_requests")

    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO print_requests (student_name, document_name, copies, print_type, "
            "status, notes, created_at, updated_at) VALUES ('Existing Student', 'old.pdf', 3, "
            "'color', 'processing', 'keep me', '2026-11-01 10:00:00', '2026-11-01 10:00:00')"
        ))

    command.upgrade(cfg, "0002_core_security_schema")

    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT * FROM print_requests")).mappings().one()
    engine.dispose()

    assert row["student_name"] == "Existing Student"
    assert row["document_name"] == "old.pdf"
    assert row["copies"] == 3
    assert row["print_type"] == "color"
    assert row["status"] == "processing"
    assert row["notes"] == "keep me"
    for column in NEW_PRINT_REQUEST_COLUMNS:
        assert row[column] is None  # new columns start empty


def test_downgrade_then_upgrade_is_reversible_and_keeps_mid_project_rows(temp_db):
    url, cfg = temp_db
    command.upgrade(cfg, "head")
    assert NEW_TABLES <= table_names(url)

    engine = sa.create_engine(url)
    with engine.begin() as conn:
        insert_user(conn, 1)
        conn.execute(sa.text(
            "INSERT INTO print_requests (student_name, document_name, copies, print_type, "
            "status, created_at, updated_at, owner_id) VALUES ('S', 'd.pdf', 1, 'black_and_white', "
            "'pending', '2026-11-01 10:00:00', '2026-11-01 10:00:00', 1)"
        ))

    command.downgrade(cfg, "0001_create_print_requests")
    assert table_names(url).isdisjoint(NEW_TABLES)
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM print_requests")).scalar() == 1

    command.upgrade(cfg, "0002_core_security_schema")  # owner_id comes back empty
    with engine.begin() as conn:
        insert_user(conn, 1)
        conn.execute(sa.text("UPDATE print_requests SET owner_id = 1"))  # explicit, as a human would
    command.upgrade(cfg, "head")
    assert NEW_TABLES <= table_names(url)
    engine.dispose()


# ----------------------------------------------------------------- migration 0003

def insert_user(conn, user_id: int) -> None:
    conn.execute(sa.text(
        "INSERT INTO users (id, email, full_name, password_hash, role, is_banned, "
        "failed_login_count, created_at, updated_at) VALUES "
        f"({user_id}, 'u{user_id}@uni.edu', 'U', 'x', 'user', 0, 0, "
        "'2026-11-01 10:00:00', '2026-11-01 10:00:00')"
    ))


def insert_request(conn, owner_id) -> None:
    conn.execute(sa.text(
        "INSERT INTO print_requests (student_name, document_name, copies, print_type, status, "
        "created_at, updated_at, owner_id) VALUES ('S', 'd.pdf', 1, 'color', 'pending', "
        "'2026-11-01 10:00:00', '2026-11-01 10:00:00', :owner)"
    ), {"owner": owner_id})


def test_0003_stops_and_changes_nothing_when_a_request_has_no_owner(temp_db):
    url, cfg = temp_db
    command.upgrade(cfg, "0002_core_security_schema")
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        insert_user(conn, 1)
        insert_request(conn, 1)
        insert_request(conn, None)  # an owner-less request

    with pytest.raises(RuntimeError, match="1 print request"):
        command.upgrade(cfg, "head")

    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        owners = sorted(r[0] or 0 for r in conn.execute(sa.text("SELECT owner_id FROM print_requests")))
    engine.dispose()
    assert version == "0002_core_security_schema"   # not applied
    assert owners == [0, 1]                          # no owner was guessed or assigned


def test_0003_succeeds_when_every_request_has_an_owner(temp_db):
    url, cfg = temp_db
    command.upgrade(cfg, "0002_core_security_schema")
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        insert_user(conn, 1)
        insert_request(conn, 1)
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0003_owner_required"
        with pytest.raises(sa.exc.IntegrityError):  # the database now refuses owner-less rows
            insert_request(conn, None)
    engine.dispose()


def test_0003_postgres_sql_checks_first_and_never_assigns_owners(monkeypatch):
    buffer = io.StringIO()
    cfg = make_config("postgresql://offline:offline@offline.invalid/offline", monkeypatch, buffer)
    command.upgrade(cfg, "0002_core_security_schema:0003_owner_required", sql=True)
    sql = buffer.getvalue()
    check = sql.index("IF EXISTS (SELECT 1 FROM print_requests WHERE owner_id IS NULL)")
    alter = sql.index("ALTER TABLE print_requests ALTER COLUMN owner_id SET NOT NULL")
    assert check < alter
    assert "RAISE EXCEPTION" in sql
    assert not re.search(r"UPDATE\s+print_requests|INSERT\s+INTO\s+print_requests|DELETE\s+FROM", sql)


def test_postgres_upgrade_sql_is_additive_and_enables_rls(monkeypatch):
    """Offline mode: generates PostgreSQL SQL text only, no connection is made."""
    buffer = io.StringIO()
    cfg = make_config("postgresql://offline:offline@offline.invalid/offline", monkeypatch, buffer)
    command.upgrade(cfg, "0001_create_print_requests:0002_core_security_schema", sql=True)
    sql = buffer.getvalue()

    # Check SQL *commands*, not words: "ON DELETE SET NULL" inside a foreign key is a
    # rule for the future, not a delete. Alembic's own version bookkeeping is allowed.
    statements = [s.strip().upper() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        if "ALEMBIC_VERSION" in stmt:
            continue
        assert not re.match(r"^(DROP|DELETE|TRUNCATE|UPDATE)\b", stmt), f"not additive: {stmt[:80]}"
        assert " DROP " not in stmt and "ALTER COLUMN" not in stmt and " RENAME " not in stmt, stmt[:80]
        assert re.match(r"^(BEGIN|COMMIT|CREATE|ALTER TABLE|-- )", stmt), f"unexpected: {stmt[:80]}"
    for table in NEW_TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
    # requeststatus already exists from 0001 and must not be created again.
    assert not re.search(r"CREATE TYPE requeststatus", sql)
    assert "CREATE TYPE userrole" in sql


def test_postgres_full_upgrade_enables_rls_on_every_table(monkeypatch):
    """Offline: every table created by `upgrade head` (incl. alembic_version) gets RLS."""
    buffer = io.StringIO()
    cfg = make_config("postgresql://offline:offline@offline.invalid/offline", monkeypatch, buffer)
    command.upgrade(cfg, "head", sql=True)
    sql = buffer.getvalue()

    created = set(re.findall(r"CREATE TABLE (\w+)", sql))
    rls = set(re.findall(r"ALTER TABLE (\w+) ENABLE ROW LEVEL SECURITY", sql))
    assert created == NEW_TABLES | {"print_requests", "alembic_version"}
    assert rls == created, f"tables without RLS: {created - rls}"
