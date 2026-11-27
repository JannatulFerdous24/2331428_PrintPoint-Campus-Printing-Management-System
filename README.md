# PrintPoint — Campus Printing Management System

[![Frontend](https://img.shields.io/badge/Frontend-React_19_+_TypeScript_+_Vite-61dafb?logo=react)](https://react.dev/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-Supabase_PostgreSQL-3ECF8E?logo=supabase)](https://supabase.com/)
[![Deployment](https://img.shields.io/badge/Deploy-Vercel-black?logo=vercel)](https://vercel.com/)

PrintPoint lets university students submit print jobs online (upload a PDF/DOCX, see the price, track the status) and lets print-shop staff run a digital queue. The CSE309 final project extends the mid project with JWT authentication, role-based access control (RBAC), shared groups with per-member permissions and an admin dashboard.

## 🔗 Live links

| What | URL |
|---|---|
| Frontend | https://2331428.vercel.app |
| API (base) | https://2331428.vercel.app/api |
| API docs (Swagger) | https://2331428.vercel.app/api/docs |
| Health check | https://2331428.vercel.app/api/health |
| Final report | [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md) |

The deployed app is built from the `main` branch. Data is stored in a hosted **Supabase PostgreSQL** database (not SQLite), so it survives restarts.

## 👥 Test accounts (for the instructor)

Passwords are **not** in this repository. They are given only in the submission form and the PDF report.

| User ID (email) | Role | Notes |
|---|---|---|
| `demo.admin1@uni.edu` | admin (Print-Shop Staff) | dashboard, users, moderation, audit log, staff queue |
| `demo.admin2@uni.edu` | admin (Print-Shop Staff) | second admin (shows "admin cannot ban another admin") |
| `demo.student1@uni.edu` | user (Student) | owner of the shared group |
| `demo.student2@uni.edu` | user (Student) | group member: can create + edit, cannot assign |
| `demo.student3@uni.edu` | user (Student) | group member: view only |

**Shared group with mixed permissions:** `CSE309 Project Team`

| Member | Create | Edit | Assign | Rename / delete / manage members |
|---|---|---|---|---|
| demo.student1 (owner) | ✅ | ✅ | ✅ | ✅ (owner only) |
| demo.student2 | ✅ | ✅ | ❌ | ❌ |
| demo.student3 | ❌ | ❌ | ❌ | ❌ (view only) |

Sample data: 6 print requests covering every status (Pending, Processing, Ready, Collected, Rejected with a reason), paid and unpaid, personal and group requests.

## 🚀 Features

**Students (role `user`)**
- Sign up, log in, update profile, change password (current password required), list and revoke own sessions.
- Create print requests with a PDF/DOCX upload (max 4 MB, stored in a private bucket), page count, copies and print type.
- **Printing cost:** the form shows the estimated price before submitting (B&W Tk 2/page, Color Tk 10/page; total = pages × copies × rate). The server recalculates and stores the amount; the browser's price is never trusted.
- **Payment status:** every request shows Paid / Unpaid. A paid request can no longer be edited.
- See only their own requests and their groups' requests (other IDs return 404).
- Groups: create a group, add members with different permissions (create, edit, assign); only the owner renames, deletes or manages members.

**Print-shop staff (role `admin`)**
- Staff queue: tabs per status, search, filters (type, payment, document, dates), oldest first.
- Status workflow `Pending → Processing → Ready → Collected` or `Pending → Rejected` (reason required, shown to the student), with a status history timeline.
- Mark a request as **Paid** (or undo); recorded in the audit log.
- Admin dashboard: statistics, user list with search/filters/paging, user detail (requests, groups, sessions, activity), ban/unban with reason, bulk ban/unban, role change, revoke sessions, content moderation (delete one or many requests/groups), activity (audit) log with filters, security view (failed logins by IP and account), CSV exports of users, requests and activity that respect the filters.

**Everyone:** 🌙/☀️ dark / light mode toggle on every page, remembered across reloads.

## 🔐 Security summary

| Topic | Implementation | Code |
|---|---|---|
| Passwords | Argon2id( HMAC-SHA256(PASSWORD_PEPPER, password) ); random salt per hash; pepper only in env | `backend/auth/security.py` |
| Access token | JWT HS256, ≤ 15 min, claims `sub` (user id), `role`, `sid`, `type`, `iat`, `exp`, `jti`; verified on every request | `backend/auth/tokens.py`, `auth/dependencies.py` |
| Refresh / logout | random token in an httpOnly cookie, only its SHA-256 hash stored; rotation + reuse detection; logout revokes the session | `backend/auth/router.py`, `auth/service.py` |
| RBAC | one module: permission constants, `require_permission` dependency, ownership + group checks, admin safety rules | `backend/rbac.py` |
| Banned / role change | user re-loaded from the database on every request, so it applies on the very next request | `backend/auth/dependencies.py` |
| Brute force | account lockout after 5 wrong passwords + per-IP limit (429) | `backend/auth/service.py` |
| Files | type checked by content (magic bytes), private bucket, 60-second signed download links after a permission check | `backend/documents.py`, `backend/storage.py` |
| Database | Row Level Security enabled on every table (no public Data API access) | `backend/migrations/` |
| Errors / CORS | consistent JSON errors, no stack traces, CORS limited to the frontend URL | `backend/main.py` |

## 🛠️ Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, React Router |
| Backend | FastAPI, SQLModel / SQLAlchemy, Pydantic, PyJWT, argon2-cffi |
| Database | Supabase PostgreSQL (psycopg 3, transaction pooler), Alembic migrations |
| File storage | Supabase Storage (private bucket `print-documents`) |
| Tests | pytest (backend), Node built-in test runner (frontend theme logic) |
| Hosting | Vercel (`vercel.json`: `/api/*` → FastAPI, everything else → Vite build) |

## 📁 Project structure

```
backend/
  main.py              FastAPI app, CORS, error handlers, routers
  config.py            settings from environment variables (refuses weak secrets)
  database.py          engine (Supabase pooler or local SQLite) + session dependency
  models.py            tables;  schemas.py  request/response models
  rbac.py              the RBAC module (permissions, ownership, groups, admin safety)
  crud.py              print-request database logic (status history, audit)
  pricing.py           printing rates and cost calculation
  documents.py / storage.py   upload validation / private Supabase Storage
  audit.py             activity log helper
  auth/                router.py + service.py (signup/login/refresh/logout), security.py (hashing),
                       tokens.py (JWT), dependencies.py (current user)
  routers/             print_requests, groups, admin
  migrations/versions/ 0001 … 0004 (Alembic)
  scripts/             create_admin, seed_demo, setup_storage_bucket, run_with_env
  tests/               pytest suites
frontend/src/
  auth/                AuthContext (token in memory, silent refresh), route guards
  api/                 typed API clients
  components/, pages/  UI (student pages, staff queue, admin dashboard)
  theme.ts             light/dark theme logic
docs/                  PRD.md, SRS.md, TDD.md, FINAL_REPORT.md
```

## 💻 Run locally

Prerequisites: Python 3.12+, Node.js 22.18+ (or 24).

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # then fill in values (see below)
alembic upgrade head              # create / update the database schema
uvicorn main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /api to :8000)
```

Create the first admin account (signup only ever creates students):

```bash
cd backend
python scripts/create_admin.py --email you@example.com --name "Your Name"   # asks for the password
```

## ⚙️ Environment variables

Names only — values live in `backend/.env` (git-ignored) locally and in Vercel → Settings → Environment Variables (Production) when deployed. See [`backend/.env.example`](backend/.env.example).

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Supabase transaction pooler (port 6543) used by the app |
| `MIGRATION_DATABASE_URL` | Supabase session pooler (port 5432) used by Alembic only (local) |
| `JWT_SECRET` | signs access tokens |
| `PASSWORD_PEPPER` | server-side secret mixed into every password hash |
| `ACCESS_TOKEN_MINUTES` | access token lifetime (1–15) |
| `REFRESH_TOKEN_DAYS` | refresh session lifetime |
| `COOKIE_SECURE` | `true` on HTTPS (always forced on Vercel) |
| `CORS_ORIGINS` | allowed frontend origin(s) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET` | private document storage (backend only) |

Two Supabase projects are used: `printpoint-dev` (local development) and `printpoint-prod` (Vercel Production only).

## 🗄️ Migrations

| Revision | Change |
|---|---|
| `0001_create_print_requests` | mid-project `print_requests` table |
| `0002_core_security_schema` | users, sessions, login attempts, audit log, groups, members, status history (+ RLS) |
| `0003_owner_required` | every print request must have an owner |
| `0004_cost_and_payment` | `pages`, `total_cost`, `payment_status`, `paid_at` |

Preview the SQL without connecting: `alembic upgrade head --sql`.

## 🧪 Tests

```bash
cd backend && python -m pytest -q      # 145 passed (20 PostgreSQL integration tests skipped unless RUN_PG_INTEGRATION=1)
cd frontend && npm test                # 7 theme tests
```

The deployed Production app was also checked end to end (signup/login/refresh/logout, JWT rejection, RBAC, groups, workflow, uploads, cost and payment, admin dashboard, CSV exports) — results in [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md#part-d--evidence).

Covered by unit/integration tests: login, lockout, missing/invalid/tampered/expired tokens (401), refresh rotation and reuse, logout, sessions, RBAC (own vs. other records, admin-only endpoints, group permissions, owner-only actions, admin safety rules, banned users), status workflow, uploads, admin dashboard, CSV exports, migrations, printing cost and payment.

## 📡 Main API endpoints

Full interactive list: **/api/docs**.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/signup`, `/login`, `/refresh`, `/logout`; `GET /api/auth/me`; `GET /api/auth/sessions`, `DELETE /api/auth/sessions/{id}`, `POST /api/auth/sessions/revoke-others` |
| Profile | `GET/PATCH /api/users/me`, `POST /api/users/me/password` |
| Print requests | `GET/POST /api/print-requests`, `GET/PATCH/DELETE /api/print-requests/{id}`, `GET /{id}/history`, `PUT/GET /{id}/document`, `PATCH /{id}/assignee`, `PATCH /{id}/payment` (staff), `GET /pricing` |
| Groups | `GET/POST /api/groups`, `GET/PATCH/DELETE /api/groups/{id}`, members `POST/PATCH/DELETE /api/groups/{id}/members/...` |
| Admin | `/api/admin/stats`, `/users` (+ ban, unban, bulk, role, revoke-sessions), `/groups`, moderation deletes, `/audit-logs`, `/security/failed-logins`, `/export/*.csv` |

## ☁️ Deployment

Vercel project linked to this GitHub repository; every push to `main` deploys Production. `vercel.json` routes `/api/*` to the FastAPI service and everything else to the Vite build; the frontend service rewrites unknown paths to `index.html`, so deep links such as `/admin/users` reload correctly. Production environment variables are set in Vercel; database migrations are applied with Alembic before deploying.

## 📚 Documentation

- [Final report](docs/FINAL_REPORT.md) — PRD, SRS, TDD, live verification evidence, limitations
- Mid-project documents (kept for history): [PRD](docs/PRD.md) · [SRS](docs/SRS.md) · [TDD](docs/TDD.md)

## 📄 License

MIT — see [LICENSE](LICENSE).
