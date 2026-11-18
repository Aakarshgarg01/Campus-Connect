"""Loads the trained stage pipelines once at startup and records why any failed.

Expected layout (produced by ml_training/train.py in Phase 6):
    models_store/stage1/model.joblib + metadata.json
    models_store/stage2/model.joblib + metadata.json
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import sklearn

from app.ml.explain import StageExplainer
from app.ml.features import STAGE_FEATURES

logger = logging.getLogger(__name__)

STAGES = tuple(STAGE_FEATURES)


@dataclass
class LoadedModel:
    pipeline: Any
    metadata: dict[str, Any]
    explainer: StageExplainer | None = None
    explainer_error: str | None = None


@dataclass
class ModelRegistry:
    models: dict[str, LoadedModel] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def get(self, stage: str) -> LoadedModel | None:
        return self.models.get(stage)

    def status(self) -> dict[str, dict[str, Any]]:
        report: dict[str, dict[str, Any]] = {}
        for stage in STAGES:
            loaded = self.models.get(stage)
            if loaded:
                report[stage] = {
                    "loaded": True,
                    "model_version": loaded.metadata.get("model_version"),
                    "explainer_ready": loaded.explainer is not None,
                }
                if loaded.explainer_error:
                    report[stage]["explainer_error"] = loaded.explainer_error
            else:
                report[stage] = {"loaded": False, "reason": self.errors.get(stage, "not loaded")}
        return report

    @property
    def all_loaded(self) -> bool:
        return all(stage in self.models for stage in STAGES)


def _check_compatibility(stage: str, metadata: dict[str, Any], model_bytes: bytes) -> str | None:
    """Refuse a model that is corrupted, for another stage, or pickled by another scikit-learn."""
    expected_sha = metadata.get("model_sha256")
    if expected_sha and hashlib.sha256(model_bytes).hexdigest() != expected_sha:
        return "model file does not match metadata.json (sha256 mismatch)"
    trained_with = metadata.get("library_versions", {}).get("scikit-learn")
    if trained_with != sklearn.__version__:
        return f"scikit-learn version mismatch (trained {trained_with}, installed {sklearn.__version__})"
    features = [f["name"] if isinstance(f, dict) else f for f in metadata.get("features", [])]
    if features != STAGE_FEATURES[stage]:
        return "model features do not match this API's feature list"
    return None


def _build_explainer(stage: str, stage_dir: Path, pipeline: Any, metadata: dict[str, Any]
                     ) -> tuple[StageExplainer | None, str | None]:
    """Build the SHAP explainer once at startup. A failure here leaves predictions working
    (they are returned without an explanation) and is reported by /health."""
    shap_meta = metadata.get("shap") or {}
    background_path = stage_dir / shap_meta.get("background_file", "background.csv")
    try:
        if not background_path.is_file():
            return None, "SHAP background file is missing"
        data = background_path.read_bytes()
        if shap_meta.get("background_sha256") and hashlib.sha256(data).hexdigest() != shap_meta["background_sha256"]:
            return None, "SHAP background file does not match metadata.json"
        background = pd.read_csv(io.BytesIO(data))
        return StageExplainer.build(pipeline, STAGE_FEATURES[stage], shap_meta.get("explainer", "linear"), background), None
    except Exception as exc:
        logger.exception("SHAP explainer failed to build", extra={"stage": stage})
        return None, f"SHAP explainer failed to build ({type(exc).__name__})"


def load_models(model_dir: Path) -> ModelRegistry:
    registry = ModelRegistry()
    for stage in STAGES:
        model_path = model_dir / stage / "model.joblib"
        metadata_path = model_dir / stage / "metadata.json"
        if not model_path.is_file() or not metadata_path.is_file():
            registry.errors[stage] = "model file or metadata.json is missing"
            logger.warning("Model not found", extra={"stage": stage, "path": str(model_path)})
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            model_bytes = model_path.read_bytes()
            problem = _check_compatibility(stage, metadata, model_bytes)
            if problem:
                registry.errors[stage] = problem
                logger.error("Model rejected", extra={"stage": stage, "reason": problem})
                continue
            pipeline = joblib.load(io.BytesIO(model_bytes))
        except Exception as exc:
            registry.errors[stage] = f"failed to load ({type(exc).__name__})"
            logger.exception("Model failed to load", extra={"stage": stage})
            continue
        loaded = LoadedModel(pipeline=pipeline, metadata=metadata)
        loaded.explainer, loaded.explainer_error = _build_explainer(stage, model_dir / stage, pipeline, metadata)
        registry.models[stage] = loaded
        logger.info("Model loaded", extra={"stage": stage, "model_version": metadata.get("model_version")})
    return registry
