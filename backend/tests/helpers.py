"""Helpers shared by API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserRole

PASSWORD = "Campus2026pass"
STUDENT = {
    "name": "Asha Verma",
    "email": "Asha.Verma@College.edu",
    "password": PASSWORD,
    "roll_number": "cs21041",
    "department": "Computer Science",
    "semester": 7,
}


def create_staff(engine: Engine, role: UserRole = UserRole.FACULTY, *, email: str = "faculty@college.edu",
                 employee_id: str = "FAC1024", active: bool = True) -> User:
    with Session(engine, expire_on_commit=False) as db:
        user = User(name="Dr. Faculty", email=email, employee_id=employee_id, role=role,
                    department="Computer Science", hashed_password=hash_password(PASSWORD), is_active=active)
        db.add(user)
        db.commit()
        return user


def login(client: TestClient, identifier: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert response.status_code == 200, response.text
    client.cookies.clear()  # tests authenticate explicitly with the Bearer header
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
