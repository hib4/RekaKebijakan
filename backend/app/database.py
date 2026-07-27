from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import TSVECTOR


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

projects = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),
    Column("owner_user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("name", String, nullable=False),
    Column("institution", String, nullable=False),
    Column("objective", Text, nullable=False),
    Column("idempotency_key", String(255), nullable=True),
    Column("status", String, nullable=False, server_default="active"),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("archived_at", DateTime(timezone=True), nullable=True),
    Column("delete_after", DateTime(timezone=True), nullable=True),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("status IN ('draft','active','archived','pending_delete','deleted')", name="projects_status_valid"),
)
Index("projects_owner_updated", projects.c.owner_user_id, projects.c.updated_at.desc())
Index("projects_owner_status", projects.c.owner_user_id, projects.c.status)
Index("projects_owner_idempotency_key", projects.c.owner_user_id, projects.c.idempotency_key, unique=True)
Index(
    "projects_pending_delete_due",
    projects.c.delete_after,
    postgresql_where=text("status = 'pending_delete' AND deleted_at IS NULL"),
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

oasis_runtime_mappings = Table(
    "oasis_runtime_mappings",
    metadata,
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), primary_key=True),
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("external_project_id", String, nullable=True),
    Column("external_simulation_id", String, nullable=True),
    Column("zep_graph_id", String, nullable=True),
    Column("graph_revision", Integer, nullable=False, server_default="0"),
    Column("status", String, nullable=False),
    Column("config", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
Index("oasis_runtime_external_project", oasis_runtime_mappings.c.external_project_id)
Index("oasis_runtime_external_simulation", oasis_runtime_mappings.c.external_simulation_id)

oasis_actions = Table(
    "oasis_actions",
    metadata,
    Column("sequence", BigInteger, Identity(), primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("platform", String, nullable=False),
    Column("external_sequence", BigInteger, nullable=False),
    Column("source_identity", String, nullable=False),
    Column("round", Integer, nullable=True),
    Column("event", JSONB, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("external_sequence >= 0", name="oasis_actions_external_sequence_valid"),
    CheckConstraint('"round" IS NULL OR "round" >= 0', name="oasis_actions_round_valid"),
)
Index(
    "oasis_actions_external_identity",
    oasis_actions.c.simulation_id,
    oasis_actions.c.platform,
    oasis_actions.c.external_sequence,
    oasis_actions.c.source_identity,
    unique=True,
)
Index("oasis_actions_simulation_sequence", oasis_actions.c.simulation_id, oasis_actions.c.sequence)

scenarios = Table(
    "scenarios",
    metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("name", String, nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("kind", String, nullable=False, server_default="custom"),
    Column("config", JSONB, nullable=False),
    Column("persona_overrides", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("base_environment_revision", Integer, nullable=False, server_default="0"),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("archived_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("kind IN ('baseline','revision','custom')", name="scenarios_kind_valid"),
)
Index("scenarios_project_updated", scenarios.c.project_id, scenarios.c.updated_at.desc())

scenario_revisions = Table(
    "scenario_revisions", metadata,
    Column("id", String, primary_key=True),
    Column("scenario_id", String, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("snapshot", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("scenario_revisions_number", scenario_revisions.c.scenario_id, scenario_revisions.c.revision, unique=True)

scenario_runs = Table(
    "scenario_runs", metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("scenario_id", String, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
    Column("scenario_revision_id", String, ForeignKey("scenario_revisions.id", ondelete="RESTRICT"), nullable=False),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("status", String, nullable=False),
    Column("input_snapshot", JSONB, nullable=False),
    Column("output_snapshot", JSONB, nullable=True),
    Column("provenance", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("status IN ('queued','running','paused','completed','failed','cancelled')", name="scenario_runs_status_valid"),
)
Index("scenario_runs_scenario_created", scenario_runs.c.scenario_id, scenario_runs.c.created_at.desc())

run_events = Table(
    "run_events", metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("scenario_runs.id", ondelete="CASCADE"), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("event", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("run_events_sequence", run_events.c.run_id, run_events.c.sequence, unique=True)

custom_personas = Table(
    "custom_personas", metadata,
    Column("id", String, primary_key=True),
    Column("scenario_id", String, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("data", JSONB, nullable=False),
    Column("active", Boolean, nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
Index("custom_personas_scenario", custom_personas.c.scenario_id, custom_personas.c.created_at)

interviews = Table(
    "interviews", metadata,
    Column("id", String, primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("owner_user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("content", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("interviews_simulation_created", interviews.c.simulation_id, interviews.c.created_at.desc())

graph_feedback_versions = Table(
    "graph_feedback_versions", metadata,
    Column("id", String, primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("owner_user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("base_revision", Integer, nullable=False),
    Column("resulting_revision", Integer, nullable=False),
    Column("content", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("graph_feedback_simulation_revision", graph_feedback_versions.c.simulation_id, graph_feedback_versions.c.resulting_revision, unique=True)

pilot_contacts = Table(
    "pilot_contacts", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False),
    Column("institution", String, nullable=True),
    Column("message", Text, nullable=True),
    Column("consent", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

artifact_versions = Table(
    "artifact_versions",
    metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("artifact_type", String, nullable=False),
    Column("version", Integer, nullable=False),
    Column("input_revision", Integer, nullable=False),
    Column("provider", String, nullable=False),
    Column("model", String, nullable=True),
    Column("prompt_version", String, nullable=True),
    Column("status", String, nullable=False),
    Column("content", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("artifact_versions_resource", artifact_versions.c.simulation_id, artifact_versions.c.artifact_type, artifact_versions.c.version, unique=True)

audit_events = Table(
    "audit_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("actor_user_id", String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
    Column("action", String, nullable=False),
    Column("resource_type", String, nullable=False),
    Column("resource_id", String, nullable=False),
    Column("metadata", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("audit_events_project_created", audit_events.c.project_id, audit_events.c.created_at.desc())

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
    Column("media_type", String, nullable=True),
    Column("size_bytes", Integer, nullable=True),
    Column("sha256", String(64), nullable=True),
    Column("page_count", Integer, nullable=True),
    Column("language", String, nullable=True),
    Column("extraction_version", String, nullable=False, server_default="1"),
    Column("status", String, nullable=False, server_default="ready"),
    Column("created_at", DateTime(timezone=True), nullable=True),
)
Index("documents_simulation_name", documents.c.simulation_id, documents.c.name)
Index("documents_simulation_size", documents.c.simulation_id, documents.c.size_bytes)

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
    Column("search_vector", TSVECTOR, nullable=True),
    CheckConstraint("char_start >= 0 AND char_end >= char_start", name="document_chunks_offsets_valid"),
)
Index("document_chunks_document_ordinal", document_chunks.c.document_id, document_chunks.c.ordinal, unique=True)
Index("document_chunks_simulation", document_chunks.c.simulation_id)
Index("document_chunks_search", document_chunks.c.search_vector, postgresql_using="gin")

document_pages = Table(
    "document_pages",
    metadata,
    Column("id", String, primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("document_id", String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
    Column("page_number", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("char_start", Integer, nullable=False),
    Column("char_end", Integer, nullable=False),
    Column("metadata", JSONB, nullable=False),
)
Index("document_pages_document_number", document_pages.c.document_id, document_pages.c.page_number, unique=True)

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
    Column("run_id", String, ForeignKey("scenario_runs.id", ondelete="SET NULL"), nullable=True),
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
    Column("execution_token", String, nullable=True),
    Column("lease_generation", Integer, nullable=False, server_default="0"),
    Column("cancel_requested_at", DateTime(timezone=True), nullable=True),
    Column("pause_requested_at", DateTime(timezone=True), nullable=True),
    Column("error_code", String, nullable=True),
    Column("error_class", String, nullable=True),
    Column("retryable", String, nullable=True),
    Column("next_retry_at", DateTime(timezone=True), nullable=True),
    Column("progress", Integer, nullable=False, server_default="0"),
    Column("checkpoint", JSONB, nullable=True),
    Column("dead_lettered_at", DateTime(timezone=True), nullable=True),
    Column("idempotency_key", String, nullable=True),
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

job_attempts = Table(
    "job_attempts",
    metadata,
    Column("id", String, primary_key=True),
    Column("job_id", String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("worker_id", String, nullable=False),
    Column("execution_token", String, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("heartbeat_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("outcome", String, nullable=True),
    Column("error_code", String, nullable=True),
    Column("error_message", Text, nullable=True),
)
Index("job_attempts_job_attempt", job_attempts.c.job_id, job_attempts.c.attempt, unique=True)
