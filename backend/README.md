# CampusConnect Backend

## Purpose

This Node.js service provides the backend foundation for CampusConnect, including student and faculty authentication, MongoDB connectivity, and a health endpoint. Academic and prediction APIs, uploads, and ML-service integration are not included yet.

## Technologies

- Node.js and Express
- MongoDB with Mongoose
- bcryptjs and jsonwebtoken for password hashing and cookie-based authentication
- dotenv, cors, and cookie-parser
- npm

## Folder structure

```text
backend/
├── config/
│   └── db.js
├── controllers/
│   └── auth-controller.js
├── middleware/
│   ├── auth.js
│   ├── error-handler.js
│   └── not-found.js
├── models/
│   └── user.js
├── routes/
│   ├── auth.js
│   └── health.js
├── scripts/
│   └── seed-users.js
├── utils/
│   └── safe-user.js
├── .env.example
├── .gitignore
├── package.json
├── package-lock.json
└── server.js
```

The `services/` directory remains available for future business logic.

## Environment variables

Copy `.env.example` to `.env` and update values for your environment. `.env` is ignored by git.

| Variable | Purpose | Default/example |
| --- | --- | --- |
| `PORT` | HTTP server port | `5000` |
| `MONGO_URI` | MongoDB connection string (required) | `mongodb://127.0.0.1:27017/campusconnect` |
| `CLIENT_URL` | Allowed frontend origin for credentialed CORS | `http://localhost:5173` |
| `ML_SERVICE_URL` | Reserved for future ML-service integration | `http://127.0.0.1:8000` |
| `JWT_SECRET` | Secret used to sign and verify authentication tokens | Generate a long, random value; never commit it |
| `JWT_EXPIRES_IN` | JWT lifetime | `1d` |
| `NODE_ENV` | Runtime environment; production cookies are secure | `development` |

## MongoDB setup

Install and start MongoDB locally, then ensure it accepts connections at `127.0.0.1:27017`. The service requires `MONGO_URI` and connects to MongoDB before opening its HTTP port. If the connection fails, startup exits with an error instead of serving requests.

## Installation

From the `backend/` directory:

```sh
npm install
```

Copy `.env.example` to `.env` before starting the service. In PowerShell, use `Copy-Item .env.example .env`.

## Development seed users

Seed the development student and faculty accounts with hashed passwords:

```sh
npm run seed
```

The script is idempotent and does not overwrite existing accounts. Both seed users use the development password `Campus@123`; do not use these accounts outside local development.

## Development

```sh
npm run dev
```

## Production start

```sh
npm start
```

The server listens at `http://localhost:5000` by default. Set `PORT` to use a different port.

## Health endpoint

`GET http://localhost:5000/api/health` returns HTTP 200:

```json
{
  "status": "ok",
  "service": "CampusConnect Backend"
}
```

## Authentication endpoints

- `POST http://localhost:5000/api/auth/login` accepts `{ "identifier": "CS21041", "password": "Campus@123" }`; identifier may be a roll number, employee ID, or email. The JWT is issued only in an HTTP-only cookie.
- `POST http://localhost:5000/api/auth/logout` clears the authentication cookie.
- `GET http://localhost:5000/api/auth/me` requires the authentication cookie and returns the safe current-user profile.

For browser requests, include credentials so the browser sends and receives the cookie. CORS allows the configured `CLIENT_URL` with credentials.
