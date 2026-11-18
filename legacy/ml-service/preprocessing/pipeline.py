"""Deterministic validation and percentage-based feature preparation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

STUDENT_ID = "Student_ID"
ATTENDANCE = "Attendance (%)"
INTERNAL1_RAW = "Internal Test 1 (out of 40)"
INTERNAL2_RAW = "Internal Test 2 (out of 40)"
ASSIGNMENT_RAW = "Assignment Score (out of 10)"
DAILY_STUDY_HOURS = "Daily Study Hours"
FINAL_MARKS = "Final Exam Marks (out of 100)"

INTERNAL1_PERCENT = "Internal Test 1 (%)"
INTERNAL2_PERCENT = "Internal Test 2 (%)"
ASSIGNMENT_PERCENT = "Assignment (%)"
TARGET = "Final Exam Marks (%)"

STAGE1_FEATURES = [ATTENDANCE, INTERNAL1_PERCENT, ASSIGNMENT_PERCENT]
STAGE2_FEATURES = [ATTENDANCE, INTERNAL1_PERCENT, INTERNAL2_PERCENT, ASSIGNMENT_PERCENT]
EXPECTED_COLUMNS = [
    STUDENT_ID,
    ATTENDANCE,
    INTERNAL1_RAW,
    INTERNAL2_RAW,
    ASSIGNMENT_RAW,
    DAILY_STUDY_HOURS,
    FINAL_MARKS,
]
NUMERIC_COLUMNS = [
    ATTENDANCE,
    INTERNAL1_RAW,
    INTERNAL2_RAW,
    ASSIGNMENT_RAW,
    DAILY_STUDY_HOURS,
    FINAL_MARKS,
]
RANGES = {
    ATTENDANCE: (0, 100),
    INTERNAL1_RAW: (0, 40),
    INTERNAL2_RAW: (0, 40),
    ASSIGNMENT_RAW: (0, 10),
    FINAL_MARKS: (0, 100),
}


def validate_dataset(data: pd.DataFrame) -> list[str]:
    """Return all validation findings; valid data produces an empty list."""
    findings: list[str] = []
    missing_columns = [column for column in EXPECTED_COLUMNS if column not in data.columns]
    unexpected_columns = [column for column in data.columns if column not in EXPECTED_COLUMNS]
    if missing_columns:
        findings.append(f"Missing required columns: {missing_columns}")
    if unexpected_columns:
        findings.append(f"Unexpected columns: {unexpected_columns}")
    if missing_columns:
        return findings

    if data.isna().any().any():
        findings.append(f"Missing values by column: {data.isna().sum().to_dict()}")
    duplicate_rows = int(data.duplicated().sum())
    if duplicate_rows:
        findings.append(f"Duplicate rows: {duplicate_rows}")
    duplicate_ids = int(data[STUDENT_ID].duplicated().sum())
    if duplicate_ids:
        findings.append(f"Duplicate Student_ID values: {duplicate_ids}")

    for column in NUMERIC_COLUMNS:
        numeric_values = pd.to_numeric(data[column], errors="coerce")
        non_numeric = int(numeric_values.isna().sum())
        if non_numeric:
            findings.append(f"Non-numeric values in {column}: {non_numeric}")
            continue
        minimum, maximum = RANGES.get(column, (None, None))
        if minimum is not None:
            below = int((numeric_values < minimum).sum())
            above = int((numeric_values > maximum).sum())
            if below:
                findings.append(f"Values below {minimum} in {column}: {below}")
            if above:
                findings.append(f"Values above {maximum} in {column}: {above}")
    return findings


def load_validated_dataset(csv_path: str | Path) -> pd.DataFrame:
    """Load the CSV and reject invalid data without modifying the source file."""
    data = pd.read_csv(csv_path)
    findings = validate_dataset(data)
    if findings:
        details = "\n".join(f"- {finding}" for finding in findings)
        raise ValueError(f"Dataset validation failed; no records were changed:\n{details}")
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column])
    return data


def prepare_features(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Convert raw marks to percentages and return all model-ready features."""
    prepared = pd.DataFrame(index=data.index)
    prepared[ATTENDANCE] = data[ATTENDANCE]
    prepared[INTERNAL1_PERCENT] = data[INTERNAL1_RAW] / 40 * 100
    prepared[INTERNAL2_PERCENT] = data[INTERNAL2_RAW] / 40 * 100
    prepared[ASSIGNMENT_PERCENT] = data[ASSIGNMENT_RAW] / 10 * 100
    target = data[FINAL_MARKS].rename(TARGET)
    return prepared, target