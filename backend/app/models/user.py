"""users: login accounts (admin, faculty, student). Passwords are stored only as Argon2 hashes."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.student import Student


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    FACULTY = "faculty"
    STUDENT = "student"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("CHAR_LENGTH(TRIM(name)) > 0", name="name_not_blank"),
        CheckConstraint("CHAR_LENGTH(hashed_password) >= 20", name="password_is_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole, "user_role"), nullable=False, index=True)
    # Faculty/admin staff ID; students sign in with their roll number via the students table.
    employee_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    department: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    student: Mapped[Student | None] = relationship(back_populates="user", uselist=False)
