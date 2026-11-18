"""Train, compare and save the Stage 1 and Stage 2 final-exam prediction pipelines.

Run from backend/:  python -m ml_training.train

Method (identical for both stages, all randomness seeded with SEED):
1. Validate the CSV and convert raw marks to percentages (ml_training/dataset.py).
2. One stratified 80/20 train/test split, shared by both stages. The test set is not used
   for any choice; it is scored once at the end for reporting.
3. Candidates: Linear Regression, Decision Tree, Random Forest, Gradient Boosting (plus a
   mean-only baseline). Each is a Pipeline(ColumnTransformer -> model), so preprocessing is
   fitted inside every CV fold (no leakage) and is saved with the model for inference.
4. Nested CV on the training set: the inner 3-fold GridSearchCV tunes hyperparameters, the outer
   5-fold estimates performance. This gives an unbiased comparison of tuned models.
5. Selection: lowest outer-CV RMSE, with the one-standard-error rule: the simplest candidate whose
   CV RMSE is within one standard error of the best is chosen (simpler = easier to explain).
6. The chosen family is re-tuned on the full training set; that fitted pipeline is saved together
   with metadata.json. Reported test metrics are for exactly the saved pipeline.
"""

from __future__ import annotations

import hashlib
import io
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
import sklearn
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GridSearchCV, KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeRegressor

from app.ml.explain import StageExplainer
from app.ml.features import FEATURE_LABELS, STAGE_FEATURES, TARGET, TARGET_LABEL
from ml_training.dataset import DATA_PATH, EXCLUDED_COLUMNS, file_sha256, load_raw, prepare

SEED = 42
TEST_SIZE = 0.2
OUTER_FOLDS = 5
INNER_FOLDS = 3
BACKEND = Path(__file__).resolve().parents[1]
MODELS_STORE = BACKEND / "models_store"
REPORTS = Path(__file__).resolve().parent / "reports"
BACKGROUND_ROWS = 200
SCORING = {"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error", "r2": "r2"}


@dataclass
class Candidate:
    key: str
    name: str
    estimator: BaseEstimator
    grid: dict[str, list] = field(default_factory=dict)
    complexity: int = 0  # lower = simpler; used by the one-standard-error rule
    explainer: str | None = None  # SHAP explainer for Phase 8


def candidates() -> list[Candidate]:
    return [
        Candidate("baseline_mean", "Baseline (predict training mean)", DummyRegressor(strategy="mean"), complexity=-1),
        Candidate("linear_regression", "Linear Regression", LinearRegression(), complexity=0, explainer="linear"),
        Candidate("decision_tree", "Decision Tree", DecisionTreeRegressor(random_state=SEED),
                  {"model__max_depth": [3, 4, 5, 6, 8], "model__min_samples_leaf": [5, 10, 20, 40]},
                  complexity=1, explainer="tree"),
        Candidate("gradient_boosting", "Gradient Boosting", GradientBoostingRegressor(random_state=SEED, subsample=0.8),
                  {"model__n_estimators": [100, 300], "model__learning_rate": [0.03, 0.1], "model__max_depth": [2, 3]},
                  complexity=2, explainer="tree"),
        Candidate("random_forest", "Random Forest", RandomForestRegressor(random_state=SEED, n_estimators=200, n_jobs=-1),
                  {"model__max_depth": [6, 10, None], "model__min_samples_leaf": [5, 10, 20], "model__max_features": [1.0, "sqrt"]},
                  complexity=3, explainer="tree"),
    ]


def build_pipeline(features: list[str], model: BaseEstimator) -> Pipeline:
    """All features are numeric percentages: scale them (needed for nothing but harmless for trees,
    and it keeps linear coefficients comparable). There are no categorical columns to encode."""
    preprocess = ColumnTransformer([("num", StandardScaler(), features)], remainder="drop",
                                   verbose_feature_names_out=False)
    return Pipeline([("preprocess", preprocess), ("model", model)])


def searcher(candidate: Candidate, features: list[str], folds: int) -> BaseEstimator:
    pipeline = build_pipeline(features, sklearn.clone(candidate.estimator))
    if not candidate.grid:
        return pipeline
    return GridSearchCV(pipeline, candidate.grid, cv=KFold(folds, shuffle=True, random_state=SEED),
                        scoring="neg_root_mean_squared_error", n_jobs=-1)


def metrics(y_true, y_pred) -> dict[str, float]:
    return {"mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
            "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 4),
            "r2": round(float(r2_score(y_true, y_pred)), 4)}


