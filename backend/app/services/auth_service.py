"""Registration and login logic (no HTTP details beyond raising HTTPException)."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import Student, User, UserRole
from app.schemas.user_schema import RegisterRequest, UserOut

logger = logging.getLogger(__name__)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def register_student(db: Session, data: RegisterRequest) -> User:
    """Create a student login. If faculty already created this roll number, link to it,
    but only when the email matches the record (so nobody can claim another student's data)."""
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise _conflict("An account with this email already exists.")

    student = db.scalar(select(Student).where(Student.roll_number == data.roll_number))
    if student is not None:
        if student.user_id is not None:
            raise _conflict("This roll number already has an account.")
        if student.email != data.email:
            raise _conflict("Roll number and email do not match the student record.")
    else:
        if db.scalar(select(Student.id).where(Student.email == data.email)):
            raise _conflict("Roll number and email do not match the student record.")
        student = Student(
            roll_number=data.roll_number,
            name=data.name,
            email=data.email,
            department=data.department,
            semester=data.semester,
        )
        db.add(student)

    user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.STUDENT,
        department=data.department,
    )
    student.user = user
    try:
        db.commit()
    except IntegrityError:  # lost a race with a concurrent registration
        db.rollback()
        raise _conflict("An account with these details already exists.") from None
    db.refresh(user)
    logger.info("Student registered", extra={"user_id": user.id, "student_id": student.id})
    return user


def authenticate(db: Session, identifier: str, password: str) -> User | None:
    """Look up by email, staff employee ID or student roll number; verify the password."""
    identifier = identifier.strip()
    if "@" in identifier:
        user = db.scalar(select(User).where(User.email == identifier.lower()))
    else:
        code = identifier.upper()
        user = db.scalar(select(User).where(User.employee_id == code)) or db.scalar(
            select(User).join(Student, Student.user_id == User.id).where(Student.roll_number == code)
        )
    # Always run a hash verification so timing doesn't reveal whether the account exists.
    if not verify_password(password, user.hashed_password if user else None):
        return None
    if not user.is_active:
        return None
    return user


def to_user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    if user.student is not None:
        out.student_id = user.student.id
        out.roll_number = user.student.roll_number
    return out
