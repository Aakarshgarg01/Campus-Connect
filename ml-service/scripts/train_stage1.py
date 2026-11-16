"""Train and evaluate the Stage 1 Linear Regression model."""

from pathlib import Path
import sys

import joblib
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from preprocessing.pipeline import (  # noqa: E402
    STAGE1_FEATURES,
    TARGET,
    load_validated_dataset,
    prepare_features,
)


def main() -> None:
    data = load_validated_dataset(SERVICE_ROOT / "data" / "Final_Marks_Data.csv")
    features, target = prepare_features(data)
    x_train, x_test, y_train, y_test = train_test_split(
        features[STAGE1_FEATURES], target, test_size=0.2, random_state=42
    )
    model = LinearRegression().fit(x_train, y_train)
    predictions = model.predict(x_test)
    print("Stage 1 Linear Regression")
    print(f"Training samples: {len(x_train)}")
    print(f"Testing samples: {len(x_test)}")
    print(f"Features: {STAGE1_FEATURES}")
    print(f"Target: {TARGET}")
    print(f"MAE: {mean_absolute_error(y_test, predictions):.6f}")
    print(f"RMSE: {mean_squared_error(y_test, predictions) ** 0.5:.6f}")
    print(f"R2: {r2_score(y_test, predictions):.6f}")
    print("Coefficients:")
    for feature, coefficient in zip(STAGE1_FEATURES, model.coef_):
        print(f"{feature} -> {coefficient:.6f}")
    print(f"Intercept: {model.intercept_:.6f}")
    model_path = SERVICE_ROOT / "models" / "stage1_model.pkl"
    joblib.dump(model, model_path)
    print(f"Saved model: {model_path}")


if __name__ == "__main__":
    main()