"""add default proxy usage to proxy pools

Revision ID: c7d8e9f0a1b2
Revises: 9a3d69805d5d
Create Date: 2026-08-12 11:44:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "9a3d69805d5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a nullable default proxy usage template."""
    op.add_column(
        "proxy_pools",
        sa.Column("default_proxy_usage", JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove the default proxy usage template."""
    op.drop_column("proxy_pools", "default_proxy_usage")
