"""provider_models catalog table

Revision ID: a9b0c1d2e3f4
Revises: c7d8e9f0a1b2
Create Date: 2026-08-15 05:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "provider", sa.String(100), nullable=False, index=True,
        ),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column(
            "type", sa.String(50), nullable=False, server_default="llm",
        ),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "provider",
            "model_id",
            name="uq_provider_models_provider_model",
        ),
    )
    # Backfill from connection JSON blobs + settings.disabledModels.
    conn = op.get_bind()
    conn.execute(sa.text(
        "CREATE EXTENSION IF NOT EXISTS pgcrypto"
    ))
    conn.execute(sa.text("""
        INSERT INTO provider_models (id, provider, model_id, type, name, enabled)
        SELECT
            gen_random_uuid(),
            provider,
            model_id,
            COALESCE(MAX(model_type), 'llm'),
            NULL,
            true
        FROM (
            SELECT
                c.provider,
                COALESCE(
                    m.elem ->> 'id',
                    CASE WHEN jsonb_typeof(m.elem) = 'string'
                         THEN m.elem #>> '{}' END
                ) AS model_id,
                COALESCE(m.elem ->> 'type', 'llm') AS model_type
            FROM provider_connections c
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE
                    WHEN c.data::jsonb -> 'models' IS NULL THEN '[]'::jsonb
                    WHEN jsonb_typeof(c.data::jsonb -> 'models') = 'array'
                        THEN c.data::jsonb -> 'models'
                    ELSE '[]'::jsonb
                END
            ) AS m(elem)
        ) parsed
        WHERE model_id IS NOT NULL AND model_id <> ''
        GROUP BY provider, model_id
        ON CONFLICT (provider, model_id) DO NOTHING
    """))


def downgrade() -> None:
    op.drop_table("provider_models")
