"""Single source of truth for model features, shared by training and the API.

The API receives percentages (0-100). Training converts the dataset's raw marks to the same
percentages with obtained / maximum * 100, so both sides feed the pipeline identical inputs.
"""

from __future__ import annotations

ATTENDANCE = "attendance_pct"
INTERNAL1 = "internal1_pct"
INTERNAL2 = "internal2_pct"
ASSIGNMENT = "assignment_pct"

STAGE_FEATURES: dict[str, list[str]] = {
    # Stage 1 is predicted before Internal 2 exists, so it must never see Internal 2 (leakage).
    "stage1": [ATTENDANCE, INTERNAL1, ASSIGNMENT],
    "stage2": [ATTENDANCE, INTERNAL1, INTERNAL2, ASSIGNMENT],
}

FEATURE_LABELS = {
    ATTENDANCE: "Attendance",
    INTERNAL1: "Internal Test 1",
    INTERNAL2: "Internal Test 2",
    ASSIGNMENT: "Assignment",
}

TARGET = "final_exam_pct"
TARGET_LABEL = "Final exam marks (%)"
