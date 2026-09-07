"""add employee groups

Revision ID: c9d0e1f2a304
Revises: b8c1d2e3f401
Create Date: 2026-09-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a304"
down_revision: Union[str, None] = "b8c1d2e3f401"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("shift_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.add_column("users", sa.Column("group_id", sa.Integer(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "shift_assignment_source",
            sa.String(length=20),
            server_default="MANUAL",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_users_group_id_employee_group",
        "users",
        "employee_group",
        ["group_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_users_shift_assignment_source_valid",
        "users",
        "shift_assignment_source IN ('MANUAL', 'GROUP')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_shift_assignment_source_valid", "users", type_="check")
    op.drop_constraint("fk_users_group_id_employee_group", "users", type_="foreignkey")
    op.drop_column("users", "shift_assignment_source")
    op.drop_column("users", "group_id")
    op.drop_table("employee_group")
