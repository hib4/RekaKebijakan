"""Add owner-scoped project creation idempotency keys."""

from alembic import op
import sqlalchemy as sa


revision = "0007_project_idempotency"
down_revision = "0006_scenario_persona_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_index(
        "projects_owner_idempotency_key",
        "projects",
        ["owner_user_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("projects_owner_idempotency_key", table_name="projects")
    op.drop_column("projects", "idempotency_key")
