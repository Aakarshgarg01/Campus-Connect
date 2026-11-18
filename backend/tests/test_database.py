"""Phase 4 tests against a real MySQL test database (TEST_DATABASE_URL).

The schema is built with the real Alembic migrations, then every test runs inside a
transaction that is rolled back, so tests never see each other's rows.
Skipped (not failed) when TEST_DATABASE_URL is not configured.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, StatementError
from sqlalchemy.orm import Session

from tests.conftest import BACKEND_ROOT
from app.models import (
    AcademicRecord,
    Attendance,
    Base,
    Monitoring,
    Prediction,
    PredictionStage,
    RiskLevel,
    Student,
    User,
    UserRole,
)

MYSQL_CHECK_VIOLATION = 3819


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


def _user(email: str = "teacher@example.edu", role: UserRole = UserRole.FACULTY) -> User:
    return User(name="Test User", email=email, hashed_password="$argon2id$" + "x" * 40, role=role)


def _student(roll: str = "CS001", email: str = "s1@example.edu", semester: int = 7, **kw) -> Student:
    return Student(roll_number=roll, name="Test Student", email=email, department="CS", semester=semester, **kw)


def _assert_check_violation(db: Session, obj: object) -> None:
    db.add(obj)
    with pytest.raises(DBAPIError) as info:
        db.flush()
    assert info.value.orig.args[0] == MYSQL_CHECK_VIOLATION, info.value.orig
    db.rollback()


# --- connectivity and schema -------------------------------------------------------------

def test_connects_to_mysql_8(db: Session):
    version = db.execute(text("SELECT VERSION()")).scalar_one()
    assert version.startswith("8."), version


def test_migrations_at_head_and_match_models(engine: Engine):
    head = ScriptDirectory.from_config(Config(str(BACKEND_ROOT / "alembic.ini"))).get_current_head()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == head
        assert compare_metadata(context, Base.metadata) == []  # no drift between models and DB


def test_all_tables_use_innodb_utf8mb4(db: Session):
    rows = db.execute(text(
        "SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME <> 'alembic_version'"
    )).all()
    assert {r.TABLE_NAME for r in rows} == set(Base.metadata.tables)
    assert all(r.ENGINE == "InnoDB" and r.TABLE_COLLATION.startswith("utf8mb4") for r in rows)


# --- constraints -------------------------------------------------------------------------

def test_user_email_unique(db: Session):
    db.add(_user("dup@example.edu"))
    db.flush()
    db.add(_user("dup@example.edu"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_student_roll_number_unique(db: Session):
    db.add(_student("CS100", "a@example.edu"))
    db.flush()
    db.add(_student("CS100", "b@example.edu"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_semester_range_enforced(db: Session):
    _assert_check_violation(db, _student(semester=13))


def test_attendance_range_enforced(db: Session):
    student = _student()
    db.add(student)
    db.flush()
    _assert_check_violation(db, Attendance(student_id=student.id, semester=7, attendance_percentage=Decimal("100.5")))


def test_marks_cannot_exceed_maximum(db: Session):
    student = _student()
    db.add(student)
    db.flush()
    _assert_check_violation(db, AcademicRecord(
        student_id=student.id, semester=7, subject_name="Networks",
        internal1_obtained=Decimal("41"), internal1_maximum=Decimal("40"),
    ))


def test_assessment_pair_must_be_complete(db: Session):
    student = _student()
    db.add(student)
    db.flush()
    _assert_check_violation(db, AcademicRecord(
        student_id=student.id, semester=7, subject_name="Networks", internal1_obtained=Decimal("30"),
    ))


def test_internal2_may_be_missing_until_uploaded(db: Session):
    student = _student()
    db.add(student)
    db.flush()
    db.add(AcademicRecord(
        student_id=student.id, semester=7, subject_name="Networks",
        internal1_obtained=Decimal("30"), internal1_maximum=Decimal("40"),
        assignment_obtained=Decimal("8"), assignment_maximum=Decimal("10"),
    ))
    db.flush()


def test_predicted_marks_range_enforced(db: Session):
    student = _student()
    db.add(student)
    db.flush()
    _assert_check_violation(db, Prediction(
        student_id=student.id, semester=7, stage=PredictionStage.STAGE1, inputs={},
        predicted_marks=Decimal("150"), risk_level=RiskLevel.LOW, model_version="v",
    ))


def test_invalid_enum_value_rejected(db: Session):
    student = _student()
    db.add(student)
    db.flush()
    db.add(Monitoring(student_id=student.id, semester=7, status="Ignored"))
    with pytest.raises(StatementError):
        db.flush()


# --- relationships, cascades, JSON --------------------------------------------------------

def test_deleting_student_cascades_in_database(db: Session):
    student = _student()
    db.add(student)
    db.flush()
    db.add_all([
        Attendance(student_id=student.id, semester=7, attendance_percentage=Decimal("87.5")),
        Prediction(student_id=student.id, semester=7, stage=PredictionStage.STAGE2,
                   inputs={"attendance": 87.5}, predicted_marks=Decimal("71.25"),
                   risk_level=RiskLevel.MEDIUM, model_version="v"),
    ])
    db.flush()
    # Raw SQL delete: proves the database (not just the ORM) enforces ON DELETE CASCADE.
    db.execute(text("DELETE FROM students WHERE id = :id"), {"id": student.id})
    for table in ("attendance", "predictions"):
        count = db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE student_id = :id"), {"id": student.id})
        assert count.scalar_one() == 0


def test_deleting_user_keeps_student_and_unlinks(db: Session):
    user = _user("stu@example.edu", UserRole.STUDENT)
    student = _student(user=user)
    db.add(student)
    db.flush()
    db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db.expire_all()
    assert db.get(Student, student.id).user_id is None


def test_prediction_json_and_decimal_round_trip(db: Session):
    student = _student()
    db.add(student)
    db.flush()
    explanation = {"base_value": 64.86, "contributions": [{"feature": "attendance", "shap": -2.5}]}
    db.add(Prediction(student_id=student.id, semester=7, stage=PredictionStage.STAGE1,
                      inputs={"attendance": 80}, predicted_marks=Decimal("62.40"),
                      risk_level=RiskLevel.MEDIUM, shap_explanation=explanation, model_version="v1"))
    db.flush()
    db.expire_all()
    saved = db.scalars(select(Prediction).where(Prediction.student_id == student.id)).one()
    assert saved.shap_explanation == explanation
    assert saved.predicted_marks == Decimal("62.40")
    assert saved.stage is PredictionStage.STAGE1 and saved.created_at is not None


# --- app integration ---------------------------------------------------------------------

def test_get_db_closes_and_rolls_back(mysql_url: str, engine: Engine, monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings
    from app.database.connection import get_db, get_engine, get_session_factory

    monkeypatch.setenv("DATABASE_URL", mysql_url)
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    for cache in (get_settings, get_engine, get_session_factory):
        cache.cache_clear()
    try:
        dependency = get_db()
        session = next(dependency)
        session.add(_student("CS900", "rollback@example.edu"))
        session.flush()
        with pytest.raises(RuntimeError):
            dependency.throw(RuntimeError("request failed"))
        assert not session.in_transaction()  # rolled back and closed
        with engine.connect() as connection:
            leaked = connection.execute(text("SELECT COUNT(*) FROM students WHERE roll_number = 'CS900'"))
            assert leaked.scalar_one() == 0
    finally:
        get_engine().dispose()
        for cache in (get_settings, get_engine, get_session_factory):
            cache.cache_clear()


def test_health_reports_mysql_connected(make_client, mysql_url: str, model_dir):
    response = make_client(database_url=mysql_url, model_dir=model_dir).get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == {"connected": True}
