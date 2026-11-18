# Deploying: Render (API) + TiDB Cloud Starter (database) + Vercel (frontend)

Everything here is free tier. Order matters: database → API → frontend → point the API's CORS at
the frontend. Passwords and connection strings are typed **only** into the providers' dashboards.
They never go in git, chat or this repo.

## 0. Prerequisite
The branch `fastapi-mysql-migration` must be on GitHub, because Render and Vercel build from it.

## 1. Database: TiDB Cloud Starter
1. Sign up at tidbcloud.com and create a **Starter** cluster. Pick the region closest to your Render
   region (e.g. AWS `ap-south-1` Mumbai with Render Singapore, or AWS `us-east-1` with Render Ohio/Virginia).
2. Open **SQL Editor** (or connect with any MySQL client) and run the SQL below. TiDB Starter
   usernames carry a cluster prefix: use the prefix shown on the **Connect** page in place of
   `PREFIX`, and choose your own strong password.
   ```sql
   CREATE DATABASE student_predictor;
   CREATE USER 'PREFIX.sp_app'@'%' IDENTIFIED BY 'CHOOSE_A_STRONG_PASSWORD';
   GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
     ON student_predictor.* TO 'PREFIX.sp_app'@'%';
   ```
3. From **Connect**, note the host (`gateway01.<region>.prod.aws.tidbcloud.com`) and port (`4000`).
   Your connection string will be:
   ```
   mysql+pymysql://PREFIX.sp_app:PASSWORD@HOST:4000/student_predictor?charset=utf8mb4
   ```
   URL-encode the password if it contains `@ : / ? # %`.
   TiDB Starter requires TLS with a public CA, which the image's `DB_SSL_CA=/etc/ssl/certs/ca-certificates.crt`
   already covers.

**TiDB differences to be aware of:**
- TiDB is MySQL-compatible, not MySQL. Foreign keys with `ON DELETE CASCADE` are supported.
- CHECK constraints are only enforced when `tidb_enable_check_constraint` is ON; otherwise TiDB
  accepts and ignores them. The API validates every value before saving, so data stays valid
  either way. The CHECKs are an extra safety net on real MySQL.

## 2. API: Render
1. Sign up at render.com with GitHub and allow access to this repository.
2. **New → Blueprint**, pick the repo and branch `fastapi-mysql-migration`. Render reads `render.yaml`.
3. When prompted, set:
   - `DATABASE_URL`: the TiDB string from step 1.
   - `CORS_ORIGINS`: temporarily `https://example.invalid` (replaced in step 4).
4. Deploy. The build takes a few minutes. The logs should show both Alembic migrations, then
   `Startup complete`. `https://<service>.onrender.com/health` should return 200 with
   `"database":{"connected":true}` and both models loaded.
5. Create the first staff account in the Render **Shell** tab:
   ```
   python -m app.cli create-user --role admin --name "Your Name" --email you@college.edu --employee-id ADM1 --department "Computer Science"
   ```

## 3. Frontend: Vercel
1. Sign up at vercel.com with GitHub. **Add New → Project**, choose the repo, set **Root Directory**
   to `frontend`, and select branch `fastapi-mysql-migration`.
2. Environment variables:
   - `VITE_API_BASE_URL` = `https://<service>.onrender.com`
   - `NITRO_PRESET` = `vercel`
3. Deploy, and note the URL (`https://<project>.vercel.app`).

## 4. Connect them
In Render → service → Environment, set `CORS_ORIGINS=https://<project>.vercel.app` (exact, no
trailing slash) and save. Render redeploys.

## 5. Smoke test (live)
- `GET /health` → 200
- Register a student on the site, then sign in as staff
- Create a student (or use the registered one), enter marks and attendance on **Academic Data**
- On the student's page: **Predict** → result with SHAP chart and recommendations
- Check the history, `/api/model-info`, `/api/feature-importance`
- Sign in as the student: dashboard, simulator, target

**Free-tier behaviour:** the API sleeps after about 15 idle minutes, so the first request afterwards
takes about a minute. The frontend retries and shows "If the server was idle this can take up to a minute."
