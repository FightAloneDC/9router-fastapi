"""Settings and Key-Value store models."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, PrimaryKeyConstraint, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SettingsModel(Base):
    """Singleton settings row (id is always 1). Stores JSON as TEXT."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
    )
    data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
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
        return "<Settings row>"


class KV(Base):
    """Generic key-value store scoped by a scope string."""

    __tablename__ = "kv"

    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (
        PrimaryKeyConstraint("scope", "key", name="pk_kv"),
    )

    def __repr__(self) -> str:
        return f"<KV {self.scope}/{self.key}>"