def split(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Stratify on final-mark quintiles so both sets cover the full range of outcomes.
    strata = pd.qcut(data[TARGET], q=5, labels=False, duplicates="drop")
    return train_test_split(data, test_size=TEST_SIZE, random_state=SEED, stratify=strata)


def train_stage(stage: str, train: pd.DataFrame, test: pd.DataFrame) -> dict:
    features = STAGE_FEATURES[stage]
    x_train, y_train, x_test, y_test = train[features], train[TARGET], test[features], test[TARGET]
    outer = KFold(OUTER_FOLDS, shuffle=True, random_state=SEED)
    rows = []
    fitted: dict[str, Pipeline] = {}
    for candidate in candidates():
        cv = cross_validate(searcher(candidate, features, INNER_FOLDS), x_train, y_train, cv=outer, scoring=SCORING)
        cv_scores = {name: -cv[f"test_{name}"] if name != "r2" else cv[f"test_{name}"] for name in SCORING}
        # Final fit for this family on the whole training set (inner CV = OUTER_FOLDS for tuning).
        final = searcher(candidate, features, OUTER_FOLDS).fit(x_train, y_train)
        best = final.best_estimator_ if isinstance(final, GridSearchCV) else final
        fitted[candidate.key] = best
        rows.append({
            "key": candidate.key,
            "name": candidate.name,
            "complexity": candidate.complexity,
            "cv": {name: {"mean": round(float(v.mean()), 4), "std": round(float(v.std(ddof=1)), 4)}
                   for name, v in cv_scores.items()},
            "cv_rmse_se": round(float(cv_scores["rmse"].std(ddof=1) / np.sqrt(OUTER_FOLDS)), 4),
            "test": metrics(y_test, best.predict(x_test)),
            "train": metrics(y_train, best.predict(x_train)),
            "best_params": {k.removeprefix("model__"): v for k, v in final.best_params_.items()}
            if isinstance(final, GridSearchCV) else {},
        })

    real = [r for r in rows if r["key"] != "baseline_mean"]
    best_row = min(real, key=lambda r: r["cv"]["rmse"]["mean"])
    threshold = best_row["cv"]["rmse"]["mean"] + best_row["cv_rmse_se"]
    chosen = min((r for r in real if r["cv"]["rmse"]["mean"] <= threshold), key=lambda r: r["complexity"])
    pipeline = fitted[chosen["key"]]
    predictions = pipeline.predict(x_test)
    residuals = y_test.to_numpy() - predictions
    return {
        "stage": stage,
        "features": features,
        "pipeline": pipeline,
        "candidates": rows,
        "selection": {
            "rule": "lowest outer-CV RMSE, then simplest model within one standard error of it",
            "best_cv_key": best_row["key"],
            "threshold_rmse": round(threshold, 4),
            "chosen_key": chosen["key"],
        },
        "chosen": chosen,
        "explainer": next(c.explainer for c in candidates() if c.key == chosen["key"]),
        "test_diagnostics": {
            "residual_std": round(float(residuals.std(ddof=1)), 4),
            "abs_error_p90": round(float(np.quantile(np.abs(residuals), 0.9)), 4),
            "predictions_outside_0_100": int(((predictions < 0) | (predictions > 100)).sum()),
            "mae_by_actual_band": {
                band: {"n": int(mask.sum()), "mae": round(float(np.abs(residuals[mask]).mean()), 4)}
                for band, mask in {
                    "<50": y_test.to_numpy() < 50,
                    "50-70": (y_test.to_numpy() >= 50) & (y_test.to_numpy() < 70),
                    ">=70": y_test.to_numpy() >= 70,
                }.items() if mask.any()
            },
        },
        "feature_ranges": {f: {"min": float(train[f].min()), "max": float(train[f].max()),
                               "mean": round(float(train[f].mean()), 4)} for f in features},
        "train_frame": train[features],
        "n_train": len(train),
        "n_test": len(test),
    }


def save(result: dict, trained_at: datetime) -> dict:
    stage_dir = MODELS_STORE / result["stage"]
    stage_dir.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    joblib.dump(result["pipeline"], buffer)
    digest = hashlib.sha256(buffer.getvalue()).hexdigest()
    version = f"{result['stage']}-{result['chosen']['key']}-{trained_at:%Y%m%d}-{digest[:8]}"
    (stage_dir / "model.joblib").write_bytes(buffer.getvalue())

    # SHAP background: a fixed random sample of training rows, shipped with the model so the API
    # computes explanations against exactly the same reference as here.
    background = result["train_frame"].sample(n=min(BACKGROUND_ROWS, len(result["train_frame"])), random_state=SEED)
    background.round(4).to_csv(stage_dir / "background.csv", index=False)
    background = pd.read_csv(stage_dir / "background.csv")
    explainer = StageExplainer.build(result["pipeline"], result["features"], result["explainer"], background)
    importance = explainer.global_importance(result["train_frame"])
    metadata = {
        "model_version": version,
        "stage": result["stage"],
        "algorithm": result["chosen"]["name"],
        "algorithm_key": result["chosen"]["key"],
        "hyperparameters": result["chosen"]["best_params"],
        "shap_explainer": result["explainer"],
        "features": [{"name": f, "label": FEATURE_LABELS[f], "unit": "percent",
                      "allowed_range": [0, 100], "training_range": [result["feature_ranges"][f]["min"],
                                                                     result["feature_ranges"][f]["max"]],
                      "training_mean": result["feature_ranges"][f]["mean"]}
                     for f in result["features"]],
        "target": {"name": TARGET, "label": TARGET_LABEL, "range": [0, 100],
                   "note": "Raw predictions can fall slightly outside 0-100; the API clips them."},
        "metrics": {"cv": result["chosen"]["cv"], "test": result["chosen"]["test"],
                    "train": result["chosen"]["train"]},
        "test_diagnostics": result["test_diagnostics"],
        "model_comparison": [{k: r[k] for k in ("key", "name", "cv", "test", "best_params")} for r in result["candidates"]],
        "selection": result["selection"],
        "training": {
            "trained_at": trained_at.isoformat(timespec="seconds"),
            "random_seed": SEED,
            "test_size": TEST_SIZE,
            "outer_cv_folds": OUTER_FOLDS,
            "inner_cv_folds": INNER_FOLDS,
            "n_train": result["n_train"],
            "n_test": result["n_test"],
            "dataset": {"file": DATA_PATH.name, "sha256": file_sha256(), "provenance": "unknown"},
            "excluded_columns": EXCLUDED_COLUMNS,
        },
        "library_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "shap": shap.__version__,
        },
        "model_sha256": digest,
        "shap": {
            "explainer": result["explainer"],
            "background_file": "background.csv",
            "background_rows": len(background),
            "background_sha256": hashlib.sha256((stage_dir / "background.csv").read_bytes()).hexdigest(),
            "base_value": round(explainer.base_value, 4),
            "global_importance": {"computed_on": f"training set (n={result['n_train']})",
                                  "statistic": "mean |SHAP value| per input", "values": importance},
        },
        "limitations": [
            "Dataset provenance is unknown; performance on a real cohort is unverified.",
            "Predictions are associations learned from data, not causal effects.",
            "Inputs outside the training range are extrapolations and less reliable.",
        ],
    }
    (stage_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def render_report(results: list[dict], metadata: list[dict]) -> str:
    lines = ["# Training report", "", "Generated by `python -m ml_training.train`. All numbers are computed, none typed in.", "",
             f"- Dataset: `{DATA_PATH.name}` (sha256 `{file_sha256()[:16]}…`, provenance unknown), "
             f"{results[0]['n_train']} train / {results[0]['n_test']} test rows (stratified, seed {SEED}).",
             f"- Nested CV: outer {OUTER_FOLDS}-fold for estimates, inner {INNER_FOLDS}-fold GridSearchCV for tuning.",
             "- Selection: lowest outer-CV RMSE; simplest model within one standard error wins.", ""]
    for result, meta in zip(results, metadata):
        lines += [f"## Stage {result['stage'].removeprefix('stage')}: {', '.join(FEATURE_LABELS[f] for f in result['features'])}", "",
                  "| Model | CV MAE | CV RMSE | CV R² | Test MAE | Test RMSE | Test R² | Train R² | Best params |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in result["candidates"]:
            mark = " **(chosen)**" if r["key"] == result["chosen"]["key"] else ""
            cv, te = r["cv"], r["test"]
            lines.append(
                f"| {r['name']}{mark} | {cv['mae']['mean']:.3f} ± {cv['mae']['std']:.3f} | "
                f"{cv['rmse']['mean']:.3f} ± {cv['rmse']['std']:.3f} | {cv['r2']['mean']:.3f} ± {cv['r2']['std']:.3f} | "
                f"{te['mae']:.3f} | {te['rmse']:.3f} | {te['r2']:.3f} | {r['train']['r2']:.3f} | "
                f"{json.dumps(r['best_params']) if r['best_params'] else '—'} |")
        d = result["test_diagnostics"]
        lines += ["", f"Saved `{meta['model_version']}`. Lowest CV RMSE: `{result['selection']['best_cv_key']}`; "
                      f"one-SE threshold {result['selection']['threshold_rmse']}. "
                      f"Test residual std {d['residual_std']}, 90% of test errors ≤ {d['abs_error_p90']} marks, "
                      f"{d['predictions_outside_0_100']} test predictions outside 0–100.",
                  "", "Test MAE by actual final mark: " + ", ".join(
                      f"{band}: {v['mae']} (n={v['n']})" for band, v in d["mae_by_actual_band"].items()), ""]
    lines += ["## Leakage controls", "- Student_ID and Daily Study Hours are never features; the target is never a feature.",
              "- Stage 1 never sees Internal 2.",
              "- Scaling and tuning happen inside each CV fold via Pipeline/GridSearchCV.",
              "- The test set is used once, after selection, for reporting only.", "",
              "CV = mean ± std over outer folds (MAE/RMSE in marks out of 100)."]
    return "\n".join(lines) + "\n"


def main() -> None:
    np.random.seed(SEED)
    trained_at = datetime.now(UTC)
    data = prepare(load_raw())
    train, test = split(data)
    results, metadata = [], []
    for stage in STAGE_FEATURES:
        print(f"Training {stage} ...", flush=True)
        result = train_stage(stage, train, test)
        meta = save(result, trained_at)
        results.append(result)
        metadata.append(meta)
        print(f"  chosen {meta['model_version']}  test {meta['metrics']['test']}", flush=True)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "training_report.md").write_text(render_report(results, metadata), encoding="utf-8")
    print(f"Wrote {REPORTS / 'training_report.md'}")


if __name__ == "__main__":
    sys.exit(main())
