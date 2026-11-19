# Student Performance Predictor (CampusConnect)

Predicts a student's **final exam performance (%)** from attendance, internal test marks and
assignment scores, explains every prediction with **SHAP**, and turns the explanation into
plain-English recommendations. Faculty manage students, marks, benchmarks and follow-up;
students see their own predictions, a what-if simulator and their target.

> Predictions are estimates learned from historical data, not guaranteed results, and the
> factors are associations, not causes.

**Live links:** not deployed yet. Deployment needs your hosting accounts; see
[Deployment](#deployment). This section will hold the public URLs once deployed.

---

## Architecture

```
React (TanStack Start, Vite, Recharts, Axios)  ──HTTPS/JSON──▶  FastAPI (Uvicorn)
  student + faculty workspaces                                  ├─ JWT auth (cookie or Bearer), roles, rate limit
  SHAP + recommendations UI                                     ├─ SQLAlchemy 2 ──▶ MySQL 8 (Alembic migrations)
                                                                └─ scikit-learn pipelines + SHAP (loaded once at startup)
```

| Layer | Technology |
|---|---|
| Frontend | React 19, TanStack Start/Router/Query, Tailwind, shadcn/Radix, Recharts, Axios |
| Backend | FastAPI, Uvicorn, Pydantic v2, pydantic-settings, SQLAlchemy 2, Alembic, PyMySQL |
| Auth | JWT (PyJWT, HS256), Argon2id password hashing (pwdlib), slowapi rate limiting |
| ML | pandas, NumPy, scikit-learn 1.9.1, joblib, SHAP 0.54.1 |
| Database | MySQL 8 (8.4 LTS tested), utf8mb4, InnoDB |

### Repository layout

```
backend/
  app/
    main.py                     app factory, CORS, lifespan (loads models once)
    core/                       config (env), security (JWT, roles), errors, logging, rate limit
    database/connection.py      engine (TLS optional), per-request session, health ping
    models/                     SQLAlchemy models (users, students, academic_records, attendance,
                                predictions, student_targets, faculty_benchmarks, monitoring)
    schemas/                    Pydantic request/response models
    routers/                    auth, students, predictions, academic, health
    services/                   business logic
    ml/                         features, model_loader, predict, explain (SHAP), recommend, risk
    cli.py                      create faculty/admin accounts
  alembic/                      migrations (2 revisions)
  ml_training/                  dataset.py, eda.py, eda.ipynb, train.py, reports/
  models_store/stage{1,2}/      model.joblib, metadata.json, background.csv (SHAP)
  tests/                        116 pytest tests (real MySQL + real models)
  Dockerfile, docker-entrypoint.sh, requirements*.txt, .env.example
frontend/                       existing UI, now on the real API (no mock data)
legacy/                         previous Node/Express + MongoDB backend and old ML service (reference only)
docs/                           postman_collection.json, screenshots/
render.yaml                     Render Blueprint for the backend
.github/workflows/ci.yml        backend tests on MySQL 8.4 + frontend type-check/build
```

---

## Dataset and limitations

`backend/ml_training/data/Final_Marks_Data.csv`: 2,000 students, 7 columns.

**Provenance: unknown.** The repository doesn't document a source or licence. The data has no
missing values and contains only whole numbers, which is consistent with a synthetic or curated
dataset. Results describe this dataset only.

| Dataset column | Used as | Notes |
|---|---|---|
| Attendance (%) | `attendance_pct` | already 0–100 |
| Internal Test 1 (out of 40) | `internal1_pct` | ×100/40 |
| Internal Test 2 (out of 40) | `internal2_pct` | ×100/40, **Stage 2 only** |
| Assignment Score (out of 10) | `assignment_pct` | a score, not a count of assignments completed |
| Final Exam Marks (out of 100) | **target** | |
| Student_ID | not used | identifier |
| Daily Study Hours | not used | excluded by project decision (self-reported; ruled out by the app's roadmap) |

Inputs the original brief asked for but the data doesn't contain (`quiz_score`,
`previous_performance`) were **not** invented.

**Leakage controls.**
- Stage 1 (before Internal 2 exists) and Stage 2 are separate models, and Stage 1 never sees Internal 2.
- Preprocessing lives inside a scikit-learn `Pipeline`, so it's fitted only on training folds.
- The test set is scored once, after model selection.

Full EDA: [`backend/ml_training/reports/eda_report.md`](backend/ml_training/reports/eda_report.md)
and [`eda.ipynb`](backend/ml_training/eda.ipynb).

## Model

`python -m ml_training.train`:
1. A stratified 80/20 split (1,600 / 400 rows, seed 42).
2. **Nested cross-validation** to compare the models: an inner 3-fold `GridSearchCV` for tuning and an outer 5-fold loop for the estimate.
3. Selection by lowest CV RMSE, preferring the simplest model within one standard error.

Every number below comes from [`training_report.md`](backend/ml_training/reports/training_report.md).

**Cross-validated RMSE (marks, lower is better), and R² on the held-out test set**

| Model | Stage 1 CV RMSE | Stage 1 test R² | Stage 2 CV RMSE | Stage 2 test R² |
|---|---|---|---|---|
| Baseline (predict the mean) | 11.371 | −0.001 | 11.371 | −0.001 |
| **Linear Regression (chosen)** | **5.830 ± 0.075** | **0.695** | **4.893 ± 0.185** | **0.815** |
| Gradient Boosting | 5.960 | 0.692 | 5.085 | 0.804 |
| Random Forest | 5.995 | 0.676 | 5.189 | 0.800 |
| Decision Tree | 6.423 | 0.647 | 5.746 | 0.758 |

**Chosen models on the held-out test set:**
- Stage 1: MAE 4.88, RMSE 6.18, R² 0.695.
- Stage 2: MAE 3.84, RMSE 4.81, R² 0.815.
- 90% of Stage 2 test errors are within ±7.8 marks (Stage 1: ±9.9). The API shows this as each prediction's likely range.

**What gets saved, and how loading is protected:**
- Each pipeline is saved with `metadata.json`: features and training ranges, all metrics, the full comparison, the seed, the dataset hash and library versions.
- The loader **refuses** a model whose file hash, scikit-learn version or feature list doesn't match. `/health` then reports the reason, and predictions return 503.
- Retraining is byte-for-byte reproducible.

## Explainability and recommendations

- **SHAP.**
  - Linear models use `shap.LinearExplainer` (tree models would use `TreeExplainer`). It runs on the transformed features and is mapped back to input names; one-hot columns would be summed.
  - The reference is a fixed 200-row training sample shipped as `background.csv`.
  - Every explanation verifies **base value + Σ contributions = raw prediction** (tolerance 1e-6), which is tested on hundreds of random inputs.
- **Global importance** (`GET /api/feature-importance`) is the mean |SHAP| over the 1,600 training students:
  - Stage 1: Attendance 42.5%, Assignment 30.1%, Internal 1 27.4%.
  - Stage 2: Internal 1 31.5%, Internal 2 31.0%, Attendance 25.8%, Assignment 11.7%.
- **Recommendations** come from the student's own values and their negative SHAP factors (at most three).
  - Each quotes the student's value against the training average.
  - Each gives a model-computed effect, such as "raising Attendance from 68% to 84.9% is associated with about +7.5 marks…".
  - Wording is always "associated with"; a test rejects causal phrasing.
- **Risk levels** are a documented policy, not learned:
  - **high** below 50%, **medium** 50–60%, **low** 60% and above.
  - 9.4% of students in the dataset scored below 50.
  - Configurable with `RISK_HIGH_BELOW` and `RISK_MEDIUM_BELOW`.

---

## API

Interactive docs: `http://localhost:8000/docs`. Every error uses one shape:
`{"error": {"code", "message", "details"}, "request_id"}`.

| Method | Path | Access |
|---|---|---|
| GET | `/health` | public. 200 only when the DB and both models are ready, else 503 |
| POST | `/api/auth/register` | public (students only) |
| POST | `/api/auth/login` | public, 5 per minute per IP. Returns the JWT and sets an httpOnly cookie |
| POST | `/api/auth/logout`, GET `/api/auth/me` | signed in |
| POST/GET | `/api/students/` | faculty/admin |
| GET/PUT/DELETE | `/api/students/{id}` | GET: staff or that student; PUT/DELETE: staff |
| GET | `/api/students/me` | student |
| GET/PUT | `/api/students/{id}/academic` | read: staff or that student; write: staff |
| GET/PUT | `/api/students/{id}/target` | read: staff or that student; write: that student |
| GET/PUT | `/api/students/{id}/monitoring` | faculty/admin |
| GET/PUT | `/api/benchmarks` | read: signed in; write: staff |
| GET | `/api/faculty/overview` | faculty/admin |
| POST | `/api/predictions/predict` | staff (manual inputs or stored records); a student only from their own records |
| POST | `/api/predictions/simulate` | signed in (nothing is saved) |
| GET | `/api/predictions/history/{student_id}`, `/api/predictions/{id}` | staff or that student |
| GET | `/api/model-info`, `/api/feature-importance` | public |

Example (real response, abridged):

```http
POST /api/predictions/predict
{"student_id": 1, "stage": "stage2",
 "inputs": {"attendance": 68, "internal1": 62.5, "internal2": 85, "assignment": 60}}

201 Created
{"predicted_marks": 50.07, "risk_level": "medium",
 "interval": {"low": 42.3, "high": 57.84},
 "shap_explanation": {"method": "shap.LinearExplainer", "base_value": 65.7891, "raw_prediction": 50.0698,
   "contributions": [{"label": "Attendance", "value": 68.0, "shap_value": -7.8157, "direction": "decreases"}, ...]},
 "recommendations": {"summary": "The estimated final exam score is 50.1% (medium risk)...", "items": [...]},
 "model_version": "stage2-linear_regression-20261118-dda06f7e"}
```

Postman: import [`docs/postman_collection.json`](docs/postman_collection.json) (21 requests).
Login saves the token; the predict request checks SHAP additivity.

---

## Local setup (Windows)

**Prerequisites:** Python 3.12+ (3.13 matches the trained models), Node 20+, and MySQL 8.4.
Install MySQL with `winget install -e --id Oracle.MySQL`.

**Database.** Run `mysql -u root -p`, then:
```sql
CREATE DATABASE student_predictor CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE student_predictor_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'sp_app'@'localhost' IDENTIFIED BY 'CHOOSE_A_STRONG_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES ON student_predictor.* TO 'sp_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES ON student_predictor_test.* TO 'sp_app'@'localhost';
```

**Backend** (PowerShell, from `backend\`):
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env        # then set DATABASE_URL, TEST_DATABASE_URL and JWT_SECRET
alembic upgrade head
python -m app.cli create-user --role faculty --name "Your Name" --email you@college.edu --employee-id FAC1024 --department "Computer Science"
uvicorn app.main:app --reload --port 8000
```

**Frontend** (from `frontend\`):
```powershell
Copy-Item .env.example .env        # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev -- --port 8080
```
Then open `http://localhost:8080`.

**Default testing logins** (local and development only): run `python -m app.cli seed-demo` once.
It creates the accounts below, or resets their password if they already exist, and refuses to run when `ENVIRONMENT=production`.

| Role | Login ID | Password |
|---|---|---|
| Faculty | `FAC1024` (or `demo.faculty@example.com`) | `Campus@123` |
| Student | `CS21041` (or `demo.student@example.com`) | `Campus@123` |

Never use these on a deployed site.

**Retrain / EDA** (optional): `python -m ml_training.eda`, `python -m ml_training.train`.

## Testing

```powershell
python -m pytest          # 116 tests, needs TEST_DATABASE_URL (a database whose name contains _test)
alembic check             # models and migrations are in sync
```

The tests cover:
- the database (constraints, cascades) and auth (valid, invalid, expired, forged and tampered tokens; role checks; the rate limit);
- student CRUD and invalid inputs (422);
- predictions with the real models: missing model → 503, insufficient data → 422;
- SHAP additivity and recommendations;
- `/health` and the production configuration checks.

CI (`.github/workflows/ci.yml`) runs the backend suite against a MySQL 8.4 service container, plus a frontend type-check and build.

---

## Deployment

### Options checked (November 2026)

| Piece | Option | Trade-offs |
|---|---|---|
| Backend | **Render, free web service (Docker)** | $0. Sleeps after ~15 min idle, and the first request then takes about a minute (the frontend retries and says so). 750 free instance-hours a month. Starter plan ($7/month) doesn't sleep. |
| Backend | Railway | Usage-based (Hobby has a $5/month minimum). No sleeping, and can host MySQL next to the API. |
| Database | **TiDB Cloud Starter** | Free tier (about 5 GiB row storage plus a monthly request-unit allowance). It's MySQL-**compatible**, not MySQL. Foreign keys are supported in recent TiDB. CHECK constraints may need `tidb_enable_check_constraint`. The API validates every value anyway. TLS uses a public CA. |
| Database | Railway MySQL | Real MySQL 8, roughly $5–20/month depending on usage. Easiest if the API is also on Railway. |
| Database | Aiven MySQL | Aiven's free MySQL tier no longer accepts new services; paid plans only. |
| Database | Azure Database for MySQL (Flexible) | Real MySQL with a 12-month free offer for new Azure accounts. More setup, and needs a card. |
| Frontend | **Vercel** | Free hobby tier. Build with `NITRO_PRESET=vercel` (tested locally: produces `.vercel/output`). |

Pricing pages change, so confirm limits on each provider's site before you sign up.

**Chosen setup: Render + TiDB Cloud Starter + Vercel.** The click-by-click guide is in [`docs/DEPLOY.md`](docs/DEPLOY.md).

### Steps (Render + managed MySQL + Vercel)

1. **Database.** Create the managed MySQL database and a dedicated user. Note the host, port and TLS requirements.
   `DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:PORT/student_predictor?charset=utf8mb4`
2. **Backend.** In Render, choose **New → Blueprint**, select this repository, and it reads `render.yaml`. Fill in `DATABASE_URL` and `CORS_ORIGINS` (your Vercel URL, `https://…`).
   - The container runs `alembic upgrade head`, then `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`.
   - In production the app **refuses to start** unless CORS lists exact `https://` origins, the database URL is MySQL, and `DB_SSL_CA` is set (TLS with certificate verification).
3. **First faculty account.** In the Render shell: `python -m app.cli create-user --role admin ...`.
4. **Frontend.** Import `frontend/` into Vercel with these environment variables:
   - `VITE_API_BASE_URL=https://<your-api>.onrender.com`
   - `NITRO_PRESET=vercel`
5. **Smoke test** the live URLs: `/health` → 200; register; login; create a student; enter marks; predict; check the SHAP output; check history; then the full flow through the live frontend.

The image uses Python 3.13 and the same pinned scikit-learn and SHAP versions as training, and the committed models are copied in.

**Verified locally without Docker** (Docker isn't installed on the dev machine). I copied exactly the files the image contains, installed `requirements.txt` only, and ran `docker-entrypoint.sh` with `ENVIRONMENT=production` against MySQL over **verified TLS**. Results:
- Migrations created 9 tables.
- `/health` returned 200.
- The login cookie was `HttpOnly; SameSite=none; Secure`.
- CORS allowed only the configured https origin.
- The rate limit keyed on the real client IP from `X-Forwarded-For`.
- An unverifiable database certificate was refused.

**Cross-site sign-in.** With the frontend and API on different sites, the app sends the JWT as a Bearer token from memory, and the cookie is `SameSite=None; Secure`. Browsers that block third-party cookies make users sign in again after a full page reload. Serving both from one site (e.g. `app.example.com` and `api.example.com`) avoids this.

---

## Security notes

- Passwords: Argon2id only. JWT: HS256 with the algorithm fixed. The role is read from the database, never trusted from the token.
- Login: one message for every failure, a dummy hash check against timing attacks, and a 5-per-minute limit per IP.
- Students can only see their own data; other students' IDs return 404. Students can't save self-entered marks; manual inputs are staff-only.
- Errors never expose stack traces or database details. Logs are structured JSON with request IDs.
- Secrets stay in `.env` (git-ignored); `.env.example` files contain placeholders only.

## Known limitations / not done

- Bulk CSV/Excel upload is **not** connected to the new backend; the page says so. Marks are entered per student on *Academic Data*.
- Dataset provenance is unknown, so performance on a real cohort is unverified.
- Not deployed: no live URLs yet (see Deployment).
- `frontend/package-lock.json` was regenerated with `npm install`. Lovable maintains `bun.lock`, which wasn't touched.

## Screenshots

From an end-to-end run against the local API and MySQL. The accounts were test accounts, deleted afterwards.

| | |
|---|---|
| ![Prediction with SHAP and recommendations](docs/screenshots/04-prediction-shap-recommendations.jpg) | ![Student dashboard](docs/screenshots/05-student-dashboard.jpg) |
| ![Faculty overview](docs/screenshots/02-faculty-overview.jpg) | ![What-if simulator](docs/screenshots/07-simulator.jpg) |
| ![Academic data entry](docs/screenshots/03-academic-data.jpg) | ![Register](docs/screenshots/01-register.jpg) |
| ![Target](docs/screenshots/06-target.jpg) | ![Mobile prediction history](docs/screenshots/08-mobile-history.jpg) |
