"""Core security schema: users, sessions, login attempts, audit log, groups,
group permissions, status history, and new print_requests columns.

ADDITIVE ONLY:
* creates 7 new tables and 1 new enum type (userrole)
* adds 8 NULLABLE columns, 3 foreign keys and 5 indexes to print_requests
* enables Row Level Security on every new table
It does not drop, delete, rename or change the type of anything that exists.
Existing print_requests rows keep all their values; new columns start as NULL.

owner_id is nullable here on purpose ("expand"). Migration 0003 will make it
required ("contract") after every existing row has an owner.

Revision ID: 0002_core_security_schema
Revises: 0001_create_print_requests
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_core_security_schema"
down_revision: Union[str, Sequence[str], None] = "0001_create_print_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USER_ROLE = sa.Enum("user", "admin", name="userrole")

# requeststatus already exists (created in 0001) - reuse it, never re-create it.
REQUEST_STATUS_EXISTING = sa.Enum(
    "pending", "processing", "ready", "collected", "rejected", name="requeststatus"
).with_variant(
    postgresql.ENUM(
        "pending", "processing", "ready", "collected", "rejected",
        name="requeststatus", create_type=False,
    ),
    "postgresql",
)

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

NEW_TABLES = [
    "users",
    "refresh_sessions",
    "login_attempts",
    "audit_logs",
    "groups",
    "group_members",
    "print_request_status_history",
]


def ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    # ---------------------------------------------------------------- users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", USER_ROLE, nullable=False),
        sa.Column("is_banned", sa.Boolean(), nullable=False),
        sa.Column("ban_reason", sa.String(500), nullable=True),
        ts("banned_at", nullable=True),
        sa.Column("banned_by_id", sa.Integer(), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        ts("locked_until", nullable=True),
        ts("password_changed_at", nullable=True),
        ts("created_at"),
        ts("updated_at"),
        sa.ForeignKeyConstraint(
            ["banned_by_id"], ["users.id"], name="fk_users_banned_by_id_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_banned", "users", ["is_banned"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # ----------------------------------------------------- refresh_sessions
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("previous_token_hash", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        ts("created_at"),
        ts("last_used_at"),
        ts("expires_at"),
        ts("revoked_at", nullable=True),
        sa.Column("revoked_reason", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_refresh_sessions_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_token_hash", "refresh_sessions", ["token_hash"], unique=True)
    op.create_index(
        "ix_refresh_sessions_previous_token_hash", "refresh_sessions", ["previous_token_hash"]
    )

    # ------------------------------------------------------- login_attempts
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email_attempted", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(50), nullable=True),
        ts("created_at"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_login_attempts_user_id_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_login_attempts_email_attempted", "login_attempts", ["email_attempted"])
    op.create_index("ix_login_attempts_user_id", "login_attempts", ["user_id"])
    op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])
    op.create_index("ix_login_attempts_success", "login_attempts", ["success"])
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"])

    # ----------------------------------------------------------- audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.String(50), nullable=True),
        sa.Column("details", JSON_TYPE, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        ts("created_at"),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name="fk_audit_logs_actor_id_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_ip_address", "audit_logs", ["ip_address"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # --------------------------------------------------------------- groups
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        ts("created_at"),
        ts("updated_at"),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name="fk_groups_owner_id_users", ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_groups_owner_id", "groups", ["owner_id"])
    op.create_index("ix_groups_created_at", "groups", ["created_at"])

    # -------------------------------------------------------- group_members
    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("can_create", sa.Boolean(), nullable=False),
        sa.Column("can_edit", sa.Boolean(), nullable=False),
        sa.Column("can_assign", sa.Boolean(), nullable=False),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        ts("joined_at"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name="fk_group_members_group_id_groups", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_group_members_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["added_by_id"], ["users.id"], name="fk_group_members_added_by_id_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"])
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])

    # ------------------------------------- print_requests: new NULLABLE columns
    # batch_alter_table: plain ALTER TABLE on PostgreSQL; safe copy-and-swap on SQLite
    # (SQLite cannot add foreign keys with ALTER TABLE). Existing rows keep their data.
    with op.batch_alter_table("print_requests") as batch:
        batch.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("assignee_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("storage_path", sa.String(500), nullable=True))
        batch.add_column(sa.Column("original_filename", sa.String(255), nullable=True))
        batch.add_column(sa.Column("content_type", sa.String(100), nullable=True))
        batch.add_column(sa.Column("file_size_bytes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_print_requests_owner_id_users", "users", ["owner_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_print_requests_group_id_groups", "groups", ["group_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_foreign_key(
            "fk_print_requests_assignee_id_users", "users", ["assignee_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_print_requests_owner_id", ["owner_id"])
        batch.create_index("ix_print_requests_group_id", ["group_id"])
        batch.create_index("ix_print_requests_assignee_id", ["assignee_id"])
        batch.create_index("ix_print_requests_status", ["status"])
        batch.create_index("ix_print_requests_created_at", ["created_at"])

    # ------------------------------------------ print_request_status_history
    op.create_table(
        "print_request_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("print_request_id", sa.Integer(), nullable=False),
        sa.Column("from_status", REQUEST_STATUS_EXISTING, nullable=True),
        sa.Column("to_status", REQUEST_STATUS_EXISTING, nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        ts("changed_at"),
        sa.ForeignKeyConstraint(
            ["print_request_id"], ["print_requests.id"],
            name="fk_status_history_print_request_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["users.id"],
            name="fk_status_history_changed_by_id_users", ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_print_request_status_history_print_request_id",
        "print_request_status_history", ["print_request_id"],
    )
    op.create_index(
        "ix_print_request_status_history_changed_at",
        "print_request_status_history", ["changed_at"],
    )

    # ------------------------------------------------- Row Level Security
    # No policies = Supabase's public Data API cannot read/write these tables.
    # The backend connects as the table owner, which RLS does not restrict.
    if op.get_context().dialect.name == "postgresql":
        for table in NEW_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # WARNING: removes the 7 new tables and the 8 new print_requests columns
    # together with any data stored in them. The original Mid Project columns and
    # rows of print_requests are kept. Back up first; never run casually.
    op.drop_table("print_request_status_history")

    with op.batch_alter_table("print_requests") as batch:
        batch.drop_index("ix_print_requests_created_at")
        batch.drop_index("ix_print_requests_status")
        batch.drop_index("ix_print_requests_assignee_id")
        batch.drop_index("ix_print_requests_group_id")
        batch.drop_index("ix_print_requests_owner_id")
        batch.drop_constraint("fk_print_requests_assignee_id_users", type_="foreignkey")
        batch.drop_constraint("fk_print_requests_group_id_groups", type_="foreignkey")
        batch.drop_constraint("fk_print_requests_owner_id_users", type_="foreignkey")
        for column in (
            "uploaded_at", "file_size_bytes", "content_type", "original_filename",
            "storage_path", "assignee_id", "group_id", "owner_id",
        ):
            batch.drop_column(column)

    op.drop_table("group_members")
    op.drop_table("groups")
    op.drop_table("audit_logs")
    op.drop_table("login_attempts")
    op.drop_table("refresh_sessions")
    op.drop_table("users")

    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS userrole")
