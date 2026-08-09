"""QuotaCache model — cached upstream quota balances."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class QuotaCache(Base):
    """Cached quota balance for a provider connection.

    Avoids re-polling the provider's usage API for idle
    connections (ban-risk reduction on farmed accounts).
    """

    __tablename__ = "quota_cache"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "provider_connections.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    plan: Mapped[str | None] = mapped_column(String(100))
    quotas: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
    )
    limit_reached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
