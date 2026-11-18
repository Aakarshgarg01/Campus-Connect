"""SHAP explanations for the saved pipelines.

SHAP is computed on the *transformed* features the model actually sees (after the
ColumnTransformer), then mapped back to the original input names. Where one input becomes
several model columns (e.g. one-hot encoding), their SHAP values are summed, which keeps
additivity: base_value + sum(contributions) == the model's raw prediction.

Explainer per model type:
  linear models -> shap.LinearExplainer (exact for linear models)
  tree models   -> shap.TreeExplainer, interventional, with the same background data
Both use a background sample of training rows, so base_value is the model's average
prediction over that sample.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from app.ml.features import FEATURE_LABELS

ADDITIVITY_TOLERANCE = 1e-6


def split_pipeline(pipeline: Pipeline) -> tuple[ColumnTransformer, object]:
    return pipeline.named_steps["preprocess"], pipeline.named_steps["model"]


def output_to_source(preprocess: ColumnTransformer) -> list[str]:
    """For every transformed column, the original input column it came from."""
    sources: list[str] = []
    for _, transformer, columns in preprocess.transformers_:
        if transformer == "drop" or len(columns) == 0:
            continue
        columns = list(columns)
        if transformer == "passthrough":
            sources.extend(columns)
            continue
        produced = list(transformer.get_feature_names_out(columns))
        if len(produced) == len(columns):  # one-to-one (scalers, imputers)
            sources.extend(columns)
        else:  # one-to-many (one-hot): names are "<column>_<category>"
            for name in produced:
                matches = [c for c in columns if name == c or name.startswith(f"{c}_")]
                if len(matches) != 1:
                    raise ValueError(f"cannot map transformed column {name!r} back to an input")
                sources.append(matches[0])
    return sources


@dataclass
class StageExplainer:
    pipeline: Pipeline
    features: list[str]
    kind: str  # "linear" or "tree"
    explainer: object
    sources: list[str]

    @classmethod
    def build(cls, pipeline: Pipeline, features: list[str], kind: str, background: pd.DataFrame) -> StageExplainer:
        preprocess, model = split_pipeline(pipeline)
        background_t = np.asarray(preprocess.transform(background[features]), dtype=float)
        if kind == "linear":
            # Explicit masker using every background row: the default silently subsamples to
            # 100 rows at random, which would make base_value differ between processes.
            masker = shap.maskers.Independent(background_t, max_samples=len(background_t))
            explainer = shap.LinearExplainer(model, masker)
        elif kind == "tree":
            explainer = shap.TreeExplainer(model, data=background_t, feature_perturbation="interventional")
        else:
            raise ValueError(f"unsupported explainer kind: {kind}")
        return cls(pipeline, features, kind, explainer, output_to_source(preprocess))

    @property
    def base_value(self) -> float:
        return float(np.ravel(self.explainer.expected_value)[0])

    def shap_matrix(self, frame: pd.DataFrame) -> np.ndarray:
        """SHAP values per original input (rows x features), one-hot columns aggregated."""
        preprocess, _ = split_pipeline(self.pipeline)
        transformed = np.asarray(preprocess.transform(frame[self.features]), dtype=float)
        if self.kind == "tree":
            values = self.explainer.shap_values(transformed, check_additivity=True)
        else:
            values = self.explainer.shap_values(transformed)
        values = np.asarray(values, dtype=float).reshape(len(frame), -1)
        aggregated = np.zeros((len(frame), len(self.features)))
        for column, source in enumerate(self.sources):
            aggregated[:, self.features.index(source)] += values[:, column]
        return aggregated

    def explain(self, inputs: dict[str, float]) -> dict:
        frame = pd.DataFrame([[float(inputs[f]) for f in self.features]], columns=self.features)
        contributions = self.shap_matrix(frame)[0]
        raw_prediction = float(self.pipeline.predict(frame)[0])
        base = self.base_value
        additivity_error = abs(base + float(contributions.sum()) - raw_prediction)
        if additivity_error > ADDITIVITY_TOLERANCE:
            raise RuntimeError(f"SHAP additivity check failed (error {additivity_error:.2e})")
        items = [
            {
                "feature": feature,
                "label": FEATURE_LABELS.get(feature, feature),
                "value": round(float(inputs[feature]), 2),
                "shap_value": round(float(value), 4),
                "direction": "increases" if value > 1e-9 else "decreases" if value < -1e-9 else "neutral",
            }
            for feature, value in zip(self.features, contributions)
        ]
        items.sort(key=lambda item: abs(item["shap_value"]), reverse=True)
        return {
            "method": f"shap.{'LinearExplainer' if self.kind == 'linear' else 'TreeExplainer'}",
            "base_value": round(base, 4),
            "raw_prediction": round(raw_prediction, 4),
            "additivity_error": float(f"{additivity_error:.3e}"),
            "contributions": items,
            "note": "Each contribution is how much that input moves this estimate away from the average "
                    "prediction (base_value). Contributions are associations learned from data, not causes.",
        }

    def global_importance(self, frame: pd.DataFrame) -> list[dict]:
        """Mean |SHAP| per input over `frame`, largest first, with each one's share of the total."""
        mean_abs = np.abs(self.shap_matrix(frame)).mean(axis=0)
        total = float(mean_abs.sum()) or 1.0
        rows = [{"feature": f, "label": FEATURE_LABELS.get(f, f), "mean_abs_shap": round(float(v), 4),
                 "share": round(float(v) / total, 4)} for f, v in zip(self.features, mean_abs)]
        return sorted(rows, key=lambda r: r["mean_abs_shap"], reverse=True)
