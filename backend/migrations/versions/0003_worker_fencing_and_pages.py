"""Add worker fencing, attempts, and page-aware evidence."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_worker_fencing_and_pages"
down_revision = "0002_evidence_and_worker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column("media_type", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("extraction_version", sa.String(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("documents", column)
    op.execute("UPDATE documents SET created_at=now() WHERE created_at IS NULL")

    op.add_column("document_chunks", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True))
    op.execute("UPDATE document_chunks SET search_vector=to_tsvector('simple', text)")
    op.create_index("document_chunks_search", "document_chunks", ["search_vector"], postgresql_using="gin")
    op.execute("""
        CREATE FUNCTION document_chunks_search_trigger() RETURNS trigger AS $$
        BEGIN
          NEW.search_vector := to_tsvector('simple', coalesce(NEW.text, ''));
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER document_chunks_search_update
        BEFORE INSERT OR UPDATE OF text ON document_chunks
        FOR EACH ROW EXECUTE FUNCTION document_chunks_search_trigger();
    """)
    op.create_table(
        "document_pages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("simulation_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("document_pages_document_number", "document_pages", ["document_id", "page_number"], unique=True)

    for column in (
        sa.Column("execution_token", sa.String(), nullable=True),
        sa.Column("lease_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pause_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_class", sa.String(), nullable=True),
        sa.Column("retryable", sa.String(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checkpoint", postgresql.JSONB(), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
    ):
        op.add_column("jobs", column)
    op.create_table(
        "job_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("execution_token", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("job_attempts_job_attempt", "job_attempts", ["job_id", "attempt"], unique=True)


def downgrade() -> None:
    op.drop_table("job_attempts")
    for name in (
        "idempotency_key", "dead_lettered_at", "checkpoint", "progress", "next_retry_at", "retryable",
        "error_class", "error_code", "pause_requested_at", "cancel_requested_at", "lease_generation", "execution_token",
    ):
        op.drop_column("jobs", name)
    op.drop_table("document_pages")
    op.execute("DROP TRIGGER IF EXISTS document_chunks_search_update ON document_chunks")
    op.execute("DROP FUNCTION IF EXISTS document_chunks_search_trigger")
    op.drop_index("document_chunks_search", table_name="document_chunks")
    op.drop_column("document_chunks", "search_vector")
    for name in ("created_at", "status", "extraction_version", "language", "page_count", "sha256", "size_bytes", "media_type"):
        op.drop_column("documents", name)
