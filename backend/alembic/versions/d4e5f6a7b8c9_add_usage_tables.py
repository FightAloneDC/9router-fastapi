"""add usage tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-18 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create usage_history and usage_daily tables."""
    op.create_table(
        'usage_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('provider', sa.String(100), nullable=True, index=True),
        sa.Column('model', sa.String(255), nullable=True),
        sa.Column('connection_id', sa.String(255), nullable=True),
        sa.Column('api_key', sa.String(255), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost', sa.Float(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='ok'),
        sa.Column('tokens', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('meta', sa.Text(), nullable=False, server_default='{}'),
    )
    op.create_index('ix_usage_history_timestamp', 'usage_history', ['timestamp'])

    op.create_table(
        'usage_daily',
        sa.Column('date_key', sa.String(10), primary_key=True),
        sa.Column('data', sa.Text(), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    """Drop usage tables."""
    op.drop_table('usage_daily')
    op.drop_index('ix_usage_history_timestamp', table_name='usage_history')
    op.drop_table('usage_history')
