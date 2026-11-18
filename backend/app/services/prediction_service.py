"""Prediction flow: check access -> resolve inputs -> predict -> risk -> SHAP -> recommendations
-> save -> return."""

from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.ml.features import ASSIGNMENT, ATTENDANCE, INTERNAL1, INTERNAL2, STAGE_FEATURES
from app.ml.model_loader import LoadedModel, ModelRegistry
from app.ml.predict import PredictionResult, predict
from app.ml.recommend import build as build_recommendations
from app.ml.risk import risk_level
from app.models import AcademicRecord, Attendance, Prediction, PredictionStage, Student, User, UserRole
from app.schemas.prediction_schema import PredictRequest, SimulateRequest

logger = logging.getLogger(__name__)

PREDICTION_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Prediction not found.")
STUDENT_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")


def require_model(registry: ModelRegistry, stage: PredictionStage) -> LoadedModel:
    model = registry.get(stage.value)
    if model is None:
        raise AppError(503, "model_unavailable",
                       f"The {stage.value} prediction model is not available. Please try again later.",
                       details={"reason": registry.errors.get(stage.value, "not loaded")})
    return model


def accessible_student(db: Session, user: User, student_id: int) -> Student:
    """Staff may access any student; a student only their own record (others look like 404)."""
    if user.role is UserRole.STUDENT and (user.student is None or user.student.id != student_id):
        raise STUDENT_NOT_FOUND
    student = db.get(Student, student_id)
    if student is None:
        raise STUDENT_NOT_FOUND
    return student


def _percent(obtained: Decimal | None, maximum: Decimal | None) -> float | None:
    if obtained is None or maximum is None:
        return None
    return float(obtained) / float(maximum) * 100


def inputs_from_records(db: Session, student: Student, semester: int, stage: PredictionStage) -> dict[str, float]:
    """Average each assessment's percentage across the semester's subjects (every subject must
    have the assessment), plus the semester attendance."""
    records = db.scalars(select(AcademicRecord).where(
        AcademicRecord.student_id == student.id, AcademicRecord.semester == semester)).all()
    attendance = db.scalar(select(Attendance).where(
        Attendance.student_id == student.id, Attendance.semester == semester))
    needed = {INTERNAL1: "internal1", ASSIGNMENT: "assignment"}
    if stage is PredictionStage.STAGE2:
        needed[INTERNAL2] = "internal2"

    missing: list[str] = []
    if attendance is None:
        missing.append("attendance")
    if not records:
        missing.append("academic records")
    values: dict[str, float] = {}
    for feature, prefix in needed.items():
        percents = [_percent(getattr(r, f"{prefix}_obtained"), getattr(r, f"{prefix}_maximum")) for r in records]
        incomplete = [r.subject_name for r, p in zip(records, percents) if p is None]
        if incomplete:
            missing.append(f"{prefix} for {', '.join(sorted(incomplete))}")
        elif records:
            values[feature] = round(sum(percents) / len(percents), 2)
    if missing:
        raise AppError(422, "insufficient_data",
                       f"{stage.value} prediction needs data that is missing for semester {semester}.",
                       details={"missing": missing})
    values[ATTENDANCE] = float(attendance.attendance_percentage)
    return {f: values[f] for f in STAGE_FEATURES[stage.value]}


def explain_and_recommend(model: LoadedModel, stage: PredictionStage, values: dict[str, float],
                          result: PredictionResult) -> tuple[dict | None, dict | None]:
    """SHAP explanation + recommendations. If the explainer is unavailable the prediction is still
    returned, with a warning instead of an explanation."""
    if model.explainer is None:
        result.warnings.append("An explanation is not available for this prediction "
                               f"({model.explainer_error or 'explainer not loaded'}).")
        return None, None
    explanation = model.explainer.explain(values)
    recommendations = build_recommendations(
        model, stage.value, values, explanation, result.predicted, risk_level(result.predicted),
        (result.interval_low, result.interval_high))
    return explanation, recommendations


def create_prediction(db: Session, registry: ModelRegistry, user: User, request: PredictRequest) -> Prediction:
    student = accessible_student(db, user, request.student_id)
    if user.role is UserRole.STUDENT and request.inputs is not None:
        # Students may predict from their stored records, or use /simulate for what-ifs;
        # self-entered marks are never saved into the official history.
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Students can predict only from stored records; use /api/predictions/simulate for what-if inputs.")
    model = require_model(registry, request.stage)
    semester = request.semester or student.semester
    if request.inputs is not None:
        source, values = "manual", request.inputs.as_features()
    else:
        source, values = "records", inputs_from_records(db, student, semester, request.stage)

    result: PredictionResult = predict(model, request.stage.value, values)
    explanation, recommendations = explain_and_recommend(model, request.stage, values, result)
    row = Prediction(
        student_id=student.id,
        semester=semester,
        stage=request.stage,
        inputs={
            "source": source,
            "values": values,
            "raw_prediction": result.raw_prediction,
            "interval": {"low": result.interval_low, "high": result.interval_high},
            "warnings": result.warnings,
        },
        predicted_marks=Decimal(str(result.predicted)),
        risk_level=risk_level(result.predicted),
        shap_explanation=explanation,
        recommendations=recommendations,
        model_version=model.metadata["model_version"],
        created_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("Prediction saved", extra={"prediction_id": row.id, "student_id": student.id,
                                           "stage": request.stage.value, "risk": row.risk_level.value})
    return row


def simulate(registry: ModelRegistry, request: SimulateRequest
             ) -> tuple[LoadedModel, dict[str, float], PredictionResult, dict | None, dict | None]:
    model = require_model(registry, request.stage)
    values = request.inputs.as_features()
    result = predict(model, request.stage.value, values)
    explanation, recommendations = explain_and_recommend(model, request.stage, values, result)
    return model, values, result, explanation, recommendations


def history(db: Session, user: User, student_id: int) -> list[Prediction]:
    accessible_student(db, user, student_id)
    return list(db.scalars(select(Prediction).where(Prediction.student_id == student_id)
                           .order_by(Prediction.created_at.desc(), Prediction.id.desc())).all())


def get_prediction(db: Session, user: User, prediction_id: int) -> Prediction:
    row = db.get(Prediction, prediction_id)
    if row is None:
        raise PREDICTION_NOT_FOUND
    if user.role is UserRole.STUDENT and (user.student is None or user.student.id != row.student_id):
        raise PREDICTION_NOT_FOUND
    return row
