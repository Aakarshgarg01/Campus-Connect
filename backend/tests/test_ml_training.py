"""Phase 6: dataset validation, feature preparation, saved artifacts and loader safety checks."""

from __future__ import annotations

import json
import shutil

import pandas as pd
import pytest
import sklearn

from app.core.config import BACKEND_ROOT
from app.ml.features import ASSIGNMENT, ATTENDANCE, INTERNAL1, INTERNAL2, STAGE_FEATURES, TARGET
from app.ml.model_loader import load_models
from ml_training.dataset import RAW_ATTENDANCE, RAW_INTERNAL1, file_sha256, load_raw, prepare, validate
from ml_training.train import SEED, metrics, split

MODELS_STORE = BACKEND_ROOT / "models_store"


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return load_raw()


# --- dataset -------------------------------------------------------------------------------------

def test_real_dataset_is_valid(raw):
    assert validate(raw) == [] and len(raw) == 2000


def test_validation_reports_problems(raw):
    broken = raw.copy()
    broken.loc[0, RAW_ATTENDANCE] = 120
    broken.loc[1, RAW_INTERNAL1] = None
    problems = validate(broken)
    assert any("missing values" in p for p in problems)
    assert any("outside [0, 100] in Attendance (%)" in p for p in problems)
    assert validate(raw.drop(columns=RAW_INTERNAL1)) == [f"missing columns: ['{RAW_INTERNAL1}']"]


def test_prepare_converts_raw_marks_to_percentages(raw):
    data = prepare(raw.head(1))
    row = raw.iloc[0]
    assert data[ATTENDANCE].iloc[0] == row["Attendance (%)"]
    assert data[INTERNAL1].iloc[0] == row["Internal Test 1 (out of 40)"] / 40 * 100
    assert data[ASSIGNMENT].iloc[0] == row["Assignment Score (out of 10)"] * 10
    assert TARGET in data and "Daily Study Hours" not in data and "Student_ID" not in data


def test_stage1_never_uses_internal2():
    assert INTERNAL2 not in STAGE_FEATURES["stage1"]
    assert set(STAGE_FEATURES["stage1"]) < set(STAGE_FEATURES["stage2"])
    assert TARGET not in STAGE_FEATURES["stage2"]


# --- saved artifacts -------------------------------------------------------------------------------

@pytest.mark.parametrize("stage", list(STAGE_FEATURES))
def test_saved_metadata_is_complete_and_matches_environment(stage):
    meta = json.loads((MODELS_STORE / stage / "metadata.json").read_text())
    for key in ("model_version", "algorithm", "features", "metrics", "model_comparison", "training",
                "library_versions", "model_sha256", "shap_explainer"):
        assert key in meta, key
    assert [f["name"] for f in meta["features"]] == STAGE_FEATURES[stage]
    assert meta["library_versions"]["scikit-learn"] == sklearn.__version__
    assert meta["training"]["dataset"]["sha256"] == file_sha256()
    assert meta["training"]["random_seed"] == SEED
    assert {m["key"] for m in meta["model_comparison"]} >= {
        "linear_regression", "decision_tree", "random_forest", "gradient_boosting"}


def test_saved_models_load_and_reproduce_reported_test_metrics(raw):
    registry = load_models(MODELS_STORE)
    assert registry.all_loaded, registry.errors
    _, test = split(prepare(raw))
    for stage, features in STAGE_FEATURES.items():
        loaded = registry.get(stage)
        predictions = loaded.pipeline.predict(test[features])
        # The numbers in metadata.json are exactly those of the saved pipeline on the held-out set.
        assert metrics(test[TARGET], predictions) == loaded.metadata["metrics"]["test"]


def test_saved_pipeline_includes_preprocessing():
    registry = load_models(MODELS_STORE)
    pipeline = registry.get("stage2").pipeline
    assert list(pipeline.named_steps) == ["preprocess", "model"]
    sample = pd.DataFrame([{ATTENDANCE: 85.0, INTERNAL1: 80.0, INTERNAL2: 80.0, ASSIGNMENT: 75.0}])
    assert 0 <= float(pipeline.predict(sample)[0]) <= 100


# --- loader safety -----------------------------------------------------------------------------------

def _copy_store(tmp_path):
    target = tmp_path / "store"
    shutil.copytree(MODELS_STORE, target)
    return target


def test_loader_rejects_scikit_learn_version_mismatch(tmp_path):
    store = _copy_store(tmp_path)
    path = store / "stage1" / "metadata.json"
    meta = json.loads(path.read_text())
    meta["library_versions"]["scikit-learn"] = "0.0.1"
    path.write_text(json.dumps(meta))
    registry = load_models(store)
    assert registry.get("stage1") is None and registry.get("stage2") is not None
    assert registry.errors["stage1"].startswith("scikit-learn version mismatch (trained 0.0.1")


def test_loader_rejects_wrong_feature_list(tmp_path):
    store = _copy_store(tmp_path)
    shutil.copy(store / "stage2" / "metadata.json", store / "stage1" / "metadata.json")
    shutil.copy(store / "stage2" / "model.joblib", store / "stage1" / "model.joblib")
    assert load_models(store).errors["stage1"] == "model features do not match this API's feature list"
