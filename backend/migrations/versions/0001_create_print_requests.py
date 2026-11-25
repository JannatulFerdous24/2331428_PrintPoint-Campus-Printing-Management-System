"""Create print_requests table (Mid Project schema) in PostgreSQL.

This migration ONLY CREATES objects. It does not drop, delete or change any
existing data. It mirrors backend/models.py -> PrintRequest exactly.

Row Level Security (RLS) is enabled with no policies so that Supabase's public
Data API (REST) cannot read or write this table. Our FastAPI backend connects
as the table owner, which is not restricted by RLS, so the app keeps working.

Revision ID: 0001_create_print_requests
Revises:
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_print_requests"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum values are the Python enum NAMES, matching how SQLModel stores them.
PRINT_TYPE = sa.Enum("black_and_white", "color", name="printtype")
REQUEST_STATUS = sa.Enum(
    "pending", "processing", "ready", "collected", "rejected", name="requeststatus"
)


def upgrade() -> None:
    op.create_table(
        "print_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_name", sa.String(length=200), nullable=False),
        sa.Column("document_name", sa.String(length=500), nullable=False),
        sa.Column("copies", sa.Integer(), nullable=False),
        sa.Column("print_type", PRINT_TYPE, nullable=False),
        sa.Column("status", REQUEST_STATUS, nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_print_requests_student_name", "print_requests", ["student_name"]
    )

    if op.get_context().dialect.name == "postgresql":
        op.execute("ALTER TABLE print_requests ENABLE ROW LEVEL SECURITY")
        # Alembic's own bookkeeping table lives in the public schema too; without RLS
        # Supabase's Data API could read or change the recorded migration version.
        op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # WARNING: removes the table and its rows. Only run on a database whose data
    # has been backed up, or on an empty development database.
    op.drop_index("ix_print_requests_student_name", table_name="print_requests")
    op.drop_table("print_requests")
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS requeststatus")
        op.execute("DROP TYPE IF EXISTS printtype")
