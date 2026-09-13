"""SQLAlchemy ORM model for persisted file metadata.

See docs/design/db.md for the schema and the rationale for keeping this
separate from the API's Pydantic request/response models.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class File(Base):
    """One row per uploaded audio file, keyed by its stored object name."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    duration_seconds: Mapped[float] = mapped_column(Float)
    sample_rate: Mapped[int] = mapped_column(Integer)
    channels: Mapped[int] = mapped_column(Integer)
    bit_depth: Mapped[int] = mapped_column(Integer)
    codec: Mapped[str] = mapped_column(String)
    sample_format: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
