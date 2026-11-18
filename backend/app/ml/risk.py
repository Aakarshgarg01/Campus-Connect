"""Risk level from the predicted final-exam percentage.

These thresholds are a documented policy choice, not something the model learned:
  high    predicted < 50   (default RISK_HIGH_BELOW)   - the bottom ~10% of this dataset
                                                        (188 of 2000 students, 9.4%, scored < 50)
  medium  50 <= predicted < 60 (RISK_MEDIUM_BELOW)     - within about one Stage 1 RMSE (~6 marks)
                                                        of the high-risk line
  low     predicted >= 60
Both thresholds are configurable in .env so an institution can align them with its own
pass marks and benchmarks.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.models import RiskLevel


def risk_level(predicted: float) -> RiskLevel:
    settings = get_settings()
    if predicted < settings.risk_high_below:
        return RiskLevel.HIGH
    if predicted < settings.risk_medium_below:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def thresholds() -> dict[str, float]:
    settings = get_settings()
    return {"high_below": settings.risk_high_below, "medium_below": settings.risk_medium_below}
