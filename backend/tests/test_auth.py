"""Phase 5: registration, login, JWT validation (valid / invalid / expired), roles, rate limit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import Student, User, UserRole
from tests.conftest import TEST_SECRET
from tests.helpers import PASSWORD, STUDENT, create_staff, login


# --- registration ----------------------------------------------------------------------------

def test_register_creates_student_account_with_hashed_password(api, engine):
    response = api.post("/api/auth/register", json=STUDENT)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "student"
    assert body["email"] == "asha.verma@college.edu"  # normalised
    assert body["roll_number"] == "CS21041"  # normalised
    assert "password" not in response.text and "hashed" not in response.text
    with Session(engine) as db:
        stored = db.scalar(select(User.hashed_password).where(User.email == "asha.verma@college.edu"))
    assert stored.startswith("$argon2id$") and PASSWORD not in stored


def test_register_links_existing_student_record_when_email_matches(api, engine):
    with Session(engine) as db:
        db.add(Student(roll_number="CS21041", name="Asha Verma", email="asha.verma@college.edu",
                       department="Computer Science", semester=7))
        db.commit()
    response = api.post("/api/auth/register", json=STUDENT)
    assert response.status_code == 201
    with Session(engine) as db:
        assert db.scalar(select(Student.user_id).where(Student.roll_number == "CS21041")) == response.json()["id"]


def test_register_rejects_claiming_someone_elses_roll_number(api, engine):
    with Session(engine) as db:
        db.add(Student(roll_number="CS21041", name="Real Owner", email="owner@college.edu",
                       department="Computer Science", semester=7))
        db.commit()
    response = api.post("/api/auth/register", json=STUDENT)
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Roll number and email do not match the student record."


def test_register_duplicate_email_conflicts(api):
    assert api.post("/api/auth/register", json=STUDENT).status_code == 201
    again = api.post("/api/auth/register", json={**STUDENT, "roll_number": "CS99999"})
    assert again.status_code == 409


def test_register_validation_errors_are_422(api):
    bad = {**STUDENT, "email": "not-an-email", "password": "short", "semester": 0, "role": "admin"}
    response = api.post("/api/auth/register", json=bad)
    assert response.status_code == 422
    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert {"body.email", "body.password", "body.semester", "body.role"} <= fields


def test_register_cannot_create_staff(api):
    response = api.post("/api/auth/register", json={**STUDENT, "role": "faculty"})
    assert response.status_code == 422  # extra fields are forbidden; role is always student


# --- login -----------------------------------------------------------------------------------

def test_login_with_email_roll_number_and_employee_id(api, engine):
    api.post("/api/auth/register", json=STUDENT)
    create_staff(engine)
    for identifier in ("asha.verma@college.edu", "cs21041", "fac1024", "FACULTY@college.edu"):
        response = api.post("/api/auth/login", json={"identifier": identifier, "password": PASSWORD})
        assert response.status_code == 200, identifier
        body = response.json()
        assert body["token_type"] == "bearer" and body["expires_in"] == 3600
        cookie = response.headers["set-cookie"]
        assert "access_token=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie


def test_login_failures_share_one_message(api, engine):
    create_staff(engine)
    wrong_password = api.post("/api/auth/login", json={"identifier": "FAC1024", "password": "Wrong12345"})
    unknown_user = api.post("/api/auth/login", json={"identifier": "nobody@x.edu", "password": "Wrong12345"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown_user.json()["error"]["message"] == "Invalid credentials."


def test_inactive_user_cannot_log_in(api, engine):
    create_staff(engine, active=False)
    assert api.post("/api/auth/login", json={"identifier": "FAC1024", "password": PASSWORD}).status_code == 401


def test_login_rate_limited_after_five_attempts(api, engine):
    create_staff(engine)
    codes = [api.post("/api/auth/login", json={"identifier": "FAC1024", "password": "Wrong12345"}).status_code
             for _ in range(6)]
    assert codes == [401] * 5 + [429]
    blocked = api.post("/api/auth/login", json={"identifier": "FAC1024", "password": PASSWORD})
    assert blocked.status_code == 429  # even the right password is blocked during the window
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.headers["retry-after"] == "60"


# --- tokens ----------------------------------------------------------------------------------

def test_me_with_valid_token_and_with_cookie(api, engine):
    create_staff(engine)
    login_response = api.post("/api/auth/login", json={"identifier": "FAC1024", "password": PASSWORD})
    token = login_response.json()["access_token"]
    via_cookie = api.get("/api/auth/me")  # TestClient kept the httpOnly cookie
    assert via_cookie.status_code == 200 and via_cookie.json()["employee_id"] == "FAC1024"
    api.cookies.clear()
    via_header = api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert via_header.status_code == 200 and via_header.json()["role"] == "faculty"


def test_missing_token_is_401(api):
    response = api.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_is_401(api, engine):
    user = create_staff(engine)
    token, _ = create_access_token(user, expires_delta=timedelta(seconds=-1))
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_tampered_and_wrong_secret_tokens_are_401(api, engine):
    user = create_staff(engine)
    now = datetime.now(UTC)
    claims = {"sub": str(user.id), "role": "admin", "iat": now, "exp": now + timedelta(hours=1)}
    forged = jwt.encode(claims, "a-different-secret-" + "y" * 40, algorithm="HS256")
    unsigned = jwt.encode(claims, key=None, algorithm="none")
    good, _ = create_access_token(user)
    tampered = good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB")
    for token in (forged, unsigned, tampered, "not.a.jwt"):
        assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_for_deleted_user_is_401(api, engine):
    user = create_staff(engine)
    token, _ = create_access_token(user)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_role_claim_in_token_is_not_trusted(api, engine):
    """Role comes from the database, so a valid token can't be used to escalate."""
    api.post("/api/auth/register", json=STUDENT)
    headers = login(api, "CS21041")
    payload = jwt.decode(headers["Authorization"][7:], TEST_SECRET, algorithms=["HS256"])
    assert payload["role"] == "student"
    assert api.get("/api/students/", headers=headers).status_code == 403


def test_logout_clears_cookie(api, engine):
    create_staff(engine)
    api.post("/api/auth/login", json={"identifier": "FAC1024", "password": PASSWORD})
    response = api.post("/api/auth/logout")
    assert response.status_code == 204
    assert 'access_token=""' in response.headers["set-cookie"] and "Max-Age=0" in response.headers["set-cookie"]
    assert api.get("/api/auth/me").status_code == 401


def test_admin_role_value(engine, api):
    create_staff(engine, UserRole.ADMIN, email="admin@college.edu", employee_id="ADM1")
    headers = login(api, "ADM1")
    assert api.get("/api/auth/me", headers=headers).json()["role"] == "admin"
