"""Exploratory data analysis. Writes reports/eda_report.md and reports/eda_summary.json.

Run from backend/:  python -m ml_training.eda
Every number in the report is computed here from the CSV; nothing is typed in by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.features import ASSIGNMENT, ATTENDANCE, FEATURE_LABELS, INTERNAL1, INTERNAL2, TARGET
from ml_training.dataset import (
    DATA_PATH,
    EXCLUDED_COLUMNS,
    RAW_FINAL,
    RAW_STUDY_HOURS,
    STUDENT_ID,
    file_sha256,
    load_raw,
    prepare,
)

REPORTS = Path(__file__).resolve().parent / "reports"
FEATURES = [ATTENDANCE, INTERNAL1, INTERNAL2, ASSIGNMENT]


def _vif(frame: pd.DataFrame) -> dict[str, float]:
    """Variance inflation factor: 1 / (1 - R²) of each feature regressed on the others."""
    result = {}
    for column in frame.columns:
        y = frame[column].to_numpy()
        x = np.column_stack([np.ones(len(frame)), frame.drop(columns=column).to_numpy()])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        r2 = 1 - ((y - x @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        result[column] = float(1 / (1 - r2))
    return result


def analyse() -> dict:
    raw = load_raw()
    data = prepare(raw)
    numeric_raw = raw.drop(columns=STUDENT_ID)

    feature_rows = raw.drop(columns=STUDENT_ID)
    dup_feature_mask = feature_rows.duplicated(keep=False)
    dup_with_target = raw.drop(columns=[STUDENT_ID, RAW_FINAL]).duplicated(keep=False)
    conflicting = raw[dup_with_target].groupby(
        list(raw.drop(columns=[STUDENT_ID, RAW_FINAL]).columns))[RAW_FINAL].nunique()

    q1, q3 = numeric_raw.quantile(0.25), numeric_raw.quantile(0.75)
    iqr = q3 - q1
    outliers = ((numeric_raw < q1 - 1.5 * iqr) | (numeric_raw > q3 + 1.5 * iqr)).sum()

    target = data[TARGET]
    # Top edge 100.01 so a mark of exactly 100 is counted (right=False makes intervals [a, b)).
    bins = pd.cut(target, bins=[0, 40, 50, 60, 70, 80, 90, 100.01], right=False)
    assert bins.notna().all(), "every target value must fall in a histogram band"
    attendance_bands = pd.cut(data[ATTENDANCE], bins=[0, 75, 80, 85, 90, 95, 100.01], right=False)

    return {
        "dataset": {
            "path": str(DATA_PATH.relative_to(DATA_PATH.parents[2])),
            "sha256": file_sha256(),
            "rows": int(len(raw)),
            "columns": list(raw.columns),
            "dtypes": {c: str(t) for c, t in raw.dtypes.items()},
            "excluded_columns": EXCLUDED_COLUMNS,
            "provenance": "unknown (source and licence not documented in the repository)",
        },
        "quality": {
            "missing_values_total": int(raw.isna().sum().sum()),
            "duplicate_student_ids": int(raw[STUDENT_ID].duplicated().sum()),
            "exact_duplicate_rows_excluding_id": int(feature_rows.duplicated().sum()),
            "rows_in_duplicate_groups_excluding_id": int(dup_feature_mask.sum()),
            "identical_inputs_with_different_targets_groups": int((conflicting > 1).sum()),
            "all_values_integers": bool((numeric_raw % 1 == 0).all().all()),
            "iqr_outliers_per_column": {c: int(v) for c, v in outliers.items()},
        },
        "describe_raw": json.loads(numeric_raw.describe().round(3).to_json()),
        "describe_features": json.loads(data.describe().round(3).to_json()),
        "target": {
            "mean": round(float(target.mean()), 3),
            "median": float(target.median()),
            "std": round(float(target.std()), 3),
            "skew": round(float(target.skew()), 3),
            "min": float(target.min()),
            "max": float(target.max()),
            "share_below_40": round(float((target < 40).mean()), 4),
            "histogram": {str(k): int(v) for k, v in bins.value_counts(sort=False).items()},
        },
        "correlation_with_target": {
            "pearson": {c: round(float(numeric_raw[c].corr(numeric_raw[RAW_FINAL])), 3)
                        for c in numeric_raw.columns if c != RAW_FINAL},
            "spearman": {c: round(float(numeric_raw[c].corr(numeric_raw[RAW_FINAL], method="spearman")), 3)
                         for c in numeric_raw.columns if c != RAW_FINAL},
        },
        "feature_correlation_matrix": json.loads(data[FEATURES].corr().round(3).to_json()),
        "vif": {c: round(v, 3) for c, v in _vif(data[FEATURES]).items()},
        "target_mean_by_attendance_band": {
            str(k): {"n": int(g.size), "mean_final": round(float(g.mean()), 2)}
            for k, g in data.groupby(attendance_bands, observed=True)[TARGET]
        },
        "study_hours_note": {
            "pearson_with_target": round(float(raw[RAW_STUDY_HOURS].corr(raw[RAW_FINAL])), 3),
            "values": sorted(int(v) for v in raw[RAW_STUDY_HOURS].unique()),
            "used_in_model": False,
        },
    }


def _table(rows: list[list[object]], header: list[str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def render(summary: dict) -> str:
    d, q, t = summary["dataset"], summary["quality"], summary["target"]
    pear, spear = summary["correlation_with_target"]["pearson"], summary["correlation_with_target"]["spearman"]
    raw_desc = summary["describe_raw"]
    stats_rows = [[c, *(raw_desc[c][k] for k in ("mean", "std", "min", "25%", "50%", "75%", "max"))] for c in raw_desc]
    corr = summary["feature_correlation_matrix"]
    return f"""# EDA report: Final_Marks_Data.csv

