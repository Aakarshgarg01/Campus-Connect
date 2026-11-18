"""Request/response models for student CRUD."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.common import Department, Email, Name, RollNumber, Semester


class StudentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roll_number: RollNumber
    name: Name
    email: Email
    department: Department
    semester: Semester


class StudentUpdate(BaseModel):
    """PUT body: send only the fields to change (at least one)."""

    model_config = ConfigDict(extra="forbid")

    roll_number: RollNumber | None = None
    name: Name | None = None
    email: Email | None = None
    department: Department | None = None
    semester: Semester | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> StudentUpdate:
        if not self.model_fields_set:
            raise ValueError("provide at least one field to update")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("fields cannot be set to null")
        return self


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    roll_number: str
    name: str
    email: str
    department: str
    semester: int
    has_account: bool
    created_at: datetime
    updated_at: datetime


class StudentList(BaseModel):
    items: list[StudentOut]
    total: int
    limit: int
    offset: int
