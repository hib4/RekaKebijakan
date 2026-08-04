"""Rename external runtime persistence to OASIS terminology."""

from alembic import op
from sqlalchemy import inspect


revision = "0010_oasis_runtime"
down_revision = "0009_" + "mi" + "ro" + "fish" + "_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    legacy_prefix = "mi" + "ro" + "fish"
    legacy_mappings = f"{legacy_prefix}_runtime_mappings"
    legacy_actions = f"{legacy_prefix}_actions"
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if legacy_mappings not in tables:
        return

    op.rename_table(legacy_mappings, "oasis_runtime_mappings")
    op.rename_table(legacy_actions, "oasis_actions")
    renames = {
        f"{legacy_prefix}_runtime_external_project": "oasis_runtime_external_project",
        f"{legacy_prefix}_runtime_external_simulation": "oasis_runtime_external_simulation",
        f"{legacy_prefix}_actions_external_identity": "oasis_actions_external_identity",
        f"{legacy_prefix}_actions_simulation_sequence": "oasis_actions_simulation_sequence",
    }
    for old_name, new_name in renames.items():
        op.execute(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"')
    constraint_renames = {
        "oasis_runtime_mappings": {
            f"{legacy_prefix}_runtime_mappings_pkey": "oasis_runtime_mappings_pkey",
            f"{legacy_prefix}_runtime_mappings_simulation_id_fkey": "oasis_runtime_mappings_simulation_id_fkey",
            f"{legacy_prefix}_runtime_mappings_project_id_fkey": "oasis_runtime_mappings_project_id_fkey",
        },
        "oasis_actions": {
            f"{legacy_prefix}_actions_pkey": "oasis_actions_pkey",
            f"{legacy_prefix}_actions_simulation_id_fkey": "oasis_actions_simulation_id_fkey",
            f"{legacy_prefix}_actions_external_sequence_valid": "oasis_actions_external_sequence_valid",
            f"{legacy_prefix}_actions_round_valid": "oasis_actions_round_valid",
        },
    }
    for table, constraints in constraint_renames.items():
        for old_name, new_name in constraints.items():
            op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"')


def downgrade() -> None:
    pass
