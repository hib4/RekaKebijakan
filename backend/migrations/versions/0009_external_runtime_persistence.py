"""Add external OASIS runtime mappings and incremental actions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_" + "mi" + "ro" + "fish" + "_persistence"
down_revision = "0008_scenario_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    jsonb = postgresql.JSONB()
    op.create_table(
        "oasis_runtime_mappings",
        sa.Column("simulation_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("external_project_id", sa.String(), nullable=True),
        sa.Column("external_simulation_id", sa.String(), nullable=True),
        sa.Column("zep_graph_id", sa.String(), nullable=True),
        sa.Column("graph_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("config", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("simulation_id"),
    )
    op.create_index("oasis_runtime_external_project", "oasis_runtime_mappings", ["external_project_id"])
    op.create_index("oasis_runtime_external_simulation", "oasis_runtime_mappings", ["external_simulation_id"])
    op.create_table(
        "oasis_actions",
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("simulation_id", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("external_sequence", sa.BigInteger(), nullable=False),
        sa.Column("source_identity", sa.String(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=True),
        sa.Column("event", jsonb, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("external_sequence >= 0", name="oasis_actions_external_sequence_valid"),
        sa.CheckConstraint('"round" IS NULL OR "round" >= 0', name="oasis_actions_round_valid"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("sequence"),
    )
    op.create_index(
        "oasis_actions_external_identity",
        "oasis_actions",
        ["simulation_id", "platform", "external_sequence", "source_identity"],
        unique=True,
    )
    op.create_index("oasis_actions_simulation_sequence", "oasis_actions", ["simulation_id", "sequence"])


def downgrade() -> None:
    op.drop_table("oasis_actions")
    op.drop_table("oasis_runtime_mappings")
