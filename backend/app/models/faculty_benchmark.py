"""faculty_benchmarks: the minimum expected performance per department and semester."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Percent, TimestampMixin


class FacultyBenchmark(TimestampMixin, Base):
    __tablename__ = "faculty_benchmarks"
    __table_args__ = (
        UniqueConstraint("department", "semester"),
        CheckConstraint("semester BETWEEN 1 AND 12", name="semester_range"),
        CheckConstraint("benchmark_percentage BETWEEN 0 AND 100", name="benchmark_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    benchmark_percentage: Mapped[Decimal] = mapped_column(Percent, nullable=False)
    # Keep the benchmark if the faculty account is removed.
    set_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
