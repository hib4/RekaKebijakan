"""Add explicit project workflow mode and demo provenance."""

import sqlalchemy as sa
from alembic import op


revision = "0014_quick_demo"
down_revision = "0013_workflow_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("workflow_mode", sa.String(), nullable=False, server_default="full_simulation"),
    )
    op.add_column("projects", sa.Column("demo_bundle_id", sa.String(), nullable=True))
    op.create_check_constraint(
        "projects_workflow_mode_valid",
        "projects",
        "workflow_mode IN ('quick_demo','full_simulation')",
    )
    op.create_check_constraint(
        "projects_demo_bundle_valid",
        "projects",
        "(workflow_mode = 'quick_demo' AND demo_bundle_id = 'registrasi-digital-umkm-v1') OR "
        "(workflow_mode = 'full_simulation' AND demo_bundle_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("projects_demo_bundle_valid", "projects", type_="check")
    op.drop_constraint("projects_workflow_mode_valid", "projects", type_="check")
    op.drop_column("projects", "demo_bundle_id")
    op.drop_column("projects", "workflow_mode")
