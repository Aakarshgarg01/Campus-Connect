"""Inspect and validate the CampusConnect source dataset."""

from pathlib import Path
import sys

import pandas as pd

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from preprocessing.pipeline import EXPECTED_COLUMNS, RANGES, STUDENT_ID, validate_dataset  # noqa: E402


def main() -> int:
    csv_path = SERVICE_ROOT / "data" / "Final_Marks_Data.csv"
    data = pd.read_csv(csv_path)
    print(f"File path: {csv_path}")
    print(f"Rows: {len(data)}")
    print(f"Columns: {len(data.columns)}")
    print(f"Exact column names: {list(data.columns)}")
    print("Data types:")
    print(data.dtypes.to_string())
    print("Missing values by column:")
    print(data.isna().sum().to_string())
    print(f"Duplicate rows: {int(data.duplicated().sum())}")
    print(f"Unique Student_ID values: {data[STUDENT_ID].nunique()}")
    numeric = data.select_dtypes(include="number")
    print("Minimum values:")
    print(numeric.min().to_string())
    print("Maximum values:")
    print(numeric.max().to_string())
    print("Mean:")
    print(numeric.mean().to_string())
    print("Median:")
    print(numeric.median().to_string())
    print("Standard deviation:")
    print(numeric.std().to_string())
    print("Basic descriptive statistics:")
    print(data.describe(include="all").to_string())
    print("\nRange checks:")
    for column, (minimum, maximum) in RANGES.items():
        values = pd.to_numeric(data[column], errors="coerce")
        valid = bool(values.notna().all() and values.between(minimum, maximum).all())
        print(f"{column}: expected {minimum}-{maximum}, valid={valid}")
    print("Daily Study Hours: excluded from modeling")

    findings = validate_dataset(data)
    if findings:
        print("\nValidation findings:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("\nValidation: passed; no unexpected values found.")
    print(f"Required schema: {list(EXPECTED_COLUMNS) == list(data.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())