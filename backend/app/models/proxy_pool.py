"""Proxy pool model for managing upstream proxy servers."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProxyPool(Base):
    """A proxy server configuration for routing outbound requests."""

    __tablename__ = "proxy_pools"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    proxy_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    no_proxy: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    pool_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="http",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    strict_proxy: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    test_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    def __repr__(self) -> str:
        return f"<ProxyPool {self.name} ({self.pool_type})>"
