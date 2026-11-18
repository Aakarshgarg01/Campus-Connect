"""Phase 9 backend additions: academic data, targets, benchmarks, monitoring, faculty overview."""

from __future__ import annotations

import pytest

from tests.helpers import STUDENT, create_staff, login

SUBJECTS = {
    "semester": 7,
    "attendance_percentage": 87.5,
    "records": [
        {"subject_name": "Networks", "internal1": {"obtained": 30, "maximum": 40},
         "internal2": {"obtained": 34, "maximum": 40}, "assignment": {"obtained": 8, "maximum": 10}},
        {"subject_name": "Databases", "internal1": {"obtained": 21, "maximum": 25},
         "assignment": {"obtained": 14, "maximum": 20}},
    ],
}


@pytest.fixture
def staff(api_real, engine):
    create_staff(engine)
    return login(api_real, "FAC1024")


@pytest.fixture
def student(api_real, staff):
    """A registered student (record + account) and their auth headers."""
    api_real.post("/api/auth/register", json=STUDENT)
    headers = login(api_real, "CS21041")
    return api_real.get("/api/students/me", headers=headers).json(), headers


def test_academic_data_round_trip_and_replace(api_real, staff, student):
    me, _ = student
    url = f"/api/students/{me['id']}/academic"
    saved = api_real.put(url, headers=staff, json=SUBJECTS)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["attendance_percentage"] == 87.5
    assert [r["subject_name"] for r in body["records"]] == ["Databases", "Networks"]
    assert body["records"][0]["internal2"] is None

    # Replacing: Databases removed, Networks updated, attendance cleared.
    replaced = api_real.put(url, headers=staff, json={"semester": 7, "records": [
        {"subject_name": "Networks", "internal1": {"obtained": 32, "maximum": 40}}]}).json()
    assert [r["subject_name"] for r in replaced["records"]] == ["Networks"]
    assert replaced["records"][0]["internal1"] == {"obtained": 32.0, "maximum": 40.0}
    assert replaced["attendance_percentage"] is None
    assert api_real.get(url, headers=staff).json() == replaced


def test_academic_data_feeds_records_based_prediction(api_real, staff, student):
    me, headers = student
    api_real.put(f"/api/students/{me['id']}/academic", headers=staff, json=SUBJECTS)
    own = api_real.get(f"/api/students/{me['id']}/academic", headers=headers)
    assert own.status_code == 200 and len(own.json()["records"]) == 2
    prediction = api_real.post("/api/predictions/predict", headers=headers, json={"student_id": me["id"], "stage": "stage1"})
    assert prediction.status_code == 201 and prediction.json()["input_source"] == "records"


@pytest.mark.parametrize("bad", [
    {**SUBJECTS, "records": [{"subject_name": "X", "internal1": {"obtained": 41, "maximum": 40}}]},
    {**SUBJECTS, "records": [{"subject_name": "X", "internal1": {"obtained": 1, "maximum": 0}}]},
    {**SUBJECTS, "records": [{"subject_name": "X"}, {"subject_name": "x"}]},
    {**SUBJECTS, "attendance_percentage": 120},
    {**SUBJECTS, "semester": 0},
])
def test_academic_validation(api_real, staff, student, bad):
    me, _ = student
    assert api_real.put(f"/api/students/{me['id']}/academic", headers=staff, json=bad).status_code == 422


def test_academic_permissions(api_real, staff, student):
    me, headers = student
    assert api_real.put(f"/api/students/{me['id']}/academic", headers=headers, json=SUBJECTS).status_code == 403
    other = api_real.post("/api/students/", headers=staff, json={
        "roll_number": "CS9", "name": "Other", "email": "o@college.edu", "department": "CS", "semester": 7}).json()
    assert api_real.get(f"/api/students/{other['id']}/academic", headers=headers).status_code == 404


