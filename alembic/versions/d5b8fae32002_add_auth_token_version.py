"""Add token version for JWT revocation.

Revision ID: d5b8fae32002
Revises: c4a7e9d21001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5b8fae32002"
down_revision: Union[str, Sequence[str], None] = "c4a7e9d21001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "auth_user",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("auth_user", "token_version")
