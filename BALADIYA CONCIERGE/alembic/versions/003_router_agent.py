"""003 router_agent: capture_requests, escalation_tickets + RLS

Revision ID: 003
Revises: 002
Create Date: 2026-06-04
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

TENANT_OWNED_TABLES = ["capture_requests", "escalation_tickets"]


def upgrade() -> None:
    op.create_table(
        "capture_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("session_id", sa.String(128), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("contact", sa.String(320), nullable=True),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "escalation_tickets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "capture_request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("capture_requests.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    for table in TENANT_OWNED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )


def downgrade() -> None:
    for table in TENANT_OWNED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("escalation_tickets")
    op.drop_table("capture_requests")