Generated by `python -m ml_training.eda`. All figures are computed from the file.

## Dataset
- File: `{d['path']}` (sha256 `{d['sha256'][:16]}…`)
- {d['rows']} rows × {len(d['columns'])} columns. **Provenance: {d['provenance']}.**
- Excluded from modelling: {", ".join(f"`{k}` ({v})" for k, v in d['excluded_columns'].items())}.

## Data quality
| Check | Result |
|---|---|
| Missing values | {q['missing_values_total']} |
| Duplicate Student_ID | {q['duplicate_student_ids']} |
| Exact duplicate rows (ignoring ID) | {q['exact_duplicate_rows_excluding_id']} ({q['rows_in_duplicate_groups_excluding_id']} rows involved) |
| Identical raw inputs (incl. study hours) with different final marks | {q['identical_inputs_with_different_targets_groups']} groups (irreducible noise no model can remove) |
| All values whole numbers | {q['all_values_integers']} |
| IQR outliers per column | {", ".join(f"{k}: {v}" for k, v in q['iqr_outliers_per_column'].items())} |

No cleaning is needed: there are no missing values or impossible values, and duplicate
rows (identical except ID) are kept because two real students can have identical marks.
IQR "outliers" are within the valid ranges, so they are kept. The data is unusually clean
(no missing values, whole numbers only), which is consistent with a synthetic or curated dataset;
this cannot be confirmed without the source.

## Raw column statistics
{_table(stats_rows, ["Column", "mean", "std", "min", "25%", "50%", "75%", "max"])}

## Target: final exam marks
Mean {t['mean']}, median {t['median']}, std {t['std']}, skew {t['skew']}, range {t['min']}–{t['max']}.
Share below 40: {t['share_below_40']:.2%}.

{_table([[k, v] for k, v in t['histogram'].items()], ["Final marks band", "Students"])}

## Correlation with the target
{_table([[c, pear[c], spear[c]] for c in pear], ["Column", "Pearson", "Spearman"])}

## Relationships between features
{_table([[FEATURE_LABELS[r], *(corr[c][r] for c in corr)] for r in corr], ["", *(FEATURE_LABELS[c] for c in corr)])}

Variance inflation factors: {", ".join(f"{FEATURE_LABELS[k]} {v}" for k, v in summary['vif'].items())}
(values below 5 are usually considered unproblematic).

## Final marks by attendance band
{_table([[k, v['n'], v['mean_final']] for k, v in summary['target_mean_by_attendance_band'].items()], ["Attendance %", "Students", "Mean final %"])}

## Study hours (not used)
Pearson correlation with the final mark: {summary['study_hours_note']['pearson_with_target']};
values present: {summary['study_hours_note']['values']}. Excluded by project decision.

## Leakage and limitations
- The target is the final exam. Internal tests are earlier assessments in the same course, which is
  legitimate at prediction time; Internal 2 must not be used for a Stage 1 prediction because it does
  not exist yet, so Stage 1 and Stage 2 are separate models with separate feature lists.
- `Student_ID` is an identifier and carries no information; it is dropped.
- Correlation is not causation: features are associated with final marks, not proven to cause them.
- Unknown provenance: results describe this dataset only and may not transfer to a real cohort.
"""


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    summary = analyse()
    (REPORTS / "eda_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (REPORTS / "eda_report.md").write_text(render(summary), encoding="utf-8")
    print(f"Wrote {REPORTS / 'eda_report.md'} and eda_summary.json")


if __name__ == "__main__":
    main()
