"""Persist direct OASIS engine outputs and per-run selection."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0011_direct_oasis_engine"
down_revision = "0010_oasis_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scenario_runs", sa.Column("engine", sa.String(), nullable=False, server_default="deterministic"))
    op.create_check_constraint("scenario_runs_engine_valid", "scenario_runs", "engine IN ('deterministic','oasis')")
    op.add_column("oasis_actions", sa.Column("raw_action", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("oasis_runtime_mappings", sa.Column(
        "runtime_status", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")
    ))
    op.add_column("oasis_runtime_mappings", sa.Column(
        "artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")
    ))
    op.add_column("interviews", sa.Column("run_id", sa.String(), nullable=True))
    op.create_foreign_key("interviews_run_id_fkey", "interviews", "scenario_runs", ["run_id"], ["id"], ondelete="SET NULL")
    op.create_index("interviews_run_created", "interviews", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("interviews_run_created", table_name="interviews")
    op.drop_constraint("interviews_run_id_fkey", "interviews", type_="foreignkey")
    op.drop_column("interviews", "run_id")
    op.drop_column("oasis_runtime_mappings", "artifacts")
    op.drop_column("oasis_runtime_mappings", "runtime_status")
    op.drop_column("oasis_actions", "raw_action")
    op.drop_constraint("scenario_runs_engine_valid", "scenario_runs", type_="check")
    op.drop_column("scenario_runs", "engine")
