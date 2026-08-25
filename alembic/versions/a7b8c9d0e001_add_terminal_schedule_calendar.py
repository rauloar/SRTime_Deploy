"""Add calendar and weekday scheduling options for terminal pulls.

Revision ID: a7b8c9d0e001
Revises: f6a7b8c9d001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e001"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("device_terminal", sa.Column("pull_schedule_mode", sa.String(length=20), nullable=False, server_default="interval"))
    op.add_column("device_terminal", sa.Column("pull_schedule_weekdays", sa.JSON(), nullable=True))
    op.add_column("device_terminal", sa.Column("pull_schedule_time", sa.Time(), nullable=True))
    op.add_column("device_terminal", sa.Column("pull_schedule_start_date", sa.Date(), nullable=True))
    op.add_column("device_terminal", sa.Column("pull_schedule_end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    for column in ("pull_schedule_end_date", "pull_schedule_start_date", "pull_schedule_time", "pull_schedule_weekdays", "pull_schedule_mode"):
        op.drop_column("device_terminal", column)
