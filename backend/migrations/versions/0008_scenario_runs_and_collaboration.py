"""Add immutable scenario runs and persisted collaboration artifacts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_scenario_runs"
down_revision = "0007_project_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    jsonb = postgresql.JSONB()
    op.create_table("scenario_revisions",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("scenario_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False), sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", jsonb, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"))
    op.create_index("scenario_revisions_number", "scenario_revisions", ["scenario_id", "revision"], unique=True)
    op.create_table("scenario_runs",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("scenario_id", sa.String(), nullable=False), sa.Column("scenario_revision_id", sa.String(), nullable=False),
        sa.Column("simulation_id", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_snapshot", jsonb, nullable=False), sa.Column("output_snapshot", jsonb, nullable=True),
        sa.Column("provenance", jsonb, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued','running','paused','completed','failed','cancelled')", name="scenario_runs_status_valid"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_revision_id"], ["scenario_revisions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"))
    op.create_index("scenario_runs_scenario_created", "scenario_runs", ["scenario_id", sa.text("created_at DESC")])
    op.create_table("run_events", sa.Column("id", sa.String(), primary_key=True), sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("event", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["scenario_runs.id"], ondelete="CASCADE"))
    op.create_index("run_events_sequence", "run_events", ["run_id", "sequence"], unique=True)
    op.create_table("custom_personas", sa.Column("id", sa.String(), primary_key=True), sa.Column("scenario_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False), sa.Column("data", jsonb, nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"))
    op.create_index("custom_personas_scenario", "custom_personas", ["scenario_id", "created_at"])
    op.create_table("interviews", sa.Column("id", sa.String(), primary_key=True), sa.Column("simulation_id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False), sa.Column("content", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"))
    op.create_index("interviews_simulation_created", "interviews", ["simulation_id", sa.text("created_at DESC")])
    op.create_table("graph_feedback_versions", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("simulation_id", sa.String(), nullable=False), sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False), sa.Column("resulting_revision", sa.Integer(), nullable=False),
        sa.Column("content", jsonb, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"))
    op.create_index("graph_feedback_simulation_revision", "graph_feedback_versions", ["simulation_id", "resulting_revision"], unique=True)
    op.create_table("pilot_contacts", sa.Column("id", sa.String(), primary_key=True), sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False), sa.Column("institution", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True), sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column("jobs", sa.Column("run_id", sa.String(), nullable=True))
    op.create_foreign_key("jobs_run_id_fkey", "jobs", "scenario_runs", ["run_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("jobs_run_id_fkey", "jobs", type_="foreignkey")
    op.drop_column("jobs", "run_id")
    for table in ("pilot_contacts", "graph_feedback_versions", "interviews", "custom_personas", "run_events", "scenario_runs", "scenario_revisions"):
        op.drop_table(table)
