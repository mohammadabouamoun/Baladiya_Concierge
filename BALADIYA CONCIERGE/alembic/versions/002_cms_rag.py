"""002 cms_rag: cms_entries, cms_chunks (pgvector 1536-dim, HNSW) + RLS

Revision ID: 002
Revises: 001
Create Date: 2026-06-02
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

TENANT_OWNED_TABLES = ["cms_entries", "cms_chunks"]


def upgrade() -> None:
    # pgvector extension was created in 001; CREATE EXTENSION IF NOT EXISTS is idempotent
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "cms_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("lang", sa.String(10), nullable=False, server_default="en"),
        sa.Column("embedding_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "cms_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cms_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    # Add vector(1536) column separately — pgvector type not available in plain SA dialect
    op.execute("ALTER TABLE cms_chunks ADD COLUMN embedding vector(1536)")

    # HNSW index for cosine similarity search (m=16, ef_construction=64 are pgvector defaults)
    op.execute(
        "CREATE INDEX cms_chunks_embedding_hnsw ON cms_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
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

    op.drop_index("cms_chunks_embedding_hnsw", table_name="cms_chunks")
    op.drop_table("cms_chunks")
    op.drop_table("cms_entries")
