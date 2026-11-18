"""Phase 5: student CRUD, role checks, validation and database error handling."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.models import UserRole
from tests.helpers import STUDENT, create_staff, login

NEW = {"roll_number": "cs21050", "name": "Ravi Kumar", "email": "Ravi@College.edu",
       "department": "Computer Science", "semester": 5}


@pytest.fixture
def staff(api, engine):
    create_staff(engine)
    return login(api, "FAC1024")


def _create(api, headers, **overrides):
    response = api.post("/api/students/", json={**NEW, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_full_crud_cycle(api, staff):
    created = _create(api, staff)
    assert created["roll_number"] == "CS21050" and created["email"] == "ravi@college.edu"
    assert created["has_account"] is False

    fetched = api.get(f"/api/students/{created['id']}", headers=staff)
    assert fetched.status_code == 200 and fetched.json() == created

    updated = api.put(f"/api/students/{created['id']}", json={"semester": 6, "name": "Ravi K."}, headers=staff)
    assert updated.status_code == 200
    assert updated.json()["semester"] == 6 and updated.json()["name"] == "Ravi K."
    assert updated.json()["roll_number"] == "CS21050"  # untouched fields kept

    deleted = api.delete(f"/api/students/{created['id']}", headers=staff)
    assert deleted.status_code == 204 and deleted.content == b""
    assert api.get(f"/api/students/{created['id']}", headers=staff).status_code == 404


def test_list_search_filter_and_paginate(api, staff):
    _create(api, staff)
    _create(api, staff, roll_number="CS21051", email="meera@college.edu", name="Meera Iyer", semester=7)
    _create(api, staff, roll_number="EC10001", email="kabir@college.edu", name="Kabir Shah", department="Electronics")

    everyone = api.get("/api/students/", headers=staff).json()
    assert everyone["total"] == 3 and [s["roll_number"] for s in everyone["items"]] == ["CS21050", "CS21051", "EC10001"]
    assert api.get("/api/students/?search=meera", headers=staff).json()["total"] == 1
    assert api.get("/api/students/?search=%25", headers=staff).json()["total"] == 0  # % is literal
    assert api.get("/api/students/?department=Electronics", headers=staff).json()["total"] == 1
    assert api.get("/api/students/?semester=7", headers=staff).json()["total"] == 1
    page = api.get("/api/students/?limit=2&offset=2", headers=staff).json()
    assert page["total"] == 3 and len(page["items"]) == 1


def test_duplicates_conflict(api, staff):
    _create(api, staff)
    assert api.post("/api/students/", json={**NEW, "email": "other@college.edu"}, headers=staff).status_code == 409
    assert api.post("/api/students/", json={**NEW, "roll_number": "CS1"}, headers=staff).status_code == 409
    second = _create(api, staff, roll_number="CS21051", email="meera@college.edu")
    clash = api.put(f"/api/students/{second['id']}", json={"roll_number": "CS21050"}, headers=staff)
    assert clash.status_code == 409


def test_invalid_inputs_are_422(api, staff):
    cases = [
        {**NEW, "semester": 13},
        {**NEW, "email": "nope"},
        {**NEW, "roll_number": "bad roll!"},
        {**NEW, "name": "   "},
        {**NEW, "attendance": 90},  # unknown field
        {k: v for k, v in NEW.items() if k != "department"},
    ]
    for body in cases:
        response = api.post("/api/students/", json=body, headers=staff)
        assert response.status_code == 422, body
        assert response.json()["error"]["code"] == "validation_error"
    assert api.put("/api/students/1", json={}, headers=staff).status_code == 422
    assert api.put("/api/students/1", json={"name": None}, headers=staff).status_code == 422
    assert api.get("/api/students/abc", headers=staff).status_code == 422
    assert api.get("/api/students/?limit=500", headers=staff).status_code == 422


def test_missing_student_is_404(api, staff):
    assert api.get("/api/students/999999", headers=staff).status_code == 404
    assert api.put("/api/students/999999", json={"semester": 3}, headers=staff).status_code == 404
    assert api.delete("/api/students/999999", headers=staff).status_code == 404


def test_requires_authentication(api):
    assert api.get("/api/students/").status_code == 401
    assert api.post("/api/students/", json=NEW).status_code == 401
    assert api.delete("/api/students/1").status_code == 401


def test_student_role_permissions(api, staff):
    other = _create(api, staff)
    api.post("/api/auth/register", json=STUDENT)
    me = login(api, "CS21041")

    own = api.get("/api/students/me", headers=me)
    assert own.status_code == 200 and own.json()["roll_number"] == "CS21041" and own.json()["has_account"]
    assert api.get(f"/api/students/{own.json()['id']}", headers=me).status_code == 200
    assert api.get(f"/api/students/{other['id']}", headers=me).status_code == 404  # can't see others
    assert api.get("/api/students/", headers=me).status_code == 403
    assert api.post("/api/students/", json={**NEW, "roll_number": "CS3"}, headers=me).status_code == 403
    assert api.put(f"/api/students/{own.json()['id']}", json={"semester": 8}, headers=me).status_code == 403
    assert api.delete(f"/api/students/{own.json()['id']}", headers=me).status_code == 403


def test_admin_can_manage_students(api, engine):
    create_staff(engine, UserRole.ADMIN, email="admin@college.edu", employee_id="ADM1")
    admin = login(api, "ADM1")
    created = _create(api, admin)
    assert api.delete(f"/api/students/{created['id']}", headers=admin).status_code == 204


def test_delete_cascades_related_records(api, staff, engine):
    created = _create(api, staff)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO attendance (student_id, semester, attendance_percentage, created_at, updated_at) "
            "VALUES (:id, 5, :pct, UTC_TIMESTAMP(), UTC_TIMESTAMP())"), {"id": created["id"], "pct": Decimal("88")})
    assert api.delete(f"/api/students/{created['id']}", headers=staff).status_code == 204
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM attendance")).scalar_one() == 0


def test_database_outage_returns_clean_500(api, staff, monkeypatch):
    """A DB failure mid-request is logged but returns the standard error body, no internals."""
    from sqlalchemy.orm import Session

    def broken(*args, **kwargs):
        raise OperationalError("SELECT ...", {}, Exception("Lost connection to MySQL server sp_app@127.0.0.1"))

    monkeypatch.setattr(Session, "scalar", broken)
    response = api.post("/api/students/", json=NEW, headers=staff)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "MySQL" not in response.text and "sp_app" not in response.text