def test_targets_are_set_by_the_student(api_real, staff, student):
    me, headers = student
    url = f"/api/students/{me['id']}/target"
    assert api_real.get(url, headers=headers).json()["target_percentage"] is None
    assert api_real.put(url, headers=headers, json={"target_percentage": 80}).json()["target_percentage"] == 80.0
    assert api_real.put(url, headers=headers, json={"target_percentage": 85.5}).json()["target_percentage"] == 85.5
    assert api_real.get(url, headers=staff).json()["target_percentage"] == 85.5  # staff can read
    assert api_real.put(url, headers=staff, json={"target_percentage": 50}).status_code == 403
    assert api_real.put(url, headers=headers, json={"target_percentage": 0}).status_code == 422


def test_benchmark_set_and_read(api_real, staff, student):
    _, headers = student
    query = "/api/benchmarks?department=Computer%20Science&semester=7"
    assert api_real.get(query, headers=staff).json()["benchmark_percentage"] is None
    saved = api_real.put("/api/benchmarks", headers=staff,
                         json={"department": "Computer Science", "semester": 7, "benchmark_percentage": 70})
    assert saved.status_code == 200 and saved.json()["benchmark_percentage"] == 70.0
    assert api_real.get(query, headers=headers).json()["benchmark_percentage"] == 70.0  # students may read
    assert api_real.put("/api/benchmarks", headers=headers,
                        json={"department": "Computer Science", "semester": 7, "benchmark_percentage": 10}).status_code == 403


def test_monitoring_defaults_and_updates(api_real, staff, student):
    me, headers = student
    url = f"/api/students/{me['id']}/monitoring"
    assert api_real.get(url, headers=staff).json()["status"] == "Not Contacted"
    saved = api_real.put(url, headers=staff, json={"status": "Counselling Done", "notes": "  Met on Monday.  "})
    assert saved.json()["status"] == "Counselling Done" and saved.json()["notes"] == "Met on Monday."
    assert api_real.put(url, headers=staff, json={"status": "Ignored"}).status_code == 422
    assert api_real.get(url, headers=headers).status_code == 403  # follow-up notes are staff-only


def test_faculty_overview_counts_real_predictions(api_real, staff):
    ids = []
    for i, inputs in enumerate([
        {"attendance": 95, "internal1": 95, "internal2": 95, "assignment": 90},   # low risk
        {"attendance": 78, "internal1": 70, "internal2": 70, "assignment": 70},   # medium
        {"attendance": 65, "internal1": 55, "internal2": 55, "assignment": 50},   # high
    ]):
        sid = api_real.post("/api/students/", headers=staff, json={
            "roll_number": f"CS{i}", "name": f"S{i}", "email": f"s{i}@college.edu",
            "department": "Computer Science", "semester": 7}).json()["id"]
        ids.append(sid)
        api_real.post("/api/predictions/predict", headers=staff, json={"student_id": sid, "stage": "stage2", "inputs": inputs})
    api_real.post("/api/students/", headers=staff, json={
        "roll_number": "CS9", "name": "No prediction", "email": "s9@college.edu", "department": "Computer Science", "semester": 7})
    api_real.put("/api/benchmarks", headers=staff, json={"department": "Computer Science", "semester": 7, "benchmark_percentage": 70})

    body = api_real.get("/api/faculty/overview?department=Computer%20Science&semester=7", headers=staff).json()
    predicted = [float(s["latest_prediction"]["predicted_marks"]) for s in body["students"] if s["latest_prediction"]]
    assert body["total_students"] == 4 and body["with_prediction"] == 3
    assert body["risk_counts"] == {"high": 1, "medium": 1, "low": 1}
    assert body["below_benchmark"] == sum(1 for v in predicted if v < 70)
    assert sum(b["count"] for b in body["distribution"]) == 3
    assert body["average_prediction"] == round(sum(predicted) / 3, 2)
    assert api_real.get("/api/faculty/overview", headers=staff).json()["below_benchmark"] is None


def test_overview_is_staff_only(api_real, student):
    _, headers = student
    assert api_real.get("/api/faculty/overview", headers=headers).status_code == 403
