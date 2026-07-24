"""Add storage quota and lifecycle lookup indexes."""

from alembic import op
import sqlalchemy as sa


revision = "0005_storage_lifecycle"
down_revision = "0004_normalized_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("documents_simulation_size", "documents", ["simulation_id", "size_bytes"])
    op.create_index(
        "projects_pending_delete_due", "projects", ["delete_after"],
        postgresql_where=sa.text("status = 'pending_delete' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("projects_pending_delete_due", table_name="projects")
    op.drop_index("documents_simulation_size", table_name="documents")
