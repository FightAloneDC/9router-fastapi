"""DB override for the public model prefix (config.ALIAS fallback)."""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProviderAlias(Base):
    """One prefix override per provider id.

    Missing row → use config.ALIAS.
    """

    __tablename__ = "provider_aliases"
    __table_args__ = (
        UniqueConstraint("alias", name="uq_provider_aliases_alias"),
    )

    provider: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    alias: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
