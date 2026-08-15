"""Provider-level model catalog (not per connection)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProviderModel(Base):
    """One model id in a provider catalog.

    Connections do not own this list. Fetch/Clear/Disable target
    these rows.
    """

    __tablename__ = "provider_models"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "model_id",
            name="uq_provider_models_provider_model",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="llm",
        server_default="llm",
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    custom: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
