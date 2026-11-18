"""Run a loaded stage pipeline on one set of inputs.

Returns the clipped prediction, a 90% error band taken from the held-out test errors in
metadata.json, and warnings when inputs fall outside the range the model was trained on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.ml.features import FEATURE_LABELS, STAGE_FEATURES
from app.ml.model_loader import LoadedModel


@dataclass
class PredictionResult:
    predicted: float  # clipped to 0-100, rounded to 2 dp
    raw_prediction: float
    interval_low: float
    interval_high: float
    warnings: list[str] = field(default_factory=list)


def to_frame(stage: str, inputs: dict[str, float]) -> pd.DataFrame:
    """One-row DataFrame with exactly the stage's columns in training order."""
    return pd.DataFrame([[float(inputs[f]) for f in STAGE_FEATURES[stage]]], columns=STAGE_FEATURES[stage])


def predict(model: LoadedModel, stage: str, inputs: dict[str, float]) -> PredictionResult:
    raw = float(model.pipeline.predict(to_frame(stage, inputs))[0])
    predicted = round(min(100.0, max(0.0, raw)), 2)

    warnings: list[str] = []
    if predicted != round(raw, 2):
        warnings.append(f"The model's raw estimate ({raw:.2f}) was outside 0-100 and has been clipped.")
    for feature in model.metadata.get("features", []):
        low, high = feature["training_range"]
        value = float(inputs[feature["name"]])
        if not low <= value <= high:
            warnings.append(
                f"{FEATURE_LABELS[feature['name']]} {value:g}% is outside the training range "
                f"({low:g}-{high:g}%); this prediction is an extrapolation and less reliable."
            )

    # 90% of absolute errors on the held-out test set were at most this many marks.
    margin = float(model.metadata["test_diagnostics"]["abs_error_p90"])
    return PredictionResult(
        predicted=predicted,
        raw_prediction=round(raw, 4),
        interval_low=round(max(0.0, predicted - margin), 2),
        interval_high=round(min(100.0, predicted + margin), 2),
        warnings=warnings,
    )
