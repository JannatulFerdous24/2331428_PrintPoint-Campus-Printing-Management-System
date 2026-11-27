# PrintPoint — Campus Printing Management System
## CSE309 Final Project Report (Autumn 2026)

| Field | Value |
|---|---|
| Project | PrintPoint — Campus Printing Management System |
| Student ID | 2331428 |
| GitHub | JannatulFerdous24 |
| Course | CSE309 — Web Application Development, Autumn 2026 |
| Repository | https://github.com/JannatulFerdous24/2331428_PrintPoint-Campus-Printing-Management-System |
| Live application | https://2331428.vercel.app |
| API base / docs | https://2331428.vercel.app/api · https://2331428.vercel.app/api/docs |
| Final branch | `main` (mid-project snapshot preserved as tag `mid-project-final`) |
| Report date | 27 November 2026 |

> **How to use this report.** Part A (PRD) explains *what* was built and *why*, Part B (SRS) states the requirements precisely, Part C (TDD) explains *how* it is built, Part D lists the evidence (live verification) and Part E covers running, limitations and sources. Demo-account passwords are **not** in this file or anywhere in the repository; they are supplied separately in the submission form.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Part A — Product Requirements (PRD)](#part-a--product-requirements-prd)
3. [Part B — Software Requirements Specification (SRS)](#part-b--software-requirements-specification-srs)
4. [Part C — Technical Design (TDD)](#part-c--technical-design-tdd)
5. [Part D — Evidence](#part-d--evidence)
6. [Part E — Running, Work Log, Limitations, Sources](#part-e--running-work-log-limitations-sources)

---

## 1. Executive Summary

### 1.1 What PrintPoint is
PrintPoint replaces the paper/queue-at-the-counter process of a campus print shop. Students submit print jobs online (upload a PDF/DOCX, choose pages, copies and black-&-white or colour), see the price before submitting and track the job until it is collected. Print-shop staff work from a digital queue, move jobs through a fixed status workflow, record payment and moderate content from an admin dashboard.

### 1.2 What the final project added to the mid project
The mid project delivered print-request CRUD (FastAPI + SQLite + React). The final project added:

- **Authentication:** signup/login with Argon2id + pepper password hashing, short-lived JWT access tokens (≤ 15 min), httpOnly refresh cookie with rotation and reuse detection, logout, session list and revoke, account lockout and per-IP rate limiting.
- **RBAC:** a single `rbac.py` module with permission constants, role → permission mapping, a `require_permission` dependency, ownership checks and admin safety rules.
- **Groups:** shared groups with per-member `can_create`, `can_edit`, `can_assign` flags; only the owner renames/deletes/manages members.
- **Workflow:** `Pending → Processing → Ready → Collected` or `Pending → Rejected` (reason required) with a status-history timeline.
- **Documents:** PDF/DOCX upload validated by content, stored in a private Supabase Storage bucket, downloaded through short-lived signed links.
- **Printing cost and payment:** cost = pages × copies × rate (B&W Tk 2/page, Colour Tk 10/page) calculated on the server; staff-only Paid/Unpaid tracking, audited.
- **Admin dashboard:** statistics, user management (ban/unban with reason, bulk actions, role change, revoke sessions), moderation, audit log, failed-login view, CSV exports.
- **Dark / light theme** remembered across reloads.
- **Production infrastructure:** Supabase PostgreSQL (Row Level Security on every table), Alembic migrations 0001–0004, Vercel deployment.

### 1.3 Live links

| What | URL |
|---|---|
| Frontend | https://2331428.vercel.app |
| API | https://2331428.vercel.app/api |
| Swagger / OpenAPI | https://2331428.vercel.app/api/docs |
| Health | https://2331428.vercel.app/api/health |

---

## Part A — Product Requirements (PRD)

### A1. Problem
Campus print shops take jobs by USB stick or e-mail, prices are calculated by hand, students wait at the counter without knowing whether a job is ready, and staff have no record of who paid. Group assignments (one student printing for a team) are coordinated informally.

### A2. Goals and success criteria

| Goal | Measure |
|---|---|
| Students submit and track jobs without visiting the counter | request created with document, status visible at any time |
| Transparent pricing | price shown before submit; server-calculated amount identical to the shown estimate |
| Staff have a single queue | every job visible to staff, filterable by status/type/payment/date |
| Accountability | every status, payment, ban, role and moderation action is in the audit log |
| Secure by default | no user can read or change another user's data; admin-only actions return 403 for students |

### A3. Users / personas

| Persona | Role in system | Needs |
|---|---|---|
| Student | `user` | submit jobs, see price, track status, share jobs with a team |
| Team member | `user` + group membership | create/edit team jobs according to the permission the owner gave |
| Print-shop staff / administrator | `admin` | process queue, record payment, manage users, moderate, review security |

### A4. User stories

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-01 | visitor | sign up with e-mail and a strong password | I get my own account |
| US-02 | student | log in and stay logged in safely | I do not re-enter my password every 15 minutes |
| US-03 | student | upload a PDF/DOCX with pages, copies and print type | the shop prints exactly what I need |
| US-04 | student | see the price before I submit | I know what I will pay |
| US-05 | student | track the status and see the rejection reason | I know when to collect or what to fix |
| US-06 | student | edit or delete my job while it is still Pending and unpaid | I can correct mistakes |
| US-07 | group owner | create a group and give each member create/edit/assign rights | the team shares print jobs safely |
| US-08 | group member | create or edit team jobs only if I was allowed | rights are respected |
| US-09 | staff | see a queue filtered by status/payment and move jobs through the workflow | I process jobs in order |
| US-10 | staff | mark a job Paid (or undo a mistake) | payment is recorded |
| US-11 | admin | ban/unban users with a reason, change roles, revoke sessions | I can stop abuse immediately |
| US-12 | admin | delete inappropriate requests/groups and see an activity log | the system stays clean and accountable |
| US-13 | admin | export users, requests and activity as CSV | I can report to the department |
| US-14 | any user | switch between dark and light mode | the app is comfortable to use |
| US-15 | any user | log out and revoke my other sessions | a lost device cannot keep access |

### A5. Scope

**In scope:** everything listed in 1.2.
**Out of scope:** online payment gateway (payment is recorded by staff at the counter), e-mail notifications, printer-driver integration, multi-shop support, e-mail verification / password reset by e-mail.

---

## Part B — Software Requirements Specification (SRS)

### B1. Roles
- **user (Student)** — default role for every signup. Signup can never create an admin.
- **admin (Print-Shop Staff)** — created with `backend/scripts/create_admin.py` or by an admin changing a role.

### B2. Functional requirements

**FR-AUTH — Authentication**

| ID | Requirement |
|---|---|
| FR-AUTH-1 | Signup with e-mail (unique, case-insensitive), full name, password (≥ 10 chars, letters + digits; weak passwords rejected with 422). |
| FR-AUTH-2 | Passwords stored as Argon2id(HMAC-SHA256(pepper, password)); never logged or returned. |
| FR-AUTH-3 | Login returns a JWT access token (HS256, lifetime ≤ 15 min) and sets an httpOnly refresh cookie (path `/api/auth`, Secure on HTTPS). |
| FR-AUTH-4 | `/api/auth/refresh` rotates the refresh token; re-use of an old token (after a 30-s grace period) revokes the session. Requires header `X-Requested-With` (CSRF protection). |
| FR-AUTH-5 | Logout revokes the session; the old access token and refresh cookie stop working immediately. |
| FR-AUTH-6 | Missing, malformed, tampered, wrong-signature or expired tokens → 401. |
| FR-AUTH-7 | 5 wrong passwords lock the account temporarily; too many failures from one IP → 429. Error messages do not reveal whether an e-mail exists. |
| FR-AUTH-8 | Users list and revoke their sessions, update profile, change password (current password required; other sessions revoked). |

**FR-RBAC — Authorization**

| ID | Requirement |
|---|---|
| FR-RBAC-1 | Permissions are defined once (`Permission` enum) and mapped to roles (`ROLE_PERMISSIONS`). |
| FR-RBAC-2 | Admin endpoints use `require_permission(...)`; a student receives 403. |
| FR-RBAC-3 | A student sees only own requests and requests of groups they belong to; any other ID returns 404 (no information leak). |
| FR-RBAC-4 | Group requests follow member flags: create (`can_create`), edit (`can_edit`), assign (`can_assign`); owner-only rename, delete, member management. |
| FR-RBAC-5 | Admin safety: admins cannot ban themselves or other admins and cannot change their own role. |
| FR-RBAC-6 | Role is re-read from the database on every request, so a ban or role change applies on the next request. |

**FR-DOMAIN — Print requests, cost, payment, documents**

| ID | Requirement |
|---|---|
| FR-DOM-1 | Create/read/update/delete print requests (student name, document name, pages 1–1000, copies 1–999, print type, notes, optional group). |
| FR-DOM-2 | `total_cost = pages × copies × rate`, rate B&W Tk 2, Colour Tk 10; calculated by the server on create/edit; any client-sent price is ignored. `GET /api/print-requests/pricing` publishes the rates. |
| FR-DOM-3 | Status workflow Pending → Processing → Ready → Collected, Pending → Rejected; only staff change status; rejection needs a 5–500 character reason. Every change is stored in status history. |
| FR-DOM-4 | Payment status Pending/Paid; only staff (`request:update_payment`) change it; `paid_at` recorded; a Rejected request cannot be marked Paid (409); a Paid request can no longer be edited (403). |
| FR-DOM-5 | One PDF/DOCX per request, ≤ 4 MB, validated by magic bytes, stored privately; download via a 60-second signed URL after a permission check. |
| FR-DOM-6 | Listing supports search, filters (status, type, payment, has document, dates), sorting and paging (`X-Total-Count`). |

**FR-ADM — Admin dashboard**

| ID | Requirement |
|---|---|
| FR-ADM-1 | Statistics (users, banned users, admins, requests by status, groups, new users/requests in 7 days, failed logins in 24 h). |
| FR-ADM-2 | User list with search/filters/paging, user detail (requests, groups, sessions, activity). |
| FR-ADM-3 | Ban/unban (reason required), bulk ban/unban, role change, revoke sessions. |
| FR-ADM-4 | Moderation: delete any request or group (single or bulk), audited. |
| FR-ADM-5 | Audit log with filters; failed-login view by IP and account. |
| FR-ADM-6 | CSV export of users, print requests (incl. pages, cost, payment) and audit log, respecting filters. |

### B3. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Security | Secrets only in environment variables; app refuses to start on Vercel if `DATABASE_URL`, `JWT_SECRET` or `PASSWORD_PEPPER` are missing or weak (< 32 chars). |
| NFR-2 | Security | CORS restricted to the frontend origin; JSON error bodies without stack traces. |
| NFR-3 | Security | Row Level Security enabled on every table (no anonymous Supabase Data API access). |
| NFR-4 | Persistence | Hosted PostgreSQL; schema changes only through Alembic migrations. |
| NFR-5 | Usability | Responsive UI; dark/light theme without flash on load; deep links reload correctly. |
| NFR-6 | Maintainability | One RBAC module; UI receives the same permission flags the server enforces. |
| NFR-7 | Testability | Automated backend (pytest) and frontend (node:test) tests. |

### B4. Permission matrix

| Permission | user | admin |
|---|:-:|:-:|
| request:create / read_own / update_own / delete_own | ✅ | ✅ |
| group:create | ✅ | ✅ |
| request:read_all | ❌ | ✅ |
| request:update_status | ❌ | ✅ |
| request:update_payment | ❌ | ✅ |
| content:moderate | ❌ | ✅ |
| user:read / user:ban / user:change_role / user:revoke_sessions | ❌ | ✅ |
| audit:read / data:export | ❌ | ✅ |

Group-level (inside one group): owner = all; member = only the flags set by the owner (`can_create`, `can_edit`, `can_assign`); viewing is allowed for every member.

### B5. Use cases

| UC | Actor | Main flow | Alternatives / errors |
|---|---|---|---|
| UC-1 Sign up & log in | Visitor | enter e-mail, name, password → account (role user) → tokens | duplicate e-mail → 409; weak password → 422; wrong password → 401; locked or rate-limited → 429 |
| UC-2 Submit print job | Student | fill form → see estimate → submit → upload document | invalid pages/copies → 422; non-PDF/DOCX → 4xx |
| UC-3 Track job | Student | open list/detail → status, history, cost, payment | foreign ID → 404 |
| UC-4 Process queue | Staff | filter queue → Processing → Ready → Collected | reject requires reason → 422 without |
| UC-5 Record payment | Staff | Mark as paid → `paid_at` set, audited; undo possible | Rejected → 409; student → 403 |
| UC-6 Team printing | Group owner / member | owner creates group, adds members with flags; members act within flags | missing flag → 403; non-owner rename → 403 |
| UC-7 Moderate & manage users | Admin | ban with reason, unban, change role, delete content, export CSV | ban admin/self → 403 |
| UC-8 Session security | Any user | refresh silently; logout; revoke other sessions | reused/rotated token → 401 |

### B6. Acceptance criteria (Given / When / Then)

1. **Given** a student is logged in, **when** they open another student's request ID, **then** the API returns 404.
2. **Given** a student token, **when** it calls `/api/admin/stats`, **then** 403.
3. **Given** an expired or forged access token, **when** any protected endpoint is called, **then** 401.
4. **Given** a logged-out session, **when** the old refresh cookie is used, **then** 401.
5. **Given** a B&W request with 5 pages × 2 copies, **when** created, **then** `total_cost = 20`; **when** changed to Colour, **then** `total_cost = 100`, even if the client sent another price.
6. **Given** a student, **when** they try to mark a request Paid, **then** 403; **given** staff, **then** 200 and `paid_at` set and an audit entry `request.payment` exists.
7. **Given** a Paid request, **when** the owner edits it, **then** 403.
8. **Given** a view-only group member, **when** they create or edit a group request, **then** 403, but they can view it.
9. **Given** a member without `can_assign`, **when** they set an assignee, **then** 403; the owner succeeds.
10. **Given** a banned user, **when** they log in, **then** login is refused.
11. **Given** the dark theme was chosen, **when** the page reloads, **then** it stays dark.

### B7. Traceability

| Requirement | Implementation | Tests |
|---|---|---|
| FR-AUTH-1…8 | `auth/router.py`, `auth/service.py`, `auth/security.py`, `auth/tokens.py`, `auth/dependencies.py` | `tests/test_auth.py`, `test_auth_postgres_integration.py` |
| FR-RBAC-1…6 | `rbac.py`, `routers/*` | `tests/test_rbac.py`, `test_rbac_postgres_integration.py` |
| FR-DOM-1,3,6 | `crud.py`, `routers/print_requests.py` | `test_print_requests.py`, `test_workflow.py` |
| FR-DOM-2,4 | `pricing.py`, `crud.update_payment_status` | `test_cost_payment.py` |
| FR-DOM-5 | `documents.py`, `storage.py` | `test_documents.py` |
| FR-ADM-1…6 | `routers/admin.py`, `audit.py` | `test_admin_dashboard.py` |
| NFR-1 | `config.py`, `database.py` | `test_database_config.py` |
| NFR-4 | `migrations/versions/0001…0004` | `test_migrations.py` |
| NFR-5 (theme) | `frontend/src/theme.ts`, `ThemeToggle.tsx`, `index.html` | `frontend/tests/theme.test.ts` |

---

## Part C — Technical Design (TDD)

### C1. Technology stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React 19 + TypeScript + Vite + React Router | typed components, fast build, client-side routing |
| Backend | FastAPI, SQLModel/SQLAlchemy, Pydantic | automatic validation and OpenAPI docs, dependency injection for auth/RBAC |
| Auth | PyJWT (HS256), argon2-cffi | standard, well-reviewed primitives |
| Database | Supabase PostgreSQL via psycopg 3 (transaction pooler 6543; session pooler 5432 for migrations) | managed Postgres that persists across serverless invocations |
| Migrations | Alembic | versioned, reviewable schema changes |
| Files | Supabase Storage (private bucket `print-documents`) | private objects + signed URLs |
| Hosting | Vercel (services: FastAPI + Vite) | one domain for UI and API → no cross-site cookies |
| Tests | pytest, Node built-in test runner | no extra frontend test dependencies |

### C2. Architecture

```
Browser (React SPA)
   │  HTTPS, same origin https://2331428.vercel.app
   ▼
Vercel edge ── /api/*  ──► FastAPI service (Python 3.12, serverless)
          └── /*      ──► Vite static build (SPA fallback to index.html)
                                   │
                ┌──────────────────┼────────────────────┐
                ▼                  ▼                    ▼
   Supabase PostgreSQL     Supabase Storage       (env vars: secrets)
   (RLS on all tables)     private bucket
```

Request pipeline in FastAPI: CORS → router → `get_current_user` (JWT verify + DB reload of the user, ban check) → `require_permission` / ownership/group check in `rbac.py` → `crud` → audit log → JSON response.

### C3. Project structure
```
backend/  main.py, config.py, database.py, models.py, schemas.py, rbac.py, crud.py,
          pricing.py, documents.py, storage.py, audit.py,
          auth/ (router, service, security, tokens, dependencies),
          routers/ (print_requests, groups, admin), migrations/versions/0001–0004,
          scripts/ (create_admin, seed_demo, setup_storage_bucket, run_with_env), tests/
frontend/ src/ (auth/, api/, components/, pages/, types/, theme.ts), tests/, index.html
vercel.json  services + rewrites
docs/     FINAL_REPORT.md (this file), PRD.md / SRS.md / TDD.md (mid-project versions)
```

### C4. Data model (PostgreSQL, 9 tables)

| Table | Key columns | Notes |
|---|---|---|
| `users` | id, email (unique, lower-case), full_name, password_hash, role, is_banned, ban_reason, banned_at, banned_by_id, failed_login_count, locked_until, password_changed_at | role ∈ {user, admin} |
| `refresh_sessions` | user_id, token_hash (SHA-256), previous_token_hash, ip, user_agent, expires_at, revoked_at, revoked_reason | raw refresh token never stored |
| `login_attempts` | email_attempted, user_id, ip, success, failure_reason | lockout, rate limit, security view |
| `audit_logs` | actor_id, action, target_type, target_id, details (JSON), ip | e.g. `request.payment`, `user.ban` |
| `groups` | name, description, owner_id | |
| `group_members` | group_id, user_id, can_create, can_edit, can_assign, added_by_id | unique (group, user) |
| `print_requests` | owner_id, group_id, assignee_id, student_name, document_name, pages, copies, print_type, status, notes, total_cost, payment_status, paid_at, storage_path, original_filename, content_type, file_size_bytes | |
| `print_request_status_history` | print_request_id, from_status, to_status, changed_by_id, note | timeline + rejection reason |
| `alembic_version` | version_num | current head `0004_cost_and_payment` |

Relationships: user 1—n print_requests (owner), user 1—n groups (owner), group n—m users via group_members, print_request 1—n status_history, user 1—n refresh_sessions/login_attempts/audit_logs.

Migrations: `0001_create_print_requests` (mid project) → `0002_core_security_schema` (auth, groups, audit, history, RLS) → `0003_owner_required` → `0004_cost_and_payment` (adds pages, total_cost, payment_status enum, paid_at, and back-fills cost for existing rows).

### C5. API design
REST + JSON, documented at `/api/docs`. Errors are `{"detail": "..."}` with 400/401/403/404/409/413/415/422/429.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/signup`, `/login`, `/refresh`, `/logout`; `GET /api/auth/me`; `GET /api/auth/sessions`, `DELETE /api/auth/sessions/{id}`, `POST /api/auth/sessions/revoke-others` |
| Account | `GET/PATCH /api/users/me`, `POST /api/users/me/password` |
| Print requests | `GET/POST /api/print-requests`, `GET /pricing`, `GET/PUT/PATCH/DELETE /{id}`, `GET /{id}/history`, `PUT/GET /{id}/document`, `PATCH /{id}/assignee`, `PATCH /{id}/payment` |
| Groups | `GET/POST /api/groups`, `GET/PATCH/DELETE /api/groups/{id}`, `POST/PATCH/DELETE /api/groups/{id}/members[/{user_id}]` |
| Admin | `GET /api/admin/stats`, `/users`, `/users/{id}`, `POST /users/{id}/ban`, `/unban`, `/users/bulk-ban`, `/bulk-unban`, `/users/{id}/revoke-sessions`, `PATCH /users/{id}/role`, `GET /groups`, `DELETE /print-requests/{id}`, `POST /print-requests/bulk-delete`, `DELETE /groups/{id}`, `POST /groups/bulk-delete`, `GET /audit-logs`, `/security/failed-logins`, `/export/users.csv`, `/export/print-requests.csv`, `/export/audit-logs.csv` |

Every print-request response includes a `permissions` object (`view, edit, delete, change_status, assign, update_payment`) computed by the same function the server uses for enforcement, so the UI only shows buttons the server will accept.

### C6. Authentication and JWT design
- **Access token:** HS256 JWT, lifetime `ACCESS_TOKEN_MINUTES` (configured ≤ 15, enforced by `config.py`). Claims: `sub` (user id), `role`, `sid` (refresh-session id), `type="access"`, `iat`, `exp`, `jti`. Kept in memory by the frontend (not in localStorage).
- **Verification** (`auth/dependencies.py`): signature, expiry, type; then the session `sid` must still be active and the user is reloaded from the database (banned → rejected, role taken from DB).
- **Refresh token:** 256-bit random value in the httpOnly cookie `pp_refresh` (path `/api/auth`, SameSite=Lax, Secure in production); only its SHA-256 hash is stored. Each refresh rotates it; presenting an already-rotated token outside a 30-second grace window revokes the session (reuse detection).
- **CSRF:** `/refresh` and `/logout` require `X-Requested-With: XMLHttpRequest`, which a cross-site page cannot send without passing CORS.
- **Passwords:** Argon2id over HMAC-SHA256(`PASSWORD_PEPPER`, password) with a random per-hash salt; lockout after 5 failures; per-IP rate limit.
- **Frontend:** `AuthContext` refreshes silently on load and on 401, then retries the request once.

### C7. RBAC design
All authorization lives in `backend/rbac.py`:

```python
ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.user: frozenset(_STUDENT),
    UserRole.admin: frozenset(Permission),  # every permission
}

def require_permission(*permissions: Permission):
    def dependency(user: User = Depends(get_current_user)) -> User:
        missing = [p for p in permissions if not has_permission(user, p)]
        if missing:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail="You do not have permission to perform this action")
        return user
    return dependency
```

Object-level rules (`request_permissions`): view = owner or group member or `request:read_all`; edit = (Pending and not Paid) and (owner or group `can_edit`); delete = owner or group owner; assign = group `can_assign`; change_status / update_payment = staff permission. Invisible objects return 404, not 403, so IDs cannot be probed. Admin safety rules: no self-ban, no banning admins, no self role change.

### C8. Admin dashboard design
React pages `AdminDashboardPage`, `AdminUsersPage`, `AdminUserDetailPage`, `AdminModerationPage`, `AdminAuditPage`, `StaffQueuePage`, guarded by an admin-only route guard on the client **and** `require_permission` on every `/api/admin/*` endpoint. Every admin action writes an `audit_logs` row (actor, action, target, details, IP). CSV exports stream the same filtered queries as the tables.

### C9. Printing cost, payment and theme
- `backend/pricing.py`: `RATES_PER_PAGE = {B&W: 2, Color: 10}`, `calculate_cost(pages, copies, type)`. Called on create and whenever pages/copies/type change.
- `crud.update_payment_status`: 409 for Rejected→Paid, sets/clears `paid_at`, writes `request.payment` audit entry with `{from, to, amount}`.
- Frontend form fetches `/pricing` and shows a live estimate; the list/queue show a Paid/Unpaid badge and staff get "Mark as paid / Undo paid".
- Theme: CSS custom properties with a `:root[data-theme="dark"]` override; choice stored in `localStorage["printpoint-theme"]`, OS preference used until the user chooses; an inline script in `index.html` applies it before React renders (no flash).

### C10. Threat model (summary)

| Threat | Mitigation |
|---|---|
| Password database leak | Argon2id + pepper stored outside the DB |
| Token theft / long-lived tokens | ≤ 15-min access token in memory; httpOnly refresh cookie; rotation + reuse detection; logout/revoke |
| Forged / tampered JWT | HS256 signature with secret ≥ 32 chars; `type` and session checks |
| IDOR (changing IDs) | ownership/group check on every object, 404 for invisible objects |
| Privilege escalation | role never accepted from client; signup always `user`; admin safety rules |
| Brute force | lockout + IP rate limit + generic error message |
| CSRF on cookie endpoints | `X-Requested-With` requirement + strict CORS |
| Malicious uploads | magic-byte validation, 4 MB limit, private bucket, signed URLs |
| Price manipulation | cost computed on server, client price ignored |
| Direct database access | RLS on all tables; service keys only on the server |

### C11. Deployment (Vercel)
- `vercel.json` defines two services: `backend` (FastAPI, `main:app`) and `frontend` (Vite). Top-level rewrites send `/api/*` to the backend and everything else to the frontend; the frontend service rewrites unknown paths to `/index.html` so React Router deep links (e.g. `/admin/users`) reload correctly.
- Production environment variables (names only): `DATABASE_URL`, `JWT_SECRET`, `PASSWORD_PEPPER`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS`, `CORS_ORIGINS`, `COOKIE_SECURE`. `MIGRATION_DATABASE_URL` is used only locally by Alembic.
- Separate Supabase projects for development and production. Migrations are applied with Alembic before deploying; a push to `main` triggers a Production deployment.

### C12. Testing strategy
- **Backend (pytest):** 165 tests collected; 145 run by default on in-memory SQLite, 20 PostgreSQL integration tests run when `RUN_PG_INTEGRATION=1`. Suites: auth, RBAC, print requests, workflow, documents, admin dashboard, cost & payment, migrations, database config.
- **Frontend (node:test):** 7 theme tests (`npm test`).
- **Live end-to-end check** against Production (Part D).

---

## Part D — Evidence

### D1. Live Production verification (27 Nov 2026)
A scripted end-to-end check was run against **https://2331428.vercel.app** using the seeded demo accounts and one temporary account that was deleted afterwards. Results (all genuine, from the live deployment):

| Area | Checks | Result |
|---|---|---|
| Frontend & routing | `/` loads, theme bootstrap present, deep link `/admin` reloads | ✅ (deep-link reload fixed in this release — see D2) |
| Health & docs | `/api/health` 200 `{"status":"ok"}`, `/api/docs` 200 | ✅ |
| Signup / login | signup 201 (role user, httpOnly cookie), duplicate rejected, weak password 422, wrong password 401, `/api/users/me` | ✅ |
| JWT | no token 401, garbage token 401, expired token 401, forged signature 401, lifetime ≤ 15 min | ✅ |
| Refresh / logout | refresh without `X-Requested-With` 403, rotation, rotated token rejected 401, logout 204, refresh and access token rejected after logout | ✅ |
| CORS | foreign origin not allowed | ✅ |
| RBAC | student → admin API 403; other student's request 404 (view, edit, document); student cannot change status or payment (403) | ✅ |
| Cost | pricing endpoint B&W 2 / Colour 10; 5×2 B&W = Tk 20; changed to Colour = Tk 100; client price ignored; seeded rows consistent | ✅ |
| Workflow | Processing → Ready → Collected, history recorded; reject without reason 422, with reason 200 | ✅ |
| Payment | staff marks Paid (paid_at set); Rejected cannot be Paid (409) | ✅ |
| Documents | PDF upload 200, owner signed link downloads the file, other student 404, non-PDF rejected | ✅ |
| Groups | view-only member sees but cannot create/edit (403); can_create member creates; can_edit member edits; member without can_assign 403; owner assigns; non-owner rename 403 | ✅ |
| Admin | stats, users, groups, failed logins; ban → banned user cannot log in → unban; student cannot ban; moderation delete 204; audit log contains payment/ban events; 3 CSV exports, print-requests CSV has cost/payment columns | ✅ |

### D2. Issues found during final deployment and how they were fixed
1. **All `/api/*` returned `FUNCTION_INVOCATION_FAILED`.** Runtime log: `RuntimeError: DATABASE_URL is not set`. Cause: the Vercel project had no environment variables. Fix: the 10 variables were added to the Production environment with the Vercel CLI (values read from a local file, never printed) and Production was redeployed. The start-up check in `database.py` worked as designed (it fails loudly instead of silently using SQLite).
2. **Reloading a deep link (e.g. `/admin`) returned Vercel 404.** Cause: with Vercel *services*, a request routed into the frontend service does not fall back to top-level rewrites. Fix: an SPA rewrite `/(.*) → /index.html` inside the `frontend` service in `vercel.json` (verified on a Preview deployment first: deep links 200, assets still served, `/api` still reaches FastAPI).

### D3. Screenshots
No screenshots are included in this Markdown report; none were captured into the repository, and this report does not reproduce images it does not have. The behaviour can be inspected directly on the live site with the demo accounts listed in the README.

---

## Part E — Running, Work Log, Limitations, Sources

### E1. Run and test locally
```bash
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # fill in values
alembic upgrade head
uvicorn main:app --reload --port 8000
cd ../frontend && npm install && npm run dev     # http://localhost:5173

cd backend && python -m pytest -q                # 145 passed, 20 PG integration skipped
cd frontend && npm test                          # 7 passed
```
First admin: `python scripts/create_admin.py --email you@example.com --name "Your Name"`. Demo data (development/demo only, dry run by default): `python scripts/seed_demo.py --execute --out <file outside repo>`.

### E2. GitHub work
- `feature/1-print-request-crud` → mid project (merged in PR #4), snapshot tag `mid-project-final`.
- `feature/2-auth-rbac-supabase` → final project: auth, RBAC, groups, workflow, documents, admin dashboard; then cost/payment, dark mode, documentation and deployment fixes; fast-forwarded into `main`.

### E3. Limitations
- Payment is recorded by staff; there is no online payment gateway.
- No e-mail verification, password-reset e-mail or notifications.
- Single print shop, fixed rates in code (`pricing.py`); changing rates requires a deploy.
- Rate limiting is database-based (per IP/account), not a distributed edge limiter.
- Uploads are limited to 4 MB by Vercel's request size.
- Automated UI (browser) tests are not included; UI behaviour was checked manually and through the API.

### E4. Future work
Online payment (bKash/card), e-mail notifications when a job is Ready, rate table editable by admins, printer queue integration, multiple shops, browser E2E tests (Playwright), file preview.

### E5. Sources and tools
- FastAPI, SQLModel, Pydantic, Alembic, PyJWT, argon2-cffi, psycopg documentation.
- Supabase docs (PostgreSQL pooling, Row Level Security, Storage signed URLs).
- Vercel docs (services, rewrites, environment variables).
- OWASP Cheat Sheets (Password Storage, JWT, Session Management, CSRF).
- React, React Router and Vite documentation.
- **AI assistance:** Claude (Anthropic) via Claude Code was used as a coding assistant for implementation, tests, debugging the deployment and drafting documentation. All code was reviewed, tested and committed by the student.
