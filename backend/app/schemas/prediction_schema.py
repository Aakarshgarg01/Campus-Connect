"""Request/response models for predictions and model information."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ml.features import ASSIGNMENT, ATTENDANCE, INTERNAL1, INTERNAL2, STAGE_FEATURES
from app.models import PredictionStage, RiskLevel
from app.schemas.common import Semester

Pct = Annotated[float, Field(ge=0, le=100, description="Percentage, 0-100")]


class PredictionInputs(BaseModel):
    """Percentages. For marks, send obtained / maximum * 100 (e.g. 32 out of 40 -> 80)."""

    model_config = ConfigDict(extra="forbid")

    attendance: Pct
    internal1: Pct
    internal2: Pct | None = None
    assignment: Pct

    def as_features(self) -> dict[str, float]:
        values = {ATTENDANCE: self.attendance, INTERNAL1: self.internal1, ASSIGNMENT: self.assignment}
        if self.internal2 is not None:
            values[INTERNAL2] = self.internal2
        return values


def _check_stage_inputs(stage: PredictionStage, inputs: PredictionInputs | None) -> None:
    if inputs is None:
        return
    if stage is PredictionStage.STAGE2 and inputs.internal2 is None:
        raise ValueError("stage2 requires inputs.internal2")
    if stage is PredictionStage.STAGE1 and inputs.internal2 is not None:
        raise ValueError("stage1 must not include internal2 (Internal 2 is not available at Stage 1)")


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int = Field(gt=0)
    stage: PredictionStage
    semester: Semester | None = Field(default=None, description="Defaults to the student's current semester")
    inputs: PredictionInputs | None = Field(
        default=None,
        description="Manual inputs (faculty/admin). Omit to compute them from the student's stored "
        "academic records and attendance for the semester.",
    )

    @model_validator(mode="after")
    def stage_matches_inputs(self) -> PredictRequest:
        _check_stage_inputs(self.stage, self.inputs)
        return self


class SimulateRequest(BaseModel):
    """What-if simulation: same model, nothing is saved."""

    model_config = ConfigDict(extra="forbid")

    stage: PredictionStage
    inputs: PredictionInputs

    @model_validator(mode="after")
    def stage_matches_inputs(self) -> SimulateRequest:
        _check_stage_inputs(self.stage, self.inputs)
        return self


class Interval(BaseModel):
    low: float
    high: float
    description: str = "90% of prediction errors on held-out test students were within this range"


class SimulationOut(BaseModel):
    stage: PredictionStage
    inputs: dict[str, float]
    predicted_marks: float
    risk_level: RiskLevel
    interval: Interval
    warnings: list[str]
    shap_explanation: dict[str, Any] | None = None
    recommendations: dict[str, Any] | None = None
    model_version: str
    simulation_only: Literal[True] = True
    disclaimer: str = "Simulation only - an estimate, not a guaranteed result. Nothing was saved."


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    semester: int
    stage: PredictionStage
    inputs: dict[str, Any]
    input_source: Literal["manual", "records"] | None = None
    predicted_marks: float
    risk_level: RiskLevel
    interval: Interval | None = None
    warnings: list[str] = []
    shap_explanation: dict[str, Any] | None
    recommendations: dict[str, Any] | None = None
    model_version: str
    created_by_user_id: int | None
    created_at: datetime
    disclaimer: str = "An estimate of final exam performance, not a guaranteed result."

    @classmethod
    def from_row(cls, row: Any) -> PredictionOut:
        out = cls.model_validate(row)
        stored = row.inputs or {}
        values = stored.get("values", {})
        # MySQL's JSON type does not keep key order; return inputs in the model's feature order.
        order = STAGE_FEATURES.get(row.stage.value, [])
        out.inputs = {k: values[k] for k in order if k in values} | values
        out.input_source = stored.get("source")
        if "interval" in stored:
            out.interval = Interval(**stored["interval"])
        out.warnings = list(stored.get("warnings", []))
        return out


class PredictionHistory(BaseModel):
    student_id: int
    items: list[PredictionOut]


class ModelStageInfo(BaseModel):
    stage: str
    loaded: bool
    model_version: str | None = None
    algorithm: str | None = None
    features: list[dict[str, Any]] = []
    metrics: dict[str, Any] | None = None
    model_comparison: list[dict[str, Any]] = []
    selection: dict[str, Any] | None = None
    trained_at: str | None = None
    library_versions: dict[str, str] | None = None
    reason: str | None = None


class ImportanceItem(BaseModel):
    feature: str
    label: str
    mean_abs_shap: float
    share: float


class StageImportance(BaseModel):
    stage: str
    model_version: str
    method: str
    computed_on: str
    statistic: str
    base_value: float
    values: list[ImportanceItem]


class FeatureImportance(BaseModel):
    stages: list[StageImportance]
    note: str = ("Mean absolute SHAP value: on average, how many marks each input moves an estimate away "
                 "from the average prediction. It measures association in the training data, not causation.")


class ModelInfo(BaseModel):
    stages: list[ModelStageInfo]
    risk_thresholds: dict[str, float]
    target: str = "Final exam marks (%)"
    dataset_provenance: str = "unknown"
    limitations: list[str]

