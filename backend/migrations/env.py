"""
Alembic migration environment for PrintPoint.

Which database is migrated?
  1. MIGRATION_DATABASE_URL, if set (recommended: Supabase SESSION pooler, port 5432)
  2. otherwise DATABASE_URL
The URL is never stored in alembic.ini, so no secret ends up in Git.

Offline mode (`alembic upgrade head --sql`) only PRINTS the SQL and does not
connect to any database. Use it to review a migration before applying it.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

# Make backend/ importable (models.py, database.py) and load backend/.env.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env", override=False)

import models  # noqa: E402,F401  (registers all tables on SQLModel.metadata)
from database import normalize_database_url  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_migration_url() -> str:
    url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Set MIGRATION_DATABASE_URL (or DATABASE_URL) before running Alembic."
        )
    return normalize_database_url(url.strip())


def run_migrations_offline() -> None:
    """Generate SQL text only - no database connection is made."""
    context.configure(
        url=get_migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply migrations."""
    url = get_migration_url()
    connect_args = {}
    if url.startswith("postgresql"):
        connect_args = {"prepare_threshold": None, "sslmode": "require"}

    connectable = create_engine(url, poolclass=NullPool, connect_args=connect_args)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
