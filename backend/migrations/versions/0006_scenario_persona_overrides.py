"""Add scenario persona overrides and environment revision fencing."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_scenario_persona_overrides"
down_revision = "0005_storage_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenarios",
        sa.Column("persona_overrides", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "scenarios",
        sa.Column("base_environment_revision", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("scenarios", "base_environment_revision")
    op.drop_column("scenarios", "persona_overrides")
