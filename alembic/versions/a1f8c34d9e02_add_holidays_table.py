"""Add holidays table

Revision ID: a1f8c34d9e02
Revises: 992f3e7cd3a4
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1f8c34d9e02'
down_revision: Union[str, Sequence[str], None] = '992f3e7cd3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'holidays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('is_recurring', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date'),
    )


def downgrade() -> None:
    op.drop_table('holidays')
