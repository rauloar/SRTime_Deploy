"""Add terminal privilege to employees.

Revision ID: b8c1d2e3f401
Revises: a7b8c9d0e001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c1d2e3f401"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("terminal_privilege", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_users_terminal_privilege_valid",
        "users",
        "terminal_privilege IN (0, 14)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_terminal_privilege_valid", "users", type_="check")
    op.drop_column("users", "terminal_privilege")
