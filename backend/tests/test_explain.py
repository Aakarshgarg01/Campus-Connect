"""Phase 8: SHAP explanations, additivity, one-hot aggregation, recommendations, global importance."""

from __future__ import annotations

import json
import re
import shutil

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy.orm import Session

from app.ml.explain import StageExplainer, output_to_source
from app.ml.features import STAGE_FEATURES, TARGET
from app.ml.model_loader import load_models
from app.ml.predict import to_frame
from app.models import Prediction, Student
from ml_training.dataset import load_raw, prepare
from ml_training.train import split
from tests.conftest import REAL_MODELS
from tests.helpers import create_staff, login

RNG = np.random.default_rng(0)


@pytest.fixture(scope="module")
def registry():
    return load_models(REAL_MODELS)


@pytest.fixture(scope="module")
def train_frame():
    train, _ = split(prepare(load_raw()))
    return train


def _random_inputs(stage: str, n: int) -> list[dict[str, float]]:
    return [{f: float(RNG.uniform(0, 100)) for f in STAGE_FEATURES[stage]} for _ in range(n)]


# --- additivity and correctness -----------------------------------------------------------------

@pytest.mark.parametrize("stage", list(STAGE_FEATURES))
def test_additivity_holds_for_random_inputs(registry, stage):
    model = registry.get(stage)
    assert model.explainer is not None, model.explainer_error
    for inputs in _random_inputs(stage, 200):
        explanation = model.explainer.explain(inputs)
        total = explanation["base_value"] + sum(c["shap_value"] for c in explanation["contributions"])
        raw = float(model.pipeline.predict(to_frame(stage, inputs))[0])
        assert abs(total - raw) < 1e-3  # rounded to 4 dp in the payload
        assert explanation["additivity_error"] < 1e-6  # unrounded check done inside explain()


def test_linear_shap_equals_coefficient_times_deviation_from_background_mean(registry):
    """For a linear model SHAP is exact: coef_i * (x_i - mean_i) in the original units."""
    model = registry.get("stage2")
    preprocess, linear = model.pipeline.named_steps["preprocess"], model.pipeline.named_steps["model"]
    scaler = preprocess.named_transformers_["num"]
    coef = linear.coef_ / scaler.scale_
    background = pd.read_csv(REAL_MODELS / "stage2" / "background.csv")
    inputs = {"attendance_pct": 70.0, "internal1_pct": 65.0, "internal2_pct": 90.0, "assignment_pct": 55.0}
    explained = {c["feature"]: c["shap_value"] for c in model.explainer.explain(inputs)["contributions"]}
    for i, feature in enumerate(STAGE_FEATURES["stage2"]):
        assert explained[feature] == pytest.approx(coef[i] * (inputs[feature] - background[feature].mean()), abs=1e-4)


def test_contributions_sorted_by_absolute_impact_with_directions(registry):
    explanation = registry.get("stage2").explainer.explain(
        {"attendance_pct": 95, "internal1_pct": 50, "internal2_pct": 85, "assignment_pct": 74})
    impacts = [abs(c["shap_value"]) for c in explanation["contributions"]]
    assert impacts == sorted(impacts, reverse=True)
    for c in explanation["contributions"]:
        assert c["direction"] == ("increases" if c["shap_value"] > 0 else "decreases")


def test_tree_explainer_path_is_additive(train_frame):
    features = STAGE_FEATURES["stage2"]
    pipeline = Pipeline([
        ("preprocess", ColumnTransformer([("num", StandardScaler(), features)], verbose_feature_names_out=False)),
        ("model", GradientBoostingRegressor(n_estimators=50, max_depth=2, random_state=0)),
    ]).fit(train_frame[features], train_frame[TARGET])
    explainer = StageExplainer.build(pipeline, features, "tree", train_frame.sample(100, random_state=0))
    for inputs in _random_inputs("stage2", 25):
        explanation = explainer.explain(inputs)
        assert explanation["method"] == "shap.TreeExplainer"
        assert explanation["additivity_error"] < 1e-6


def test_one_hot_columns_are_aggregated_back_to_their_input(train_frame):
    """Generic path: a categorical input expanded by OneHotEncoder gets one combined SHAP value."""
    frame = train_frame.copy()
    frame["band"] = pd.cut(frame["attendance_pct"], [0, 80, 90, 101], labels=["low", "mid", "high"]).astype(str)
    numeric = ["internal1_pct", "assignment_pct"]
    features = [*numeric, "band"]
    preprocess = ColumnTransformer([("num", StandardScaler(), numeric),
                                    ("cat", OneHotEncoder(handle_unknown="ignore"), ["band"])],
                                   verbose_feature_names_out=False)
    pipeline = Pipeline([("preprocess", preprocess), ("model", LinearRegression())]).fit(frame[features], frame[TARGET])
    assert output_to_source(pipeline.named_steps["preprocess"]) == [*numeric, "band", "band", "band"]

    explainer = StageExplainer.build(pipeline, features, "linear", frame.sample(200, random_state=1))
    row = frame[features].iloc[0]
    one = pd.DataFrame([row.to_dict()], columns=features)
    values = explainer.shap_matrix(one)[0]
    assert len(values) == len(features)  # one value per original input, not per one-hot column
    raw = float(pipeline.predict(one)[0])
    assert explainer.base_value + values.sum() == pytest.approx(raw, abs=1e-6)


# --- API: predictions carry explanation + recommendations ---------------------------------------

