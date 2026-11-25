"""
Database connection for PrintPoint.

Where the data lives is decided ONLY by the DATABASE_URL environment variable:

* Production (Vercel)  -> Supabase PostgreSQL through the transaction pooler (port 6543)
* Local development    -> whatever is in backend/.env (SQLite file or Supabase)
* Automated tests      -> in-memory SQLite (set by tests/conftest.py)

PostgreSQL tables are created by Alembic migrations (see backend/migrations),
never automatically at startup. SQLite tables are still auto-created so local
development and tests keep working without extra steps.
"""

import os

from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Load backend/.env for local development. On Vercel there is no .env file,
# so this does nothing and the real environment variables are used.
# override=False: a variable that is already set (e.g. by tests) always wins.
load_dotenv(override=False)


def normalize_database_url(url: str) -> str:
    """Tell SQLAlchemy to use the psycopg (v3) driver for PostgreSQL URLs.

    Supabase shows connection strings as "postgresql://..." (or the older
    "postgres://..."). SQLAlchemy needs "postgresql+psycopg://..." to pick psycopg 3.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def get_database_url() -> str:
    """Read DATABASE_URL and refuse unsafe settings in production."""
    url = os.getenv("DATABASE_URL", "").strip()
    on_vercel = bool(os.getenv("VERCEL"))  # Vercel sets VERCEL=1 automatically

    if not url:
        if on_vercel:
            raise RuntimeError(
                "DATABASE_URL is not set. Add the Supabase connection string "
                "in the Vercel project environment variables."
            )
        # Local development fallback: a SQLite file next to the backend code.
        # NOTE: deliberately NOT the Mid Project's printpoint.db - that file has the
        # old table layout and is kept untouched as historical data.
        url = "sqlite:///./printpoint_dev.db"

    if on_vercel and url.startswith("sqlite"):
        # SQLite on Vercel lives in temporary storage and is lost on restart.
        raise RuntimeError("SQLite is not allowed on Vercel. Use Supabase PostgreSQL.")

    return normalize_database_url(url)


def build_engine(url: str) -> Engine:
    """Create the SQLAlchemy engine with settings that suit the database type."""
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # In-memory database: share ONE connection so every session sees the same tables.
            return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
        return create_engine(url, connect_args=connect_args)

    # PostgreSQL (Supabase)
    return create_engine(
        url,
        # Vercel functions are short-lived; Supabase's pooler does the pooling,
        # so we open a connection per request and close it straight after.
        poolclass=NullPool,
        connect_args={
            # The Supabase transaction pooler (port 6543) does not support
            # prepared statements; None turns them off in psycopg 3.
            "prepare_threshold": None,
            # Always encrypt traffic to the database.
            "sslmode": "require",
        },
    )


DATABASE_URL = get_database_url()
engine = build_engine(DATABASE_URL)


def is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"


def init_db() -> None:
    """Called at app startup.

    SQLite (local dev / tests): create missing tables automatically.
    PostgreSQL: do nothing - the schema is managed by Alembic migrations.
    """
    if is_sqlite():
        SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
