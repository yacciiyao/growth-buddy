"""init schema

Revision ID: 0001_init
Revises: 
Create Date: 2026-01-06
"""

from __future__ import annotations

# 执行方式：在项目根目录运行 `alembic upgrade head`。
from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


if __name__ == "__main__":
    raise SystemExit(
        "This file is an Alembic migration script. "
        "Do NOT run it with `python`. "
        "Run `alembic upgrade head` from the project root instead."
    )


def upgrade() -> None:
    # parents
    op.create_table(
        "parents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_parents_phone", "parents", ["phone"], unique=True)
    op.create_index("ix_parents_email", "parents", ["email"], unique=True)

    # auth_sessions
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("revoked_at", sa.BigInteger(), nullable=True),
        sa.Column("last_seen_at", sa.BigInteger(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["parents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_parent_id", "auth_sessions", ["parent_id"], unique=False)
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)

    # children
    op.create_table(
        "children",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("interests", sa.String(length=512), nullable=True),
        sa.Column("forbidden_topics", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["parents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_children_parent_id", "children", ["parent_id"], unique=False)

    # devices
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_sn", sa.String(length=64), nullable=False),
        sa.Column("bound_child_id", sa.Integer(), nullable=True),
        sa.Column("toy_name", sa.String(length=50), nullable=True),
        sa.Column("toy_age", sa.String(length=10), nullable=True),
        sa.Column("toy_gender", sa.String(length=20), nullable=True),
        sa.Column("toy_persona", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.Column("last_seen_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["bound_child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_sn"),
    )
    op.create_index("ix_devices_device_sn", "devices", ["device_sn"], unique=True)
    op.create_index("ix_devices_bound_child_id", "devices", ["bound_child_id"], unique=False)

    # chat_sessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("ended_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sessions_child_id", "chat_sessions", ["child_id"], unique=False)

    # turns
    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=True),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("user_audio_path", sa.String(length=512), nullable=True),
        sa.Column("reply_audio_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.Column("playback_status", sa.String(length=20), nullable=True),
        sa.Column("resume_count", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=True),
        sa.Column("audit_action", sa.String(length=32), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("risk_flag", sa.Boolean(), nullable=False),
        sa.Column("risk_source", sa.String(length=20), nullable=True),
        sa.Column("risk_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_turns_session_id", "turns", ["session_id"], unique=False)
    op.create_index("ix_turns_device_id", "turns", ["device_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_turns_device_id", table_name="turns")
    op.drop_index("ix_turns_session_id", table_name="turns")
    op.drop_table("turns")

    op.drop_index("ix_chat_sessions_child_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    op.drop_index("ix_devices_bound_child_id", table_name="devices")
    op.drop_index("ix_devices_device_sn", table_name="devices")
    op.drop_table("devices")

    op.drop_index("ix_children_parent_id", table_name="children")
    op.drop_table("children")

    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_parent_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("ix_parents_email", table_name="parents")
    op.drop_index("ix_parents_phone", table_name="parents")
    op.drop_table("parents")
