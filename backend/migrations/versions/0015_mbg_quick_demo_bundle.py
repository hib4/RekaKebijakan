"""Replace quick demo bundle with MBG."""

from alembic import op


revision = "0015_mbg_quick_demo_bundle"
down_revision = "0014_quick_demo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("projects_demo_bundle_valid", "projects", type_="check")
    op.execute(
        "UPDATE projects SET demo_bundle_id = 'makan-bergizi-gratis-v1' "
        "WHERE workflow_mode = 'quick_demo' AND demo_bundle_id = 'registrasi-digital-umkm-v1'"
    )
    op.create_check_constraint(
        "projects_demo_bundle_valid",
        "projects",
        "(workflow_mode = 'quick_demo' AND demo_bundle_id = 'makan-bergizi-gratis-v1') OR "
        "(workflow_mode = 'full_simulation' AND demo_bundle_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("projects_demo_bundle_valid", "projects", type_="check")
    op.execute(
        "UPDATE projects SET demo_bundle_id = 'registrasi-digital-umkm-v1' "
        "WHERE workflow_mode = 'quick_demo' AND demo_bundle_id = 'makan-bergizi-gratis-v1'"
    )
    op.create_check_constraint(
        "projects_demo_bundle_valid",
        "projects",
        "(workflow_mode = 'quick_demo' AND demo_bundle_id = 'registrasi-digital-umkm-v1') OR "
        "(workflow_mode = 'full_simulation' AND demo_bundle_id IS NULL)",
    )