@pytest.fixture
def staff(api_real, engine):
    create_staff(engine)
    return login(api_real, "FAC1024")


@pytest.fixture
def student_id(engine) -> int:
    with Session(engine) as db:
        student = Student(roll_number="CS21041", name="Asha", email="asha@college.edu", department="CS", semester=7)
        db.add(student)
        db.commit()
        return student.id


WEAK = {"attendance": 68, "internal1": 62.5, "internal2": 85, "assignment": 60}
BANNED = re.compile(r"\b(will (improve|increase|raise)|causes?|guarantees? (a|that)|proven)\b", re.I)


def test_predict_returns_saved_explanation_and_recommendations(api_real, staff, student_id, registry, engine):
    response = api_real.post("/api/predictions/predict", headers=staff,
                             json={"student_id": student_id, "stage": "stage2", "inputs": WEAK})
    assert response.status_code == 201, response.text
    body = response.json()
    explanation, recs = body["shap_explanation"], body["recommendations"]

    total = explanation["base_value"] + sum(c["shap_value"] for c in explanation["contributions"])
    assert total == pytest.approx(explanation["raw_prediction"], abs=1e-3)
    assert float(body["predicted_marks"]) == round(explanation["raw_prediction"], 2)

    negatives = [c["feature"] for c in explanation["contributions"] if c["direction"] == "decreases"]
    assert [i["feature"] for i in recs["items"]] == negatives[:3]
    assert [s["feature"] for s in recs["strengths"]] == ["internal2_pct"]

    model = registry.get("stage2")
    values = body["inputs"]
    base = float(model.pipeline.predict(to_frame("stage2", values))[0])
    for item in recs["items"]:
        changed = {**values, item["feature"]: item["estimated_effect"]["change_to"]}
        effect = float(model.pipeline.predict(to_frame("stage2", changed))[0]) - base
        assert item["estimated_effect"]["predicted_change"] == pytest.approx(effect, abs=0.01)
        assert item["current_value"] == values[item["feature"]]
        assert "associated" in item["finding"] and "not a guarantee" in item["estimated_effect"]["text"]

    all_text = json.dumps(recs)
    assert not BANNED.search(all_text.replace("not a guarantee", "")), BANNED.search(all_text)
    assert "not proof" in recs["summary"]

    with Session(engine) as db:
        saved = db.get(Prediction, body["id"])
        assert saved.shap_explanation == explanation and saved.recommendations == recs
    history = api_real.get(f"/api/predictions/history/{student_id}", headers=staff).json()
    assert history["items"][0]["recommendations"] == recs


def test_strong_student_gets_no_improvement_items(api_real, staff):
    response = api_real.post("/api/predictions/simulate", headers=staff, json={
        "stage": "stage2", "inputs": {"attendance": 98, "internal1": 95, "internal2": 95, "assignment": 95}})
    recs = response.json()["recommendations"]
    assert response.json()["risk_level"] == "low" and recs["items"] == []
    assert len(recs["strengths"]) == 4
    assert response.json()["shap_explanation"]["contributions"]


def test_stage1_summary_mentions_internal2_pending(api_real, staff):
    response = api_real.post("/api/predictions/simulate", headers=staff,
                             json={"stage": "stage1", "inputs": {"attendance": 70, "internal1": 60, "assignment": 60}})
    assert "Internal Test 2 has not been included yet" in response.json()["recommendations"]["summary"]


def test_prediction_still_works_when_explainer_unavailable(make_client, mysql_url, engine, tmp_path, student_id):
    store = tmp_path / "store"
    shutil.copytree(REAL_MODELS, store)
    (store / "stage1" / "background.csv").unlink()
    client = make_client(database_url=mysql_url, model_dir=store)
    try:
        create_staff(engine)
        headers = login(client, "FAC1024")
        assert client.get("/health").json()["models"]["stage1"]["explainer_ready"] is False
        response = client.post("/api/predictions/predict", headers=headers, json={
            "student_id": student_id, "stage": "stage1", "inputs": {"attendance": 80, "internal1": 70, "assignment": 70}})
        assert response.status_code == 201
        body = response.json()
        assert body["shap_explanation"] is None and body["recommendations"] is None
        assert any("explanation is not available" in w for w in body["warnings"])
    finally:
        from tests.conftest import empty_all_tables
        empty_all_tables(engine)


# --- global importance ---------------------------------------------------------------------------

def test_feature_importance_endpoint_matches_recomputation(api_real, registry, train_frame):
    body = api_real.get("/api/feature-importance").json()
    assert [s["stage"] for s in body["stages"]] == ["stage1", "stage2"]
    for stage_body in body["stages"]:
        stage = stage_body["stage"]
        recomputed = registry.get(stage).explainer.global_importance(train_frame)
        assert stage_body["values"] == recomputed
        assert sum(v["share"] for v in stage_body["values"]) == pytest.approx(1, abs=1e-3)
        assert stage_body["computed_on"] == "training set (n=1600)"
    only = api_real.get("/api/feature-importance?stage=stage1").json()
    assert [s["stage"] for s in only["stages"]] == ["stage1"]
    assert api_real.get("/api/feature-importance?stage=stage9").status_code == 422


def test_feature_importance_503_without_models(make_client, tmp_path):
    client = make_client(model_dir=tmp_path / "none")
    response = client.get("/api/feature-importance")
    assert response.status_code == 503 and response.json()["error"]["code"] == "model_unavailable"
