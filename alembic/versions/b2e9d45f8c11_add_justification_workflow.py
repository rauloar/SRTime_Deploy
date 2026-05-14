"""Add justification workflow fields to processed_attendance

Revision ID: b2e9d45f8c11
Revises: a1f8c34d9e02
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2e9d45f8c11'
down_revision: Union[str, Sequence[str], None] = 'a1f8c34d9e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('processed_attendance', sa.Column('previous_status', sa.String(20), nullable=True))
    op.add_column('processed_attendance', sa.Column('pending_first_in', sa.Time(), nullable=True))
    op.add_column('processed_attendance', sa.Column('pending_last_out', sa.Time(), nullable=True))
    op.add_column('processed_attendance', sa.Column('pending_justification', sa.String(), nullable=True))
    op.add_column('processed_attendance', sa.Column('requested_by', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('processed_attendance', 'requested_by')
    op.drop_column('processed_attendance', 'pending_justification')
    op.drop_column('processed_attendance', 'pending_last_out')
    op.drop_column('processed_attendance', 'pending_first_in')
    op.drop_column('processed_attendance', 'previous_status')
