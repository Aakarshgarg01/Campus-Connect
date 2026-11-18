"""attendance: overall attendance percentage per student and semester."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Percent, TimestampMixin

if TYPE_CHECKING:
    from app.models.student import Student


class Attendance(TimestampMixin, Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "semester"),
        CheckConstraint("semester BETWEEN 1 AND 12", name="semester_range"),
        CheckConstraint("attendance_percentage BETWEEN 0 AND 100", name="percentage_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    attendance_percentage: Mapped[Decimal] = mapped_column(Percent, nullable=False)

    student: Mapped[Student] = relationship(back_populates="attendance")
