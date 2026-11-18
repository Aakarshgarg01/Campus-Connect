"""Phase 7: prediction API with the real trained models and MySQL."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.features import ASSIGNMENT, ATTENDANCE, INTERNAL1, INTERNAL2
from app.ml.model_loader import load_models
from app.ml.predict import to_frame
from app.models import AcademicRecord, Attendance, Prediction, RiskLevel, Student
from tests.conftest import REAL_MODELS
from tests.helpers import STUDENT, create_staff, login

MANUAL1 = {"attendance": 85, "internal1": 80, "assignment": 75}
MANUAL2 = {**MANUAL1, "internal2": 82.5}


@pytest.fixture(scope="module")
def registry():
    return load_models(REAL_MODELS)


@pytest.fixture
def staff(api_real, engine):
    create_staff(engine)
    return login(api_real, "FAC1024")


@pytest.fixture
def student_id(engine) -> int:
    with Session(engine) as db:
        student = Student(roll_number="CS21041", name="Asha Verma", email="asha.verma@college.edu",
                          department="Computer Science", semester=7)
        db.add(student)
        db.commit()
        return student.id


def _expected(registry, stage, features):
    return round(float(registry.get(stage).pipeline.predict(to_frame(stage, features))[0]), 2)


def _add_records(engine, student_id, *, with_internal2=True, semester=7):
    with Session(engine) as db:
        db.add_all([
            AcademicRecord(student_id=student_id, semester=semester, subject_name="Networks",
                           internal1_obtained=Decimal("30"), internal1_maximum=Decimal("40"),
                           internal2_obtained=Decimal("34") if with_internal2 else None,
                           internal2_maximum=Decimal("40") if with_internal2 else None,
                           assignment_obtained=Decimal("8"), assignment_maximum=Decimal("10")),
            AcademicRecord(student_id=student_id, semester=semester, subject_name="Databases",
                           internal1_obtained=Decimal("21"), internal1_maximum=Decimal("25"),
                           internal2_obtained=Decimal("27") if with_internal2 else None,
                           internal2_maximum=Decimal("30") if with_internal2 else None,
                           assignment_obtained=Decimal("14"), assignment_maximum=Decimal("20")),
            Attendance(student_id=student_id, semester=semester, attendance_percentage=Decimal("87.50")),
        ])
        db.commit()


# --- manual inputs ------------------------------------------------------------------------------

@pytest.mark.parametrize(("stage", "inputs"), [("stage1", MANUAL1), ("stage2", MANUAL2)])
def test_predict_manual_inputs_is_saved_and_matches_model(api_real, staff, student_id, registry, engine, stage, inputs):
    response = api_real.post("/api/predictions/predict", headers=staff,
                             json={"student_id": student_id, "stage": stage, "inputs": inputs})
    assert response.status_code == 201, response.text
    body = response.json()
    features = {ATTENDANCE: inputs["attendance"], INTERNAL1: inputs["internal1"], ASSIGNMENT: inputs["assignment"]}
    if stage == "stage2":
        features[INTERNAL2] = inputs["internal2"]
    expected = _expected(registry, stage, features)
    assert float(body["predicted_marks"]) == expected
    assert body["input_source"] == "manual" and body["inputs"] == {k: float(v) for k, v in features.items()}
    assert body["semester"] == 7  # defaulted from the student
    assert body["model_version"] == registry.get(stage).metadata["model_version"]
    assert body["interval"]["low"] < expected < body["interval"]["high"]
    assert body["risk_level"] == ("high" if expected < 50 else "medium" if expected < 60 else "low")
    with Session(engine) as db:
        saved = db.get(Prediction, body["id"])
        assert float(saved.predicted_marks) == expected and saved.created_by_user_id is not None


def test_risk_levels_follow_thresholds(api_real, staff, student_id):
    def risk(inputs):
        r = api_real.post("/api/predictions/simulate", headers=staff, json={"stage": "stage2", "inputs": inputs})
        return r.json()["predicted_marks"], r.json()["risk_level"]
    for inputs in ({"attendance": 95, "internal1": 95, "internal2": 95, "assignment": 90},
                   {"attendance": 78, "internal1": 70, "internal2": 70, "assignment": 70},
                   {"attendance": 65, "internal1": 55, "internal2": 55, "assignment": 50}):
        value, level = risk(inputs)
        assert level == ("high" if value < 50 else "medium" if value < 60 else "low")
    assert {risk(i)[1] for i in (
        {"attendance": 95, "internal1": 95, "internal2": 95, "assignment": 90},
        {"attendance": 78, "internal1": 70, "internal2": 70, "assignment": 70},
        {"attendance": 65, "internal1": 55, "internal2": 55, "assignment": 50})} == {"low", "medium", "high"}


def test_extreme_inputs_are_clipped_and_warned(api_real, staff, student_id):
    response = api_real.post("/api/predictions/predict", headers=staff, json={
        "student_id": student_id, "stage": "stage1", "inputs": {"attendance": 0, "internal1": 0, "assignment": 0}})
    assert response.status_code == 201
    body = response.json()
    assert float(body["predicted_marks"]) == 0.0 and body["risk_level"] == RiskLevel.HIGH.value
    assert any("clipped" in w for w in body["warnings"])
    assert any("outside the training range" in w for w in body["warnings"])


@pytest.mark.parametrize("payload", [
    {"stage": "stage1", "inputs": MANUAL2},                                   # stage1 with internal2
    {"stage": "stage2", "inputs": MANUAL1},                                   # stage2 without internal2
    {"stage": "stage1", "inputs": {**MANUAL1, "attendance": 101}},            # out of range
    {"stage": "stage1", "inputs": {**MANUAL1, "attendance": -1}},
    {"stage": "stage3", "inputs": MANUAL1},                                   # unknown stage
    {"stage": "stage1", "inputs": {**MANUAL1, "study_hours": 3}},            # unknown field
    {"stage": "stage1", "inputs": {"attendance": 80, "internal1": 70}},      # missing field
    {"stage": "stage1", "inputs": {**MANUAL1, "attendance": "lots"}},        # wrong type
])
def test_invalid_prediction_input_is_422(api_real, staff, student_id, payload):
    response = api_real.post("/api/predictions/predict", headers=staff, json={"student_id": student_id, **payload})
    assert response.status_code == 422, payload
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_student_is_404(api_real, staff):
    response = api_real.post("/api/predictions/predict", headers=staff,
                             json={"student_id": 999999, "stage": "stage1", "inputs": MANUAL1})
    assert response.status_code == 404


# --- inputs from stored records -------------------------------------------------------------------

def test_predict_from_records_averages_subject_percentages(api_real, staff, student_id, engine, registry):
    _add_records(engine, student_id)
    response = api_real.post("/api/predictions/predict", headers=staff, json={"student_id": student_id, "stage": "stage2"})
    assert response.status_code == 201, response.text
    body = response.json()
    expected_inputs = {
        ATTENDANCE: 87.5,
        INTERNAL1: round((30 / 40 * 100 + 21 / 25 * 100) / 2, 2),   # 79.5
        INTERNAL2: round((34 / 40 * 100 + 27 / 30 * 100) / 2, 2),   # 87.5
        ASSIGNMENT: round((8 / 10 * 100 + 14 / 20 * 100) / 2, 2),   # 75.0
    }
    assert body["input_source"] == "records" and body["inputs"] == expected_inputs
    assert float(body["predicted_marks"]) == _expected(registry, "stage2", expected_inputs)


def test_records_missing_internal2_blocks_stage2_but_not_stage1(api_real, staff, student_id, engine):
    _add_records(engine, student_id, with_internal2=False)
    stage2 = api_real.post("/api/predictions/predict", headers=staff, json={"student_id": student_id, "stage": "stage2"})
    assert stage2.status_code == 422
    assert stage2.json()["error"]["code"] == "insufficient_data"
    assert stage2.json()["error"]["details"]["missing"] == ["internal2 for Databases, Networks"]
    stage1 = api_real.post("/api/predictions/predict", headers=staff, json={"student_id": student_id, "stage": "stage1"})
    assert stage1.status_code == 201


def test_no_records_is_422(api_real, staff, student_id):
    response = api_real.post("/api/predictions/predict", headers=staff, json={"student_id": student_id, "stage": "stage1"})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["missing"] == ["attendance", "academic records"]


# --- history, single prediction, simulation -------------------------------------------------------

def test_history_newest_first_and_get_by_id(api_real, staff, student_id):
    ids = [api_real.post("/api/predictions/predict", headers=staff,
                         json={"student_id": student_id, "stage": s, "inputs": i}).json()["id"]
           for s, i in (("stage1", MANUAL1), ("stage2", MANUAL2))]
    history = api_real.get(f"/api/predictions/history/{student_id}", headers=staff)
    assert history.status_code == 200
    assert [p["id"] for p in history.json()["items"]] == list(reversed(ids))
    one = api_real.get(f"/api/predictions/{ids[0]}", headers=staff)
    assert one.status_code == 200 and one.json()["stage"] == "stage1"
    assert api_real.get("/api/predictions/999999", headers=staff).status_code == 404
    assert api_real.get("/api/predictions/history/999999", headers=staff).status_code == 404


def test_simulate_returns_prediction_without_saving(api_real, staff, student_id, engine):
    response = api_real.post("/api/predictions/simulate", headers=staff, json={"stage": "stage2", "inputs": MANUAL2})
    assert response.status_code == 200
    assert response.json()["simulation_only"] is True
    with Session(engine) as db:
        assert db.scalar(select(Prediction.id)) is None


# --- permissions ----------------------------------------------------------------------------------

def test_student_permissions(api_real, staff, engine):
    other = api_real.post("/api/students/", headers=staff, json={
        "roll_number": "CS9", "name": "Other", "email": "other@college.edu", "department": "CS", "semester": 7}).json()
    api_real.post("/api/auth/register", json=STUDENT)
    me = login(api_real, "CS21041")
    my_id = api_real.get("/api/students/me", headers=me).json()["id"]
    _add_records(engine, my_id)

    own = api_real.post("/api/predictions/predict", headers=me, json={"student_id": my_id, "stage": "stage2"})
    assert own.status_code == 201
    manual = api_real.post("/api/predictions/predict", headers=me,
                           json={"student_id": my_id, "stage": "stage1", "inputs": MANUAL1})
    assert manual.status_code == 403
    assert api_real.post("/api/predictions/predict", headers=me,
                         json={"student_id": other["id"], "stage": "stage1"}).status_code == 404
    assert api_real.get(f"/api/predictions/history/{my_id}", headers=me).status_code == 200
    assert api_real.get(f"/api/predictions/history/{other['id']}", headers=me).status_code == 404
    staff_made = api_real.post("/api/predictions/predict", headers=staff,
                               json={"student_id": other["id"], "stage": "stage1", "inputs": MANUAL1}).json()
    assert api_real.get(f"/api/predictions/{staff_made['id']}", headers=me).status_code == 404
    assert api_real.post("/api/predictions/simulate", headers=me,
                         json={"stage": "stage1", "inputs": MANUAL1}).status_code == 200


def test_prediction_routes_require_auth(api_real):
    assert api_real.post("/api/predictions/predict", json={"student_id": 1, "stage": "stage1"}).status_code == 401
    assert api_real.post("/api/predictions/simulate", json={"stage": "stage1", "inputs": MANUAL1}).status_code == 401
    assert api_real.get("/api/predictions/history/1").status_code == 401


# --- model availability and info ------------------------------------------------------------------

def test_missing_model_returns_503(make_client, mysql_url, engine, tmp_path):
    client = make_client(database_url=mysql_url, model_dir=tmp_path / "no_models")
    try:
        create_staff(engine)
        headers = login(client, "FAC1024")
        with Session(engine) as db:
            db.add(Student(roll_number="CS1", name="S", email="s@college.edu", department="CS", semester=7))
            db.commit()
            sid = db.scalar(select(Student.id))
        response = client.post("/api/predictions/predict", headers=headers,
                               json={"student_id": sid, "stage": "stage1", "inputs": MANUAL1})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "model_unavailable"
        assert client.post("/api/predictions/simulate", headers=headers,
                           json={"stage": "stage1", "inputs": MANUAL1}).status_code == 503
        info = client.get("/api/model-info").json()
        assert [s["loaded"] for s in info["stages"]] == [False, False]
    finally:
        from tests.conftest import empty_all_tables
        empty_all_tables(engine)


def test_model_info_reports_real_metadata(api_real):
    body = api_real.get("/api/model-info").json()
    meta = json.loads((REAL_MODELS / "stage2" / "metadata.json").read_text())
    stage2 = body["stages"][1]
    assert stage2["loaded"] and stage2["model_version"] == meta["model_version"]
    assert stage2["metrics"]["test"] == meta["metrics"]["test"]
    assert stage2["algorithm"] == "Linear Regression"
    assert body["risk_thresholds"] == {"high_below": 50.0, "medium_below": 60.0}
