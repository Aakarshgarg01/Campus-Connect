# CampusConnect ML Service

This directory contains the reproducible Linear Regression training pipeline for CampusConnect, an academic early-warning and performance monitoring system. The models estimate expected final academic performance from the indicators available at each stage. A prediction is an estimate, not a guaranteed final result.

## Dataset

Source: `data/Final_Marks_Data.csv`. The source CSV is read-only and is not copied or modified.

| Dataset column | Use |
| --- | --- |
| `Student_ID` | Identifier only; excluded from modeling |
| `Attendance (%)` | Stage 1 and Stage 2 feature, already a percentage |
| `Internal Test 1 (out of 40)` | Converted to `Internal Test 1 (%)` |
| `Internal Test 2 (out of 40)` | Converted to `Internal Test 2 (%)` |
| `Assignment Score (out of 10)` | Converted to `Assignment (%)` |
| `Daily Study Hours` | Excluded from modeling |
| `Final Exam Marks (out of 100)` | Target, retained on a 0-100 scale as `Final Exam Marks (%)` |

## Models and preprocessing

Both models use only `sklearn.linear_model.LinearRegression`.

- Stage 1 features: `Attendance (%)`, `Internal Test 1 (%)`, `Assignment (%)`
- Stage 2 features: `Attendance (%)`, `Internal Test 1 (%)`, `Internal Test 2 (%)`, `Assignment (%)`
- Target: `Final Exam Marks (%)`
- Excluded: `Student_ID`, `Daily Study Hours`, and all target-derived values

Training converts raw marks deterministically using `obtained / maximum * 100`: internal tests use 40 and assignments use 10. The FastAPI service receives percentage-based inputs and does not convert them again. Attendance and final marks are already percentages. No standardization or target normalization is applied. The shared feature names and ordering are defined in `preprocessing/pipeline.py`.

Each model uses an 80/20 train/test split with `random_state=42`. Evaluation uses MAE, RMSE, and R2. The test set is not used during training.

## Install and run

From `ml-service`:

```powershell
py -m pip install -r requirements.txt
py -m uvicorn main:app --reload --port 8000
```

The service is available at `http://127.0.0.1:8000`. Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.

The API loads the existing models at application startup. It does not retrain or modify them.

For the direct training pipeline and dataset inspection, run:

```powershell
py scripts/inspect_dataset.py
py scripts/train_stage1.py
py scripts/train_stage2.py
py scripts/test_predictions.py
```

On Windows, use the selected Python interpreter if `py` is not available.

## FastAPI endpoints

### `GET /health`

Returns status only when both model files exist and loaded successfully:

```json
{
	"status": "ok",
	"service": "CampusConnect ML Service"
}
```

### `POST /predict/stage1`

Inputs are percentages from 0 to 100:

```json
{
	"attendance": 85,
	"internal1": 75,
	"assignment": 80
}
```

Response:

```json
{
	"stage": "stage1",
	"predicted_final_performance": 65.06
}
```

### `POST /predict/stage2`

```json
{
	"attendance": 85,
	"internal1": 75,
	"internal2": 80,
	"assignment": 80
}
```

Response:

```json
{
	"stage": "stage2",
	"predicted_final_performance": 63.19
}
```

### `POST /predict/what-if`

The `stage` field must be `stage1` or `stage2`. Stage 2 requires `internal2`.

```json
{
	"stage": "stage1",
	"attendance": 90,
	"internal1": 85,
	"assignment": 90
}
```

Response:

```json
{
	"stage": "stage1",
	"predicted_final_performance": 75.65,
	"simulation_only": true,
	"message": "Simulation only - this is not a guaranteed result."
}
```

All percentage values are validated with Pydantic and must be between 0 and 100. Invalid values, missing fields, unknown fields, invalid stages, or a missing Stage 2 `internal2` value return HTTP 422. Prediction failures return HTTP 500 without exposing stack traces.

## CORS

Development origins default to `http://localhost:5173` and `http://localhost:3000`. Change them with the comma-separated `CORS_ORIGINS` environment variable, for example:

```powershell
$env:CORS_ORIGINS = "http://localhost:5173,http://localhost:3000"
```

## API tests

With the service dependencies installed, run the independent in-process API checks from `ml-service`:

```powershell
py scripts/test_api.py
```

This tests health, Stage 1, Stage 2, both What-if stages, invalid input, invalid stage, and missing Stage 2 input.

## Saved model files

- `models/stage1_model.pkl`
- `models/stage2_model.pkl`

The prediction test verifies that both models load, use the explicit feature order, and produce numeric predictions. Predictions are not silently clamped to 0-100; out-of-range values are reported.

## Results

The results below were produced from the current 2,000-row dataset using the fixed 80/20 split and `random_state=42`.

### Stage 1

- Features: `Attendance (%)`, `Internal Test 1 (%)`, `Assignment (%)`
- Target: `Final Exam Marks (%)`
- Training/testing samples: 1,600/400
- MAE: 4.726111
- RMSE: 5.902586
- R2: 0.721811
- Coefficients: Attendance `0.653639`; Internal Test 1 `0.287875`; Assignment `0.340376`
- Intercept: `-39.319115`

### Stage 2

- Features: `Attendance (%)`, `Internal Test 1 (%)`, `Internal Test 2 (%)`, `Assignment (%)`
- Target: `Final Exam Marks (%)`
- Training/testing samples: 1,600/400
- MAE: 3.945305
- RMSE: 4.878954
- R2: 0.809932
- Coefficients: Attendance `0.437875`; Internal Test 1 `0.373805`; Internal Test 2 `0.372598`; Assignment `0.136429`
- Intercept: `-42.783197`

The scripts print these metrics, coefficients, intercept, and model paths whenever training is rerun.

## Limitations

The models learn relationships in this dataset and do not guarantee future results. The training data uses fixed maximums for internal tests and assignments, while the real application should normalize obtained and maximum marks into percentages before calling this service. Authentication, request rate limiting, model monitoring, confidence intervals, and the future Node.js gateway remain outside this ML service.