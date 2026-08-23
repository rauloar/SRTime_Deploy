"""Add persistent raw-log pull schedule to device terminals.

Revision ID: f6a7b8c9d001
Revises: d5b8fae32002
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d001"
down_revision: Union[str, Sequence[str], None] = "d5b8fae32002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("device_terminal", sa.Column("pull_schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("device_terminal", sa.Column("pull_interval_minutes", sa.Integer(), nullable=True))
    op.add_column("device_terminal", sa.Column("pull_window_start", sa.Time(), nullable=True))
    op.add_column("device_terminal", sa.Column("pull_window_end", sa.Time(), nullable=True))
    op.add_column("device_terminal", sa.Column("next_pull_at", sa.DateTime(), nullable=True))
    op.add_column("device_terminal", sa.Column("last_pull_status", sa.String(length=20), nullable=True))
    op.add_column("device_terminal", sa.Column("last_pull_error", sa.String(length=500), nullable=True))


def downgrade() -> None:
    for column in ("last_pull_error", "last_pull_status", "next_pull_at", "pull_window_end", "pull_window_start", "pull_interval_minutes", "pull_schedule_enabled"):
        op.drop_column("device_terminal", column)
