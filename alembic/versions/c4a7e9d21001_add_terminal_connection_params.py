"""Add generic terminal connection parameters.

Revision ID: c4a7e9d21001
Revises: b2e9d45f8c11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a7e9d21001"
down_revision: Union[str, Sequence[str], None] = "b2e9d45f8c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("device_terminal", sa.Column("connection_params", sa.JSON(), nullable=True))
    op.alter_column("device_terminal", "ip", existing_type=sa.String(length=45), nullable=True)
    # Versiones anteriores usaban una fila raw inválida para persistir la ruta
    # seleccionada por la UI. Sólo se elimina esa forma exacta de registro dummy.
    op.execute(
        "DELETE FROM attendance_log "
        "WHERE raw_identifier = '' AND date IS NULL AND time IS NULL AND mark_type IS NULL"
    )


def downgrade() -> None:
    op.alter_column("device_terminal", "ip", existing_type=sa.String(length=45), nullable=False)
    op.drop_column("device_terminal", "connection_params")
