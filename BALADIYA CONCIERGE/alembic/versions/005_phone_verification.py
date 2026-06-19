"""Add phone verification and false-report blocking.

Revision ID: 005
Revises: 004
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add phone accountability columns to capture_requests
    op.add_column("capture_requests", sa.Column("visitor_phone_hash", sa.String(64), nullable=True))
    op.add_column("capture_requests", sa.Column("is_false_report", sa.Boolean(), nullable=False, server_default=sa.false()))

    # Blocked reporters — one row per (tenant, phone_hash); incremented on each false flag
    op.create_table(
        "blocked_reporters",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("phone_hash", sa.String(64), nullable=False),
        sa.Column("false_report_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_blocked_reporters_tenant_phone", "blocked_reporters", ["tenant_id", "phone_hash"], unique=True)

    # RLS: blocked_reporters is admin-only (platform manager + tenant admin reads)
    op.execute("ALTER TABLE blocked_reporters ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY blocked_reporters_tenant_isolation ON blocked_reporters
        USING (
            tenant_id::text = current_setting('app.current_tenant', TRUE)
            OR current_setting('app.current_tenant', TRUE) IS NULL
        );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS blocked_reporters_tenant_isolation ON blocked_reporters;")
    op.drop_table("blocked_reporters")
    op.drop_column("capture_requests", "is_false_report")
    op.drop_column("capture_requests", "visitor_phone_hash")
