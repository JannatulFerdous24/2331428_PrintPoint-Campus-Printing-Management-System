"""
Tests for database configuration rules (backend/database.py).

None of these tests connect to a real database or the network.
"""

import pytest
from sqlalchemy.pool import NullPool, StaticPool

import database


# --- Safety: tests must only ever use the in-memory database ---------------

def test_tests_use_in_memory_sqlite_only():
    url = database.engine.url
    assert url.get_backend_name() == "sqlite"
    assert url.database in (None, "", ":memory:")
    assert isinstance(database.engine.pool, StaticPool)


# --- URL normalisation ----------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgresql://u:p@host:6543/postgres", "postgresql+psycopg://u:p@host:6543/postgres"),
        ("postgres://u:p@host:6543/postgres", "postgresql+psycopg://u:p@host:6543/postgres"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///./printpoint.db", "sqlite:///./printpoint.db"),
    ],
)
def test_normalize_database_url(raw, expected):
    assert database.normalize_database_url(raw) == expected


# --- Production safety rules ----------------------------------------------

def test_vercel_without_database_url_refuses_to_start(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        database.get_database_url()


def test_vercel_with_sqlite_refuses_to_start(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/printpoint.db")
    with pytest.raises(RuntimeError, match="SQLite is not allowed on Vercel"):
        database.get_database_url()


def test_vercel_with_postgres_url_is_accepted(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@example.pooler.supabase.com:6543/postgres")
    assert database.get_database_url().startswith("postgresql+psycopg://")


def test_local_without_database_url_uses_local_sqlite_file(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Must NOT be the Mid Project's printpoint.db (old layout, kept untouched).
    assert database.get_database_url() == "sqlite:///./printpoint_dev.db"


# --- PostgreSQL engine settings (Supabase transaction pooler) -------------

def test_postgres_engine_uses_nullpool_without_prepared_statements(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    database.build_engine("postgresql+psycopg://u:p@example.pooler.supabase.com:6543/postgres")

    assert captured["poolclass"] is NullPool
    assert captured["connect_args"]["prepare_threshold"] is None
    assert captured["connect_args"]["sslmode"] == "require"


def test_init_db_creates_tables_for_sqlite():
    from sqlalchemy import inspect

    import models  # noqa: F401

    database.init_db()
    assert "print_requests" in inspect(database.engine).get_table_names()
