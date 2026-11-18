"""Academic data, targets, benchmarks, monitoring and the faculty overview."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, StaffUser
from app.database.connection import get_db
from app.schemas.academic_schema import (
    AcademicDataIn,
    AcademicDataOut,
    BenchmarkIn,
    BenchmarkOut,
    FacultyOverview,
    MonitoringIn,
    MonitoringOut,
    TargetIn,
    TargetOut,
)
from app.schemas.common import Department
from app.services import academic_service

router = APIRouter(prefix="/api", tags=["academic"])

DB = Annotated[Session, Depends(get_db)]
SemesterQ = Annotated[int | None, Query(ge=1, le=12, description="Defaults to the student's current semester")]


@router.get("/students/{student_id}/academic", response_model=AcademicDataOut,
            summary="Subject marks and attendance for a semester")
def get_academic(student_id: int, db: DB, user: CurrentUser, semester: SemesterQ = None) -> AcademicDataOut:
    return academic_service.get_academic(db, user, student_id, semester)


@router.put("/students/{student_id}/academic", response_model=AcademicDataOut,
            summary="Replace a semester's subject marks and attendance (faculty/admin)")
def put_academic(student_id: int, data: AcademicDataIn, db: DB, user: StaffUser) -> AcademicDataOut:
    return academic_service.put_academic(db, user, student_id, data)


@router.get("/students/{student_id}/target", response_model=TargetOut, summary="A student's personal target")
def get_target(student_id: int, db: DB, user: CurrentUser, semester: SemesterQ = None) -> TargetOut:
    return academic_service.get_target(db, user, student_id, semester)


@router.put("/students/{student_id}/target", response_model=TargetOut, summary="Set your own target (students)")
def put_target(student_id: int, data: TargetIn, db: DB, user: CurrentUser) -> TargetOut:
    return academic_service.put_target(db, user, student_id, data)


@router.get("/benchmarks", response_model=BenchmarkOut, summary="Class benchmark for a department and semester")
def get_benchmark(department: Annotated[Department, Query()], semester: Annotated[int, Query(ge=1, le=12)],
                  db: DB, _: CurrentUser) -> BenchmarkOut:
    return academic_service.get_benchmark(db, department, semester)


@router.put("/benchmarks", response_model=BenchmarkOut, summary="Set the class benchmark (faculty/admin)")
def put_benchmark(data: BenchmarkIn, db: DB, user: StaffUser) -> BenchmarkOut:
    return academic_service.put_benchmark(db, user, data)


@router.get("/students/{student_id}/monitoring", response_model=MonitoringOut, summary="Faculty follow-up status")
def get_monitoring(student_id: int, db: DB, user: StaffUser, semester: SemesterQ = None) -> MonitoringOut:
    return academic_service.get_monitoring(db, user, student_id, semester)


@router.put("/students/{student_id}/monitoring", response_model=MonitoringOut, summary="Update follow-up status")
def put_monitoring(student_id: int, data: MonitoringIn, db: DB, user: StaffUser) -> MonitoringOut:
    return academic_service.put_monitoring(db, user, student_id, data)


@router.get("/faculty/overview", response_model=FacultyOverview,
            summary="Cohort overview: latest predictions, risk counts, distribution, benchmark")
def faculty_overview(db: DB, _: StaffUser,
                     department: Annotated[str | None, Query(max_length=120)] = None,
                     semester: Annotated[int | None, Query(ge=1, le=12)] = None) -> FacultyOverview:
    return academic_service.overview(db, department, semester)
