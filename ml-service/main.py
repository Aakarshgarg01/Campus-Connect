"""FastAPI service for the trained CampusConnect prediction models."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator

from preprocessing.pipeline import STAGE1_FEATURES, STAGE2_FEATURES

logger = logging.getLogger(__name__)

SERVICE_ROOT = Path(__file__).resolve().parent
STAGE1_MODEL_PATH = SERVICE_ROOT / "models" / "stage1_model.pkl"
STAGE2_MODEL_PATH = SERVICE_ROOT / "models" / "stage2_model.pkl"


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Stage1PredictionRequest(StrictRequestModel):
    attendance: float = Field(ge=0, le=100)
    internal1: float = Field(ge=0, le=100)
    assignment: float = Field(ge=0, le=100)


class Stage2PredictionRequest(StrictRequestModel):
    attendance: float = Field(ge=0, le=100)
    internal1: float = Field(ge=0, le=100)
    internal2: float = Field(ge=0, le=100)
    assignment: float = Field(ge=0, le=100)


class WhatIfPredictionRequest(StrictRequestModel):
    stage: Literal["stage1", "stage2"]
    attendance: float = Field(ge=0, le=100)
    internal1: float = Field(ge=0, le=100)
    internal2: float | None = Field(default=None, ge=0, le=100)
    assignment: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def require_stage2_internal(self) -> "WhatIfPredictionRequest":
        if self.stage == "stage2" and self.internal2 is None:
            raise ValueError("internal2 is required when stage is stage2")
        return self


class PredictionResponse(BaseModel):
    stage: Literal["stage1", "stage2"]
    predicted_final_performance: float


class WhatIfPredictionResponse(PredictionResponse):
    simulation_only: bool
    message: str


def _load_models() -> dict[str, object]:
    models: dict[str, object] = {}
    for stage, model_path in (
        ("stage1", STAGE1_MODEL_PATH),
        ("stage2", STAGE2_MODEL_PATH),
    ):
        if not model_path.is_file():
            raise RuntimeError(f"Required {stage} model is missing: {model_path}")
        try:
            models[stage] = joblib.load(model_path)
        except Exception as exc:
            logger.exception("Could not load %s model", stage)
            raise RuntimeError(f"Could not load required {stage} model") from exc
    return models


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.models = _load_models()
    logger.info("CampusConnect ML models loaded successfully")
    yield


app = FastAPI(
    title="CampusConnect ML Service",
    description="Linear Regression predictions for academic performance monitoring.",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)


def _predict(
    model: object,
    values: dict[str, float],
    feature_order: list[str],
) -> float:
    features = pd.DataFrame([values], columns=feature_order)
    try:
        return round(float(model.predict(features)[0]), 2)  # type: ignore[attr-defined]
    except Exception:
        logger.exception("Model prediction failed")
        raise HTTPException(status_code=500, detail="Prediction failed.") from None


def _get_model(request: Request, stage: str) -> object:
    models = getattr(request.app.state, "models", None)
    model = models.get(stage) if models else None
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not available.")
    return model


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    models = getattr(request.app.state, "models", None)
    if (
        not STAGE1_MODEL_PATH.is_file()
        or not STAGE2_MODEL_PATH.is_file()
        or not models
    ):
        raise HTTPException(status_code=503, detail="Required models are not available.")
    return {"status": "ok", "service": "CampusConnect ML Service"}


@app.post("/predict/stage1", response_model=PredictionResponse)
def predict_stage1(
    payload: Stage1PredictionRequest,
    request: Request,
) -> PredictionResponse:
    prediction = _predict(
        _get_model(request, "stage1"),
        {
            "Attendance (%)": payload.attendance,
            "Internal Test 1 (%)": payload.internal1,
            "Assignment (%)": payload.assignment,
        },
        STAGE1_FEATURES,
    )
    return PredictionResponse(stage="stage1", predicted_final_performance=prediction)


@app.post("/predict/stage2", response_model=PredictionResponse)
def predict_stage2(
    payload: Stage2PredictionRequest,
    request: Request,
) -> PredictionResponse:
    prediction = _predict(
        _get_model(request, "stage2"),
        {
            "Attendance (%)": payload.attendance,
            "Internal Test 1 (%)": payload.internal1,
            "Internal Test 2 (%)": payload.internal2,
            "Assignment (%)": payload.assignment,
        },
        STAGE2_FEATURES,
    )
    return PredictionResponse(stage="stage2", predicted_final_performance=prediction)


@app.post("/predict/what-if", response_model=WhatIfPredictionResponse)
def predict_what_if(
    payload: WhatIfPredictionRequest,
    request: Request,
) -> WhatIfPredictionResponse:
    if payload.stage == "stage1":
        values = {
            "Attendance (%)": payload.attendance,
            "Internal Test 1 (%)": payload.internal1,
            "Assignment (%)": payload.assignment,
        }
        feature_order = STAGE1_FEATURES
    else:
        values = {
            "Attendance (%)": payload.attendance,
            "Internal Test 1 (%)": payload.internal1,
            "Internal Test 2 (%)": payload.internal2,
            "Assignment (%)": payload.assignment,
        }
        feature_order = STAGE2_FEATURES

    prediction = _predict(_get_model(request, payload.stage), values, feature_order)
    return WhatIfPredictionResponse(
        stage=payload.stage,
        predicted_final_performance=prediction,
        simulation_only=True,
        message="Simulation only - this is not a guaranteed result.",
    )