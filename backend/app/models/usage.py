"""Usage analytics models: per-request history and daily aggregates."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UsageHistory(Base):
    """Individual API request usage record."""

    __tablename__ = "usage_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )
    provider: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connection_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    cost: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(50), default="ok", server_default="ok"
    )
    tokens: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    meta: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    def __repr__(self) -> str:
        return (
            f"<UsageHistory id={self.id} provider={self.provider} "
            f"model={self.model} cost={self.cost}>"
        )


class UsageDaily(Base):
    """Aggregated daily usage statistics stored as a JSON blob."""

    __tablename__ = "usage_daily"

    date_key: Mapped[str] = mapped_column(String(10), primary_key=True)
    data: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")

    def __repr__(self) -> str:
        return f"<UsageDaily date={self.date_key}>"
