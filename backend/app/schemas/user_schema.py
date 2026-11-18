"""Request/response models for registration, login and the current user."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import UserRole
from app.schemas.common import Department, Email, Name, RollNumber, Semester


def _password_policy(value: str) -> str:
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("must contain at least one letter and one digit")
    return value


Password = Annotated[str, Field(min_length=8, max_length=128), AfterValidator(_password_policy)]


class RegisterRequest(BaseModel):
    """Student self-registration. Faculty/admin accounts are created by an admin (CLI)."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    email: Email
    password: Password
    roll_number: RollNumber
    department: Department
    semester: Semester


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)] = Field(
        description="Email, student roll number or staff employee ID"
    )
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: UserRole
    employee_id: str | None
    department: str | None
    student_id: int | None = None
    roll_number: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")
    user: UserOut
