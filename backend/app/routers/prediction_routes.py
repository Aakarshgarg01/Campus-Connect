"""/api/predictions and /api/model-info."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import CurrentUser
from app.database.connection import get_db
from app.ml.model_loader import STAGES, ModelRegistry
from app.ml.risk import risk_level, thresholds
from app.schemas.prediction_schema import (
    FeatureImportance,
    Interval,
    ModelInfo,
    ModelStageInfo,
    PredictionHistory,
    PredictionOut,
    PredictRequest,
    SimulateRequest,
    SimulationOut,
    StageImportance,
)
from app.models import PredictionStage
from app.services import prediction_service

router = APIRouter(prefix="/api/predictions", tags=["predictions"])
info_router = APIRouter(prefix="/api", tags=["model"])

DB = Annotated[Session, Depends(get_db)]


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.models


Registry = Annotated[ModelRegistry, Depends(get_registry)]


@router.post("/predict", response_model=PredictionOut, status_code=status.HTTP_201_CREATED,
             summary="Predict final exam performance for a student and save it")
def predict(body: PredictRequest, db: DB, registry: Registry, user: CurrentUser) -> PredictionOut:
    return PredictionOut.from_row(prediction_service.create_prediction(db, registry, user, body))


@router.post("/simulate", response_model=SimulationOut,
             summary="What-if simulation with any inputs (not saved)")
def simulate(body: SimulateRequest, registry: Registry, _: CurrentUser) -> SimulationOut:
    model, values, result, explanation, recommendations = prediction_service.simulate(registry, body)
    return SimulationOut(
        stage=body.stage, inputs=values, predicted_marks=result.predicted, risk_level=risk_level(result.predicted),
        interval=Interval(low=result.interval_low, high=result.interval_high), warnings=result.warnings,
        shap_explanation=explanation, recommendations=recommendations,
        model_version=model.metadata["model_version"],
    )


@router.get("/history/{student_id}", response_model=PredictionHistory, summary="A student's predictions, newest first")
def history(student_id: int, db: DB, user: CurrentUser) -> PredictionHistory:
    rows = prediction_service.history(db, user, student_id)
    return PredictionHistory(student_id=student_id, items=[PredictionOut.from_row(r) for r in rows])


@router.get("/{prediction_id}", response_model=PredictionOut, summary="One saved prediction")
def get_prediction(prediction_id: int, db: DB, user: CurrentUser) -> PredictionOut:
    return PredictionOut.from_row(prediction_service.get_prediction(db, user, prediction_id))


@info_router.get("/model-info", response_model=ModelInfo, summary="Models in use: algorithm, metrics, training date")
def model_info(registry: Registry) -> ModelInfo:
    stages: list[ModelStageInfo] = []
    limitations: list[str] = []
    for stage in STAGES:
        loaded = registry.get(stage)
        if loaded is None:
            stages.append(ModelStageInfo(stage=stage, loaded=False, reason=registry.errors.get(stage, "not loaded")))
            continue
        meta = loaded.metadata
        limitations = meta.get("limitations", limitations)
        stages.append(ModelStageInfo(
            stage=stage, loaded=True, model_version=meta["model_version"], algorithm=meta.get("algorithm"),
            features=meta.get("features", []), metrics=meta.get("metrics"),
            model_comparison=meta.get("model_comparison", []), selection=meta.get("selection"),
            trained_at=meta.get("training", {}).get("trained_at"), library_versions=meta.get("library_versions"),
        ))
    return ModelInfo(stages=stages, risk_thresholds=thresholds(), limitations=limitations)


@info_router.get("/feature-importance", response_model=FeatureImportance,
                 summary="Global SHAP feature importance (mean |SHAP| over the training set)")
def feature_importance(
    registry: Registry,
    stage: Annotated[PredictionStage | None, Query(description="Omit for both stages")] = None,
) -> FeatureImportance:
    wanted = [stage.value] if stage else list(STAGES)
    stages: list[StageImportance] = []
    for name in wanted:
        loaded = registry.get(name)
        shap_meta = (loaded.metadata.get("shap") or {}) if loaded else {}
        if loaded is None or "global_importance" not in shap_meta:
            raise AppError(503, "model_unavailable", f"Feature importance for {name} is not available.",
                           details={"reason": registry.errors.get(name) or "no SHAP metadata"})
        importance = shap_meta["global_importance"]
        stages.append(StageImportance(
            stage=name, model_version=loaded.metadata["model_version"],
            method=f"shap.{'LinearExplainer' if shap_meta['explainer'] == 'linear' else 'TreeExplainer'}",
            computed_on=importance["computed_on"], statistic=importance["statistic"],
            base_value=shap_meta["base_value"], values=importance["values"],
        ))
    return FeatureImportance(stages=stages)
