"""/api/students: CRUD for faculty/admin; a student may read only their own record."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, StaffUser
from app.database.connection import get_db
from app.models import UserRole
from app.schemas.student_schema import StudentCreate, StudentList, StudentOut, StudentUpdate
from app.services import student_service

router = APIRouter(prefix="/api/students", tags=["students"])

DB = Annotated[Session, Depends(get_db)]


@router.post("/", response_model=StudentOut, status_code=status.HTTP_201_CREATED, summary="Create a student")
def create_student(data: StudentCreate, db: DB, _: StaffUser) -> StudentOut:
    return StudentOut.model_validate(student_service.create_student(db, data))


@router.get("/", response_model=StudentList, summary="List students (search, filter, paginate)")
def list_students(
    db: DB,
    _: StaffUser,
    search: Annotated[str | None, Query(max_length=100, description="Matches name, roll number or email")] = None,
    department: Annotated[str | None, Query(max_length=120)] = None,
    semester: Annotated[int | None, Query(ge=1, le=12)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StudentList:
    items, total = student_service.list_students(
        db, search=search, department=department, semester=semester, limit=limit, offset=offset
    )
    return StudentList(items=[StudentOut.model_validate(s) for s in items], total=total, limit=limit, offset=offset)


@router.get("/me", response_model=StudentOut, summary="The signed-in student's own record")
def my_student_record(user: CurrentUser) -> StudentOut:
    if user.role is not UserRole.STUDENT or user.student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No student record is linked to this account.")
    return StudentOut.model_validate(user.student)


@router.get("/{student_id}", response_model=StudentOut, summary="Get one student")
def get_student(student_id: int, db: DB, user: CurrentUser) -> StudentOut:
    if user.role is UserRole.STUDENT:
        own = user.student
        if own is None or own.id != student_id:
            # 404 rather than 403 so students can't probe which IDs exist.
            raise student_service.NOT_FOUND
    return StudentOut.model_validate(student_service.get_student(db, student_id))


@router.put("/{student_id}", response_model=StudentOut, summary="Update a student")
def update_student(student_id: int, data: StudentUpdate, db: DB, _: StaffUser) -> StudentOut:
    return StudentOut.model_validate(student_service.update_student(db, student_id, data))


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a student and all their records")
def delete_student(student_id: int, db: DB, _: StaffUser) -> Response:
    student_service.delete_student(db, student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
