from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
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

jobs = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("simulation_id", String, ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("stage", String, nullable=False),
    Column("status", String, nullable=False),
    Column("config", JSONB, nullable=False),
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
