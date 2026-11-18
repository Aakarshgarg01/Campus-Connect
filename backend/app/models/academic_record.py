"""academic_records: one row per student, semester and subject.

Each assessment is an (obtained, maximum) pair because maximum marks vary by subject.
Pairs are NULL until that assessment is uploaded (Internal 2 arrives after Internal 1).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Marks, TimestampMixin

if TYPE_CHECKING:
    from app.models.student import Student

ASSESSMENTS = ("internal1", "internal2", "assignment")


def _pair_checks(prefix: str) -> list[CheckConstraint]:
    obtained, maximum = f"{prefix}_obtained", f"{prefix}_maximum"
    return [
        CheckConstraint(
            f"({obtained} IS NULL AND {maximum} IS NULL) OR ({obtained} IS NOT NULL AND {maximum} IS NOT NULL)",
            name=f"{prefix}_pair_complete",
        ),
        CheckConstraint(
            f"{maximum} IS NULL OR ({maximum} > 0 AND {obtained} >= 0 AND {obtained} <= {maximum})",
            name=f"{prefix}_in_range",
        ),
    ]


class AcademicRecord(TimestampMixin, Base):
    __tablename__ = "academic_records"
    __table_args__ = (
        UniqueConstraint("student_id", "semester", "subject_name"),
        CheckConstraint("semester BETWEEN 1 AND 12", name="semester_range"),
        CheckConstraint("CHAR_LENGTH(TRIM(subject_name)) > 0", name="subject_not_blank"),
        *[check for prefix in ASSESSMENTS for check in _pair_checks(prefix)],
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    subject_name: Mapped[str] = mapped_column(String(120), nullable=False)
    internal1_obtained: Mapped[Decimal | None] = mapped_column(Marks)
    internal1_maximum: Mapped[Decimal | None] = mapped_column(Marks)
    internal2_obtained: Mapped[Decimal | None] = mapped_column(Marks)
    internal2_maximum: Mapped[Decimal | None] = mapped_column(Marks)
    assignment_obtained: Mapped[Decimal | None] = mapped_column(Marks)
    assignment_maximum: Mapped[Decimal | None] = mapped_column(Marks)

    student: Mapped[Student] = relationship(back_populates="academic_records")
