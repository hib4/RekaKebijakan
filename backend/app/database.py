from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB


metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

simulations = Table(
    "simulations",
    metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, nullable=False),
    Column("state", JSONB, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("owner_user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
)
Index("simulations_owner_updated", simulations.c.owner_user_id, simulations.c.updated_at.desc())

sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
Index("sessions_user_id", sessions.c.user_id)
Index("sessions_expires_at", sessions.c.expires_at)

documents = Table(
    "documents",
    metadata,
    Column("id", String, primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("name", String, nullable=False),
    Column("path", Text, nullable=False),
    Column("text", Text, nullable=False),
)
Index("documents_simulation_name", documents.c.simulation_id, documents.c.name)

document_chunks = Table(
    "document_chunks",
    metadata,
    Column("id", String, primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("document_id", String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("char_start", Integer, nullable=False),
    Column("char_end", Integer, nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("metadata", JSONB, nullable=False),
    CheckConstraint("char_start >= 0 AND char_end >= char_start", name="document_chunks_offsets_valid"),
)
Index("document_chunks_document_ordinal", document_chunks.c.document_id, document_chunks.c.ordinal, unique=True)
Index("document_chunks_simulation", document_chunks.c.simulation_id)

citations = Table(
    "citations",
    metadata,
    Column("id", String, primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("artifact_type", String, nullable=False),
    Column("artifact_id", String, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("source_type", String, nullable=False),
    Column("source_id", String, nullable=False),
    Column("document_id", String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True),
    Column("chunk_id", String, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=True),
    Column("locator", JSONB, nullable=False),
    Column("quote", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "source_type IN ('document_chunk','event','graph_node','interview_answer','report_section')",
        name="citations_source_type_valid",
    ),
)
Index("citations_artifact", citations.c.simulation_id, citations.c.artifact_type, citations.c.artifact_id)
Index("citations_source", citations.c.simulation_id, citations.c.source_type, citations.c.source_id)

jobs = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("stage", String, nullable=False),
    Column("status", String, nullable=False),
    Column("config", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("available_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("lease_owner", String, nullable=True),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("heartbeat_at", DateTime(timezone=True), nullable=True),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("max_attempts", Integer, nullable=False, server_default="3"),
    Column("last_error", Text, nullable=True),
    Column("result", JSONB, nullable=True),
    Column("input_revision", Integer, nullable=False, server_default="0"),
    CheckConstraint(
        "status IN ('queued','running','paused','completed','failed','cancelled')",
        name="jobs_status_valid",
    ),
)
Index("jobs_simulation_status", jobs.c.simulation_id, jobs.c.status)
Index(
    "one_active_job_per_simulation",
    jobs.c.simulation_id,
    unique=True,
    postgresql_where=text("status IN ('queued','running','paused')"),
)
