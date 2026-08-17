"""backfill alims-intl models into provider_models

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-08-17 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "CREATE EXTENSION IF NOT EXISTS pgcrypto"
    ))
    conn.execute(sa.text("""
        INSERT INTO provider_models (
            id, provider, model_id, type, name, enabled
        )
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
                    WHEN c.data::jsonb -> 'models' IS NULL
                        THEN '[]'::jsonb
                    WHEN jsonb_typeof(
                        c.data::jsonb -> 'models'
                    ) = 'array'
                        THEN c.data::jsonb -> 'models'
                    ELSE '[]'::jsonb
                END
            ) AS m(elem)
            WHERE c.provider = 'alims-intl'
        ) parsed
        WHERE model_id IS NOT NULL AND model_id <> ''
        GROUP BY provider, model_id
        ON CONFLICT (provider, model_id) DO NOTHING
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM provider_models WHERE provider = 'alims-intl'"
    ))
