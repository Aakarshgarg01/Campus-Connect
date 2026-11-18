"""student_targets: the final-performance percentage a student is aiming for, per semester."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Percent, TimestampMixin

if TYPE_CHECKING:
    from app.models.student import Student


class StudentTarget(TimestampMixin, Base):
    __tablename__ = "student_targets"
    __table_args__ = (
        UniqueConstraint("student_id", "semester"),
        CheckConstraint("semester BETWEEN 1 AND 12", name="semester_range"),
        CheckConstraint("target_percentage BETWEEN 1 AND 100", name="target_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_percentage: Mapped[Decimal] = mapped_column(Percent, nullable=False)

    student: Mapped[Student] = relationship(back_populates="targets")
