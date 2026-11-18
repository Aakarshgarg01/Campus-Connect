"""students: academic profile of a student, optionally linked to a login account.

Faculty can create a student before that student registers; registration later links
the account (users.id) to the existing roll number.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.academic_record import AcademicRecord
    from app.models.attendance import Attendance
    from app.models.monitoring import Monitoring
    from app.models.prediction import Prediction
    from app.models.student_target import StudentTarget
    from app.models.user import User


class Student(TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("semester BETWEEN 1 AND 12", name="semester_range"),
        CheckConstraint("CHAR_LENGTH(TRIM(name)) > 0", name="name_not_blank"),
        CheckConstraint("CHAR_LENGTH(TRIM(roll_number)) > 0", name="roll_number_not_blank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    roll_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    @property
    def has_account(self) -> bool:
        return self.user_id is not None

    user: Mapped[User | None] = relationship(back_populates="student")
    academic_records: Mapped[list[AcademicRecord]] = relationship(
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )
    attendance: Mapped[list[Attendance]] = relationship(
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )
    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Prediction.created_at",
    )
    targets: Mapped[list[StudentTarget]] = relationship(
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )
    monitoring: Mapped[list[Monitoring]] = relationship(
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )
