"""add mitm tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-18 00:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create mitm_config and mitm_logs tables."""
    op.create_table(
        'mitm_config',
        sa.Column('id', sa.Integer(), primary_key=True, default=1),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('port', sa.Integer(), nullable=False, server_default='443'),
        sa.Column('router_base_url', sa.String(500), nullable=False, server_default='http://localhost:20128'),
        sa.Column('cert_generated', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sudo_password_hash', sa.String(255), nullable=True),
        sa.Column('tools_config', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'mitm_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('tool', sa.String(100), nullable=False),
        sa.Column('direction', sa.String(20), nullable=False),
        sa.Column('method', sa.String(20), nullable=True),
        sa.Column('url', sa.String(2000), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('headers', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('body_preview', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
    )
    op.create_index('ix_mitm_logs_timestamp', 'mitm_logs', ['timestamp'])


def downgrade() -> None:
    """Drop MITM tables."""
    op.drop_index('ix_mitm_logs_timestamp', table_name='mitm_logs')
    op.drop_table('mitm_logs')
    op.drop_table('mitm_config')
