"""monitoring: faculty follow-up status and notes for a student in a semester."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.student import Student


class MonitoringStatus(str, enum.Enum):
    NOT_CONTACTED = "Not Contacted"
    CONTACTED = "Contacted"
    COUNSELLING_DONE = "Counselling Done"
    UNDER_MONITORING = "Under Monitoring"
    IMPROVED = "Improved"


class Monitoring(TimestampMixin, Base):
    __tablename__ = "monitoring"
    __table_args__ = (
        UniqueConstraint("student_id", "semester"),
        CheckConstraint("semester BETWEEN 1 AND 12", name="semester_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[MonitoringStatus] = mapped_column(
        enum_column(MonitoringStatus, "monitoring_status"),
        nullable=False,
        default=MonitoringStatus.NOT_CONTACTED,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    student: Mapped[Student] = relationship(back_populates="monitoring")
