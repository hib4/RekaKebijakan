"""Add evidence provenance and durable worker leases."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_evidence_and_worker"
down_revision = "0001_initial_postgresql"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("simulation_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("char_start >= 0 AND char_end >= char_start", name="document_chunks_offsets_valid"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("document_chunks_document_ordinal", "document_chunks", ["document_id", "ordinal"], unique=True)
    op.create_index("document_chunks_simulation", "document_chunks", ["simulation_id"])
    op.create_table(
        "citations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("simulation_id", sa.String(), nullable=False),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=True),
        sa.Column("chunk_id", sa.String(), nullable=True),
        sa.Column("locator", postgresql.JSONB(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('document_chunk','event','graph_node','interview_answer','report_section')",
            name="citations_source_type_valid",
        ),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
    )
    op.create_index("citations_artifact", "citations", ["simulation_id", "artifact_type", "artifact_id"])
    op.create_index("citations_source", "citations", ["simulation_id", "source_type", "source_id"])

    for name, column in (
        ("created_at", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True)),
        ("updated_at", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)),
        ("available_at", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True)),
        ("started_at", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)),
        ("completed_at", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)),
        ("lease_owner", sa.Column("lease_owner", sa.String(), nullable=True)),
        ("lease_expires_at", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True)),
        ("heartbeat_at", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)),
        ("attempts", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0")),
        ("max_attempts", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3")),
        ("last_error", sa.Column("last_error", sa.Text(), nullable=True)),
        ("result", sa.Column("result", postgresql.JSONB(), nullable=True)),
        ("input_revision", sa.Column("input_revision", sa.Integer(), nullable=False, server_default="0")),
    ):
        op.add_column("jobs", column)
    op.execute("UPDATE jobs SET created_at=now(), updated_at=now(), available_at=now()")
    op.alter_column("jobs", "created_at", nullable=False)
    op.alter_column("jobs", "updated_at", nullable=False)
    op.alter_column("jobs", "available_at", nullable=False)


def downgrade() -> None:
    for name in (
        "input_revision", "result", "last_error", "max_attempts", "attempts", "heartbeat_at",
        "lease_expires_at", "lease_owner", "completed_at", "started_at", "available_at", "updated_at", "created_at",
    ):
        op.drop_column("jobs", name)
    op.drop_table("citations")
    op.drop_table("document_chunks")
