"""Printing cost and payment tracking on print_requests (additive).

* pages          INTEGER NOT NULL DEFAULT 1   (pages in the document)
* total_cost     INTEGER NOT NULL DEFAULT 0   (Taka, calculated by the server)
* payment_status paymentstatus NOT NULL DEFAULT 'pending'   ('pending' | 'paid')
* paid_at        TIMESTAMPTZ NULL

Existing rows get pages = 1 and their total_cost is filled in with the same
rates as pricing.py (B&W Tk 2, Color Tk 10 per page). No rows are deleted.

Revision ID: 0004_cost_and_payment
Revises: 0003_owner_required
Create Date: 2026-11-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_cost_and_payment"
down_revision: Union[str, Sequence[str], None] = "0003_owner_required"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL_COST_SQL = """
UPDATE print_requests
SET total_cost = pages * copies * CASE WHEN print_type = 'color' THEN 10 ELSE 2 END
"""


def _payment_type(dialect: str):
    if dialect == "postgresql":
        return postgresql.ENUM("pending", "paid", name="paymentstatus", create_type=False)
    return sa.Enum("pending", "paid", name="paymentstatus")


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        op.execute("CREATE TYPE paymentstatus AS ENUM ('pending', 'paid')")
    with op.batch_alter_table("print_requests") as batch:
        batch.add_column(sa.Column("pages", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("total_cost", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("payment_status", _payment_type(dialect), nullable=False,
                                   server_default="pending"))
        batch.add_column(sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(BACKFILL_COST_SQL)


def downgrade() -> None:
    with op.batch_alter_table("print_requests") as batch:
        batch.drop_column("paid_at")
        batch.drop_column("payment_status")
        batch.drop_column("total_cost")
        batch.drop_column("pages")
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS paymentstatus")
