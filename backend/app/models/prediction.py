"""predictions: every prediction made, with the exact inputs, SHAP explanation and model version.

Rows are immutable history (no updated_at). They are deleted with their student (CASCADE).
"""

from __future__ import annotations

import enum
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, Percent, enum_column

if TYPE_CHECKING:
    from app.models.student import Student


class PredictionStage(str, enum.Enum):
    STAGE1 = "stage1"  # attendance, Internal 1, assignment
    STAGE2 = "stage2"  # + Internal 2


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Prediction(CreatedAtMixin, Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("semester BETWEEN 1 AND 12", name="semester_range"),
        CheckConstraint("predicted_marks BETWEEN 0 AND 100", name="predicted_marks_range"),
        Index("ix_predictions_student_semester_created", "student_id", "semester", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stage: Mapped[PredictionStage] = mapped_column(
        enum_column(PredictionStage, "prediction_stage"), nullable=False
    )
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    predicted_marks: Mapped[Decimal] = mapped_column(Percent, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(enum_column(RiskLevel, "risk_level"), nullable=False)
    shap_explanation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Summary + recommendations generated from the inputs and SHAP values (Phase 8).
    recommendations: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    student: Mapped[Student] = relationship(back_populates="predictions")
