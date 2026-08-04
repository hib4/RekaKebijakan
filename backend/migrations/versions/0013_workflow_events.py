"""Add durable workflow event stream."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0013_workflow_events"
down_revision = "0012_oasis_run_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_events",
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("simulation_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "workflow_events_simulation_sequence", "workflow_events", ["simulation_id", "sequence"]
    )


def downgrade() -> None:
    op.drop_index("workflow_events_simulation_sequence", table_name="workflow_events")
    op.drop_table("workflow_events")
