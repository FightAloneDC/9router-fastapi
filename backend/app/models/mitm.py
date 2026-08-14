"""MITM proxy configuration and log models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MitmConfig(Base):
    """Singleton row (id=1) storing MITM proxy configuration."""

    __tablename__ = "mitm_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=443, nullable=False)
    router_base_url: Mapped[str] = mapped_column(
        String(500), default="http://127.0.0.1:8013", nullable=False
    )
    cert_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    sudo_password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    tools_config: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<MitmConfig enabled={self.enabled}>"


class MitmLog(Base):
    """Individual MITM proxy request/response log entry."""

    __tablename__ = "mitm_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headers: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    body_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<MitmLog tool={self.tool} direction={self.direction}>"
