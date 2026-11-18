"""Load, validate and prepare Final_Marks_Data.csv. The source file is never modified.

Raw columns -> model features:
  Attendance (%)                  -> attendance_pct   (already 0-100)
  Internal Test 1 (out of 40)     -> internal1_pct    (x / 40 * 100)
  Internal Test 2 (out of 40)     -> internal2_pct    (x / 40 * 100)
  Assignment Score (out of 10)    -> assignment_pct   (x / 10 * 100)
  Final Exam Marks (out of 100)   -> final_exam_pct   (target, already 0-100)
Excluded: Student_ID (identifier) and Daily Study Hours (excluded by project decision:
self-reported, and the app's roadmap rules it out as a model input).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from app.ml.features import ASSIGNMENT, ATTENDANCE, INTERNAL1, INTERNAL2, TARGET

DATA_PATH = Path(__file__).resolve().parent / "data" / "Final_Marks_Data.csv"

STUDENT_ID = "Student_ID"
RAW_ATTENDANCE = "Attendance (%)"
RAW_INTERNAL1 = "Internal Test 1 (out of 40)"
RAW_INTERNAL2 = "Internal Test 2 (out of 40)"
RAW_ASSIGNMENT = "Assignment Score (out of 10)"
RAW_STUDY_HOURS = "Daily Study Hours"
RAW_FINAL = "Final Exam Marks (out of 100)"

EXPECTED_COLUMNS = [STUDENT_ID, RAW_ATTENDANCE, RAW_INTERNAL1, RAW_INTERNAL2, RAW_ASSIGNMENT, RAW_STUDY_HOURS, RAW_FINAL]
RAW_RANGES = {
    RAW_ATTENDANCE: (0, 100),
    RAW_INTERNAL1: (0, 40),
    RAW_INTERNAL2: (0, 40),
    RAW_ASSIGNMENT: (0, 10),
    RAW_STUDY_HOURS: (0, 24),
    RAW_FINAL: (0, 100),
}
EXCLUDED_COLUMNS = {STUDENT_ID: "identifier", RAW_STUDY_HOURS: "excluded by project decision"}


def file_sha256(path: Path = DATA_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(data: pd.DataFrame) -> list[str]:
    """Return every problem found; an empty list means the data is valid."""
    problems: list[str] = []
    missing = [c for c in EXPECTED_COLUMNS if c not in data.columns]
    extra = [c for c in data.columns if c not in EXPECTED_COLUMNS]
    if missing:
        return [f"missing columns: {missing}"]
    if extra:
        problems.append(f"unexpected columns: {extra}")
    if data.isna().any().any():
        problems.append(f"missing values: {data.isna().sum()[lambda s: s > 0].to_dict()}")
    if data[STUDENT_ID].duplicated().any():
        problems.append(f"duplicate Student_ID values: {int(data[STUDENT_ID].duplicated().sum())}")
    for column, (low, high) in RAW_RANGES.items():
        values = pd.to_numeric(data[column], errors="coerce")
        if values.isna().any():
            problems.append(f"non-numeric values in {column}: {int(values.isna().sum())}")
        elif ((values < low) | (values > high)).any():
            problems.append(f"values outside [{low}, {high}] in {column}: {int(((values < low) | (values > high)).sum())}")
    return problems


def load_raw(path: Path = DATA_PATH) -> pd.DataFrame:
    data = pd.read_csv(path)
    problems = validate(data)
    if problems:
        raise ValueError("Dataset validation failed:\n- " + "\n- ".join(problems))
    return data


def prepare(data: pd.DataFrame) -> pd.DataFrame:
    """Raw marks -> percentage features + target (the only transformation outside the Pipeline)."""
    return pd.DataFrame(
        {
            ATTENDANCE: data[RAW_ATTENDANCE].astype(float),
            INTERNAL1: data[RAW_INTERNAL1] / 40 * 100,
            INTERNAL2: data[RAW_INTERNAL2] / 40 * 100,
            ASSIGNMENT: data[RAW_ASSIGNMENT] / 10 * 100,
            TARGET: data[RAW_FINAL].astype(float),
        },
        index=data.index,
    )
