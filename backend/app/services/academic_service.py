"""Academic records, attendance, targets, benchmarks, monitoring and the faculty overview."""

from __future__ import annotations

import logging
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AcademicRecord,
    Attendance,
    FacultyBenchmark,
    Monitoring,
    MonitoringStatus,
    Prediction,
    Student,
    StudentTarget,
    User,
    UserRole,
)
from app.schemas.academic_schema import (
    AcademicDataIn,
    AcademicDataOut,
    BenchmarkIn,
    BenchmarkOut,
    FacultyOverview,
    LatestPrediction,
    Mark,
    MarkOut,
    MonitoringIn,
    MonitoringOut,
    OverviewStudent,
    SubjectRecordOut,
    TargetIn,
    TargetOut,
)
from app.services.prediction_service import accessible_student

logger = logging.getLogger(__name__)

ASSESSMENTS = ("internal1", "internal2", "assignment")
OVERVIEW_LIMIT = 1000
DISTRIBUTION = [("Below 50", 0, 50), ("50–59", 50, 60), ("60–69", 60, 70), ("70–79", 70, 80), ("80+", 80, 101)]


def _mark(record: AcademicRecord, prefix: str) -> MarkOut | None:
    obtained, maximum = getattr(record, f"{prefix}_obtained"), getattr(record, f"{prefix}_maximum")
    return None if obtained is None else MarkOut(obtained=obtained, maximum=maximum)


# --- academic records + attendance ------------------------------------------------------------

def get_academic(db: Session, user: User, student_id: int, semester: int | None) -> AcademicDataOut:
    student = accessible_student(db, user, student_id)
    semester = semester or student.semester
    records = db.scalars(select(AcademicRecord).where(
        AcademicRecord.student_id == student.id, AcademicRecord.semester == semester
    ).order_by(AcademicRecord.subject_name)).all()
    attendance = db.scalar(select(Attendance.attendance_percentage).where(
        Attendance.student_id == student.id, Attendance.semester == semester))
    return AcademicDataOut(
        student_id=student.id, semester=semester, attendance_percentage=attendance,
        records=[SubjectRecordOut(id=r.id, subject_name=r.subject_name,
                                  **{p: _mark(r, p) for p in ASSESSMENTS}) for r in records],
    )


def put_academic(db: Session, user: User, student_id: int, data: AcademicDataIn) -> AcademicDataOut:
    student = accessible_student(db, user, student_id)
    existing = {r.subject_name.casefold(): r for r in db.scalars(select(AcademicRecord).where(
        AcademicRecord.student_id == student.id, AcademicRecord.semester == data.semester))}
    keep: set[str] = set()
    for item in data.records:
        key = item.subject_name.casefold()
        keep.add(key)
        record = existing.get(key) or AcademicRecord(student_id=student.id, semester=data.semester)
        record.subject_name = item.subject_name
        for prefix in ASSESSMENTS:
            mark: Mark | None = getattr(item, prefix)
            setattr(record, f"{prefix}_obtained", mark.obtained if mark else None)
            setattr(record, f"{prefix}_maximum", mark.maximum if mark else None)
        db.add(record)
    for key, record in existing.items():
        if key not in keep:
            db.delete(record)

    attendance = db.scalar(select(Attendance).where(
        Attendance.student_id == student.id, Attendance.semester == data.semester))
    if data.attendance_percentage is None:
        if attendance is not None:
            db.delete(attendance)
    elif attendance is None:
        db.add(Attendance(student_id=student.id, semester=data.semester,
                          attendance_percentage=data.attendance_percentage))
    else:
        attendance.attendance_percentage = data.attendance_percentage
    db.commit()
    logger.info("Academic data saved", extra={"student_id": student.id, "semester": data.semester,
                                              "subjects": len(data.records)})
    return get_academic(db, user, student.id, data.semester)


# --- targets ----------------------------------------------------------------------------------

def get_target(db: Session, user: User, student_id: int, semester: int | None) -> TargetOut:
    student = accessible_student(db, user, student_id)
    semester = semester or student.semester
    value = db.scalar(select(StudentTarget.target_percentage).where(
        StudentTarget.student_id == student.id, StudentTarget.semester == semester))
    return TargetOut(student_id=student.id, semester=semester, target_percentage=value)


def put_target(db: Session, user: User, student_id: int, data: TargetIn) -> TargetOut:
    if user.role is not UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Targets are set by the student.")
    student = accessible_student(db, user, student_id)
    semester = data.semester or student.semester
    target = db.scalar(select(StudentTarget).where(
        StudentTarget.student_id == student.id, StudentTarget.semester == semester))
    if target is None:
        db.add(StudentTarget(student_id=student.id, semester=semester, target_percentage=data.target_percentage))
    else:
        target.target_percentage = data.target_percentage
    db.commit()
    return get_target(db, user, student.id, semester)


# --- benchmarks -------------------------------------------------------------------------------

def get_benchmark(db: Session, department: str, semester: int) -> BenchmarkOut:
    row = db.scalar(select(FacultyBenchmark).where(
        FacultyBenchmark.department == department, FacultyBenchmark.semester == semester))
    return BenchmarkOut(department=department, semester=semester,
                        benchmark_percentage=row.benchmark_percentage if row else None,
                        updated_at=row.updated_at if row else None)


def put_benchmark(db: Session, user: User, data: BenchmarkIn) -> BenchmarkOut:
    row = db.scalar(select(FacultyBenchmark).where(
        FacultyBenchmark.department == data.department, FacultyBenchmark.semester == data.semester))
    if row is None:
        row = FacultyBenchmark(department=data.department, semester=data.semester)
        db.add(row)
    row.benchmark_percentage = data.benchmark_percentage
    row.set_by_user_id = user.id
    db.commit()
    return get_benchmark(db, data.department, data.semester)


# --- monitoring -------------------------------------------------------------------------------

def get_monitoring(db: Session, user: User, student_id: int, semester: int | None) -> MonitoringOut:
    student = accessible_student(db, user, student_id)
    semester = semester or student.semester
    row = db.scalar(select(Monitoring).where(Monitoring.student_id == student.id, Monitoring.semester == semester))
    if row is None:
        return MonitoringOut(student_id=student.id, semester=semester,
                             status=MonitoringStatus.NOT_CONTACTED, notes=None)
    return MonitoringOut(student_id=student.id, semester=semester, status=row.status,
                         notes=row.notes, updated_at=row.updated_at)


def put_monitoring(db: Session, user: User, student_id: int, data: MonitoringIn) -> MonitoringOut:
    student = accessible_student(db, user, student_id)
    semester = data.semester or student.semester
    row = db.scalar(select(Monitoring).where(Monitoring.student_id == student.id, Monitoring.semester == semester))
    if row is None:
        row = Monitoring(student_id=student.id, semester=semester)
        db.add(row)
    row.status, row.notes, row.updated_by_user_id = data.status, data.notes or None, user.id
    db.commit()
    return get_monitoring(db, user, student.id, semester)


# --- faculty overview -------------------------------------------------------------------------

def overview(db: Session, department: str | None, semester: int | None) -> FacultyOverview:
    query = select(Student)
    if department:
        query = query.where(Student.department == department)
    if semester:
        query = query.where(Student.semester == semester)
    students = db.scalars(query.order_by(Student.roll_number).limit(OVERVIEW_LIMIT)).all()
    ids = [s.id for s in students]

    latest_ids = select(func.max(Prediction.id)).where(Prediction.student_id.in_(ids)).group_by(Prediction.student_id)
    latest = {p.student_id: p for p in db.scalars(select(Prediction).where(Prediction.id.in_(latest_ids)))} if ids else {}
    attendance = {(a.student_id, a.semester): a.attendance_percentage
                  for a in db.scalars(select(Attendance).where(Attendance.student_id.in_(ids)))} if ids else {}
    monitoring = {(m.student_id, m.semester): m
                  for m in db.scalars(select(Monitoring).where(Monitoring.student_id.in_(ids)))} if ids else {}

    benchmark = None
    if department and semester:
        benchmark = get_benchmark(db, department, semester).benchmark_percentage

    rows: list[OverviewStudent] = []
    for s in students:
        p = latest.get(s.id)
        m = monitoring.get((s.id, s.semester))
        rows.append(OverviewStudent(
            id=s.id, roll_number=s.roll_number, name=s.name, department=s.department, semester=s.semester,
            attendance_percentage=attendance.get((s.id, s.semester)),
            latest_prediction=LatestPrediction(id=p.id, stage=p.stage, predicted_marks=p.predicted_marks,
                                               risk_level=p.risk_level, created_at=p.created_at) if p else None,
            monitoring_status=m.status if m else None, monitoring_notes=m.notes if m else None,
        ))

    values = [float(r.latest_prediction.predicted_marks) for r in rows if r.latest_prediction]
    risk_counts = {level: sum(1 for r in rows if r.latest_prediction and r.latest_prediction.risk_level.value == level)
                   for level in ("high", "medium", "low")}
    return FacultyOverview(
        department=department, semester=semester, benchmark_percentage=benchmark,
        total_students=len(rows), with_prediction=len(values),
        below_benchmark=sum(1 for v in values if v < float(benchmark)) if benchmark is not None else None,
        risk_counts=risk_counts,
        distribution=[{"band": name, "count": sum(1 for v in values if low <= v < high)}
                      for name, low, high in DISTRIBUTION],
        average_prediction=round(sum(values) / len(values), 2) if values else None,
        students=rows,
    )

