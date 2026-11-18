"""Student CRUD logic."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Student
from app.schemas.student_schema import StudentCreate, StudentUpdate

logger = logging.getLogger(__name__)

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")


def _ensure_unique(db: Session, *, roll_number: str | None, email: str | None, exclude_id: int | None = None) -> None:
    for column, value, label in ((Student.roll_number, roll_number, "roll number"), (Student.email, email, "email")):
        if value is None:
            continue
        query = select(Student.id).where(column == value)
        if exclude_id is not None:
            query = query.where(Student.id != exclude_id)
        if db.scalar(query) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, f"A student with this {label} already exists.")


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:  # concurrent insert slipped past the pre-check
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A student with this roll number or email already exists.") from None


def list_students(
    db: Session,
    *,
    search: str | None,
    department: str | None,
    semester: int | None,
    limit: int,
    offset: int,
) -> tuple[list[Student], int]:
    conditions = []
    if search:
        term = search.strip()
        # contains(autoescape=True) treats % and _ in the search text literally;
        # the utf8mb4_0900_ai_ci collation makes the match case-insensitive.
        conditions.append(or_(*(column.contains(term, autoescape=True)
                                for column in (Student.name, Student.roll_number, Student.email))))
    if department:
        conditions.append(Student.department == department.strip())
    if semester is not None:
        conditions.append(Student.semester == semester)
    total = db.scalar(select(func.count()).select_from(Student).where(*conditions)) or 0
    rows = db.scalars(
        select(Student).where(*conditions).order_by(Student.roll_number).limit(limit).offset(offset)
    ).all()
    return list(rows), total


def get_student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise NOT_FOUND
    return student


def create_student(db: Session, data: StudentCreate) -> Student:
    _ensure_unique(db, roll_number=data.roll_number, email=data.email)
    student = Student(**data.model_dump())
    db.add(student)
    _commit(db)
    db.refresh(student)
    logger.info("Student created", extra={"student_id": student.id})
    return student


def update_student(db: Session, student_id: int, data: StudentUpdate) -> Student:
    student = get_student(db, student_id)
    changes = data.model_dump(exclude_unset=True)
    _ensure_unique(db, roll_number=changes.get("roll_number"), email=changes.get("email"), exclude_id=student.id)
    for field, value in changes.items():
        setattr(student, field, value)
    _commit(db)
    db.refresh(student)
    logger.info("Student updated", extra={"student_id": student.id, "fields": sorted(changes)})
    return student


def delete_student(db: Session, student_id: int) -> None:
    student = get_student(db, student_id)
    db.delete(student)  # DB cascades academic records, attendance, predictions, targets, monitoring
    db.commit()
    logger.info("Student deleted", extra={"student_id": student_id})
