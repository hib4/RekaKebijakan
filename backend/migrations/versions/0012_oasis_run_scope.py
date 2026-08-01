"""Scope OASIS actions and artifacts to immutable scenario runs."""

import sqlalchemy as sa
from alembic import op


revision = "0012_oasis_run_scope"
down_revision = "0011_direct_oasis_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("oasis_actions", sa.Column("run_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "oasis_actions_run_id_fkey", "oasis_actions", "scenario_runs", ["run_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_index("oasis_actions_external_identity", table_name="oasis_actions")
    op.create_index(
        "oasis_actions_external_identity", "oasis_actions",
        ["simulation_id", "run_id", "platform", "external_sequence", "source_identity"],
        unique=True, postgresql_nulls_not_distinct=True,
    )
    op.create_index("oasis_actions_run_sequence", "oasis_actions", ["run_id", "sequence"])


def downgrade() -> None:
    op.drop_index("oasis_actions_run_sequence", table_name="oasis_actions")
    op.drop_index("oasis_actions_external_identity", table_name="oasis_actions")
    op.create_index(
        "oasis_actions_external_identity", "oasis_actions",
        ["simulation_id", "platform", "external_sequence", "source_identity"], unique=True,
    )
    op.drop_constraint("oasis_actions_run_id_fkey", "oasis_actions", type_="foreignkey")
    op.drop_column("oasis_actions", "run_id")
