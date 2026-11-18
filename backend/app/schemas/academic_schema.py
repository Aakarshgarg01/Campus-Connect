"""Schemas for academic records, attendance, targets, benchmarks, monitoring and the faculty overview."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import MonitoringStatus, PredictionStage, RiskLevel
from app.schemas.common import Department, Semester

Pct = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
MarkValue = Annotated[Decimal, Field(ge=0, max_digits=6, decimal_places=2)]
SubjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Mark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obtained: MarkValue
    maximum: Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)]

    @model_validator(mode="after")
    def obtained_within_maximum(self) -> Mark:
        if self.obtained > self.maximum:
            raise ValueError("obtained marks cannot exceed maximum marks")
        return self


class SubjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_name: SubjectName
    internal1: Mark | None = None
    internal2: Mark | None = None
    assignment: Mark | None = None


class AcademicDataIn(BaseModel):
    """Replaces the student's records for one semester with exactly these subjects."""

    model_config = ConfigDict(extra="forbid")

    semester: Semester
    attendance_percentage: Pct | None = None
    records: list[SubjectRecord] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def unique_subjects(self) -> AcademicDataIn:
        names = [r.subject_name.casefold() for r in self.records]
        if len(names) != len(set(names)):
            raise ValueError("each subject may appear only once")
        return self


class MarkOut(BaseModel):
    obtained: float
    maximum: float


class SubjectRecordOut(BaseModel):
    """Responses use plain JSON numbers (not decimal strings) for easy use in the frontend."""

    id: int
    subject_name: str
    internal1: MarkOut | None = None
    internal2: MarkOut | None = None
    assignment: MarkOut | None = None


class AcademicDataOut(BaseModel):
    student_id: int
    semester: int
    attendance_percentage: float | None
    records: list[SubjectRecordOut]


class TargetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semester: Semester | None = None
    target_percentage: Annotated[Decimal, Field(ge=1, le=100, max_digits=5, decimal_places=2)]


class TargetOut(BaseModel):
    student_id: int
    semester: int
    target_percentage: float | None


class BenchmarkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: Department
    semester: Semester
    benchmark_percentage: Pct


class BenchmarkOut(BaseModel):
    department: str
    semester: int
    benchmark_percentage: float | None
    updated_at: datetime | None = None


class MonitoringIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semester: Semester | None = None
    status: MonitoringStatus
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class MonitoringOut(BaseModel):
    student_id: int
    semester: int
    status: MonitoringStatus
    notes: str | None
    updated_at: datetime | None = None


class LatestPrediction(BaseModel):
    id: int
    stage: PredictionStage
    predicted_marks: float
    risk_level: RiskLevel
    created_at: datetime


class OverviewStudent(BaseModel):
    id: int
    roll_number: str
    name: str
    department: str
    semester: int
    attendance_percentage: float | None
    latest_prediction: LatestPrediction | None
    monitoring_status: MonitoringStatus | None
    monitoring_notes: str | None


class FacultyOverview(BaseModel):
    department: str | None
    semester: int | None
    benchmark_percentage: float | None
    total_students: int
    with_prediction: int
    below_benchmark: int | None
    risk_counts: dict[str, int]
    distribution: list[dict[str, int | str]]
    average_prediction: float | None
    students: list[OverviewStudent]
