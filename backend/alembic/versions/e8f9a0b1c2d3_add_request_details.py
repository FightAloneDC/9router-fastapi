"""add request_details table

Revision ID: e8f9a0b1c2d3
Revises: d474b774ed85
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, Sequence[str], None] = 'd474b774ed85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'request_details',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=255), nullable=True),
        sa.Column('connection_id', sa.String(length=255), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='ok', nullable=False),
        sa.Column('latency_ttft', sa.Integer(), nullable=True),
        sa.Column('latency_total', sa.Integer(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), server_default='0'),
        sa.Column('cost', sa.Float(), server_default='0.0'),
        sa.Column('request', sa.Text(), nullable=True),
        sa.Column('provider_request', sa.Text(), nullable=True),
        sa.Column('provider_response', sa.Text(), nullable=True),
        sa.Column('response', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_request_details_provider', 'request_details', ['provider'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_request_details_provider', table_name='request_details')
    op.drop_table('request_details')
