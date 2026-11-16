"""Load both persisted models and run valid prediction examples."""

from pathlib import Path
import sys

import joblib
import pandas as pd

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from preprocessing.pipeline import (  # noqa: E402
    ASSIGNMENT_PERCENT,
    ATTENDANCE,
    INTERNAL1_PERCENT,
    INTERNAL2_PERCENT,
    STAGE1_FEATURES,
    STAGE2_FEATURES,
)


def main() -> None:
    stage1_model = joblib.load(SERVICE_ROOT / "models" / "stage1_model.pkl")
    stage2_model = joblib.load(SERVICE_ROOT / "models" / "stage2_model.pkl")
    stage1_features = pd.DataFrame(
        [
            {
                ATTENDANCE: 85,
                INTERNAL1_PERCENT: 75,
                ASSIGNMENT_PERCENT: 80,
            }
        ],
        columns=STAGE1_FEATURES,
    )
    stage2_features = pd.DataFrame(
        [
            {
                ATTENDANCE: 85,
                INTERNAL1_PERCENT: 75,
                INTERNAL2_PERCENT: 80,
                ASSIGNMENT_PERCENT: 80,
            }
        ],
        columns=STAGE2_FEATURES,
    )
    stage1_prediction = float(stage1_model.predict(stage1_features)[0])
    stage2_prediction = float(stage2_model.predict(stage2_features)[0])
    print(f"Stage 1 prediction: {stage1_prediction:.6f}")
    print(f"Stage 2 prediction: {stage2_prediction:.6f}")
    for stage, prediction in [("Stage 1", stage1_prediction), ("Stage 2", stage2_prediction)]:
        print(f"{stage} prediction numeric: {isinstance(prediction, float)}")
        if not 0 <= prediction <= 100:
            print(f"WARNING: {stage} prediction is outside the expected 0-100 range.")


if __name__ == "__main__":
    main()