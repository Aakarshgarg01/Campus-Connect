"""Declarative base, shared column helpers and constraint naming convention."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, MetaData, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names so Alembic migrations are stable across databases.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    """Naive UTC timestamp (MySQL DATETIME has no time zone; we always store UTC)."""
    return datetime.now(UTC).replace(tzinfo=None)


# Percentages and marks: exact decimals, two places (e.g. 87.50).
Percent = Numeric(5, 2)
Marks = Numeric(6, 2)


def enum_column(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Store an Enum by its .value (human-readable) rather than its Python member name."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


__all__ = ["Base", "CreatedAtMixin", "Marks", "Percent", "TimestampMixin", "enum_column", "utcnow"]
