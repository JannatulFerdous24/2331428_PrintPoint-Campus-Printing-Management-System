"""Make print_requests.owner_id required (NOT NULL).

Safe "contract" step after 0002 added owner_id as nullable:
* FIRST checks that no print request is missing an owner. If any is, the whole
  migration stops with an error and NOTHING is changed (it runs in a transaction).
* Then adds the NOT NULL rule. No rows are inserted, updated or deleted.

Revision ID: 0003_owner_required
Revises: 0002_core_security_schema
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_owner_required"
down_revision: Union[str, Sequence[str], None] = "0002_core_security_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PRECHECK_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM print_requests WHERE owner_id IS NULL) THEN
        RAISE EXCEPTION 'Migration 0003 stopped: % print request(s) have no owner. Assign owners first; nothing was changed.',
            (SELECT count(*) FROM print_requests WHERE owner_id IS NULL);
    END IF;
END
$$
"""


def upgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute(PRECHECK_SQL)
        op.alter_column("print_requests", "owner_id", existing_type=sa.Integer(), nullable=False)
    else:  # SQLite (tests / local development)
        if not op.get_context().as_sql:
            missing = op.get_bind().execute(
                sa.text("SELECT count(*) FROM print_requests WHERE owner_id IS NULL")
            ).scalar()
            if missing:
                raise RuntimeError(f"Migration 0003 stopped: {missing} print request(s) have no owner.")
        with op.batch_alter_table("print_requests") as batch:
            batch.alter_column("owner_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    # Only relaxes the rule again; no data is touched.
    with op.batch_alter_table("print_requests") as batch:
        batch.alter_column("owner_id", existing_type=sa.Integer(), nullable=True)
