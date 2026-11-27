Independent University, Bangladesh
CSE309 Web Application & Internet

# Final Project Submission Report — PrintPoint: Campus Printing Management System

| | |
|---|---|
| **Name** | Jannatul Ferdous |
| **Student ID** | 2331428 |
| **Section** | 5 |
| **Project type** | Individual |
| **Project title** | PrintPoint — Campus Printing Management System |
| **Vercel URL** | https://2331428.vercel.app |
| **GitHub repository** | https://github.com/JannatulFerdous24/2331428_PrintPoint-Campus-Printing-Management-System |
| **Submitted to** | Sayef Reyadh, Adjunct Lecturer, Department of CSE, Independent University, Bangladesh |
| **Semester** | Autumn 2026 |
| **Date of submission** | 28 November 2026 |


## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [Part A. Product Requirements (PRD)](#part-a-product-requirements-prd)
- [Part B. Software Requirements (SRS)](#part-b-software-requirements-srs)
- [Part C. Technical Design (TDD)](#part-c-technical-design-tdd)
- [Part D. Evidence: Screenshots of the Running Application](#part-d-evidence-screenshots-of-the-running-application)
- [Part E. Project Management and Conclusion](#part-e-project-management-and-conclusion)
- [Appendix A. Test Accounts](#appendix-a-test-accounts)

**List of figures:** Figure 1 use-case diagram · Figure 2 system architecture · Figure 3 ER diagram · Figure 4 JWT sequence · Figure 5 authorization flow · Figure 6 group-permission flow · Figure 7 request workflow state machine · Figure 8 admin pages and endpoints · Figure 9 deployment layout.

**List of screenshots:** S1 signup validation · S1b login error · S2 student requests · S3 wrong current password · S4 sessions · S5 group members and permissions · S6a/S6b RBAC denial (UI and API 403) · S7 expired token 401 · S10 admin dashboard and security view · S11 users list · S12 user detail · S13 admin cannot ban admin · S14a/b/c groups and moderation · S15 audit log · S20 API docs · S22 dark mode · S23 staff queue with cost and payment.

---

## 1. Executive Summary

### 1.1 Project overview

PrintPoint is a web application that moves a university print shop online. Students upload a PDF or DOCX, choose pages, copies and black-&-white or colour printing, see the price before they submit and follow the job until they collect it. Print-shop staff work from a single digital queue, move each job through a fixed status workflow, record payment and administer the system from an admin dashboard. Students can also share print jobs with a team through groups whose owner decides what each member may do.

**Stack:** React 19 + TypeScript (Vite) · FastAPI + SQLModel (Python 3.12) · Supabase PostgreSQL + Supabase Storage · Vercel.

### 1.2 What was built since the mid assessment

The mid project delivered anonymous print-request CRUD on SQLite. The final project added:

- **JWT authentication with refresh and logout** — Argon2id + pepper password hashing, 15-minute access tokens, rotating httpOnly refresh cookie with reuse detection, session list and revoke.
- **Refresh session handling** — A missing refresh cookie returns HTTP 204 No Content (guest/no session), while invalid, expired, revoked, or reused refresh cookies return HTTP 401 Unauthorized.
- **Role-based access control** — one RBAC module (`backend/rbac.py`): roles `user`/`admin`, permission constants, ownership checks, group permissions, admin safety rules.
- **Groups with fine-grained permissions** — per-member `can_create`, `can_edit`, `can_assign`; owner-only rename, delete and member management.
- **Print workflow and documents** — `Pending → Processing → Ready → Collected` or `Pending → Rejected` (reason required), status history, private document storage with 60-second signed links.
- **Printing cost and payment** — server-calculated cost (B&W Tk 2, Colour Tk 10 per page), staff-only Paid/Unpaid tracking.
- **Admin dashboard** — statistics, user management (ban/unban, bulk, role, sessions), all-groups view, content moderation, activity log, failed-login security view, CSV exports.
- **Audit logging, brute-force protection (lockout + per-IP limit), dark/light theme, Alembic migrations and deployment on Vercel with Supabase.**

### 1.3 Live links

**Table 1. Links**

| What | Link |
|---|---|
| GitHub repository | https://github.com/JannatulFerdous24/2331428_PrintPoint-Campus-Printing-Management-System |
| Vercel frontend | https://2331428.vercel.app |
| API base | https://2331428.vercel.app/api |
| API docs (Swagger) | https://2331428.vercel.app/api/docs |
| Health check | https://2331428.vercel.app/api/health |
| Video demo | Submitted separately |

---

## Part A. Product Requirements (PRD)

### A1. Problem Statement

At a typical campus print shop students bring files on a USB stick or send them by e-mail or messenger, then wait at the counter. Staff calculate prices by hand, there is no record of which jobs were paid, and students cannot tell whether a job is ready without walking to the shop. When a team prints a group assignment, one student usually collects files from everyone informally, with no control over who may change or submit what.

This wastes student time during busy periods (before deadlines and exams), causes pricing disputes and lost jobs, and gives the shop no data about its workload. A shared online system must also be secure: students' documents and history are private, and only staff should be able to change job status, record payment or manage accounts.

**Background.** The mid-semester project (tag `mid-project-final`) proved the core idea with an anonymous CRUD prototype. The final project turns it into a multi-user system with authentication, authorization, groups, an admin dashboard and production hosting.

### A2. Users and Roles

**Table 2. Users and roles**

| Role | Who they are | Main tasks | Must never be able to |
|---|---|---|---|
| Visitor | anyone not logged in | sign up, log in | see any print request, group or user data; call any protected API |
| User (Student) | a registered student (`role = user`) | create, view, edit (while Pending and unpaid) and delete own requests; upload documents; see price and status; manage own profile and sessions | see or change another student's requests; change status or payment; access admin pages or APIs; become admin through signup |
| Group member | a student added to a group | view all group requests; create/edit/assign group requests **only if** the owner granted `can_create` / `can_edit` / `can_assign` | rename or delete the group, manage members, act beyond the granted flags |
| Group owner | the student who created the group | everything a member can, plus rename/delete group, add/remove members, set their flags | give anyone admin rights; see groups they don't belong to |
| Admin (Print-shop staff) | staff created by script or promoted by an admin | process the queue, change status, mark payment, manage users, moderate content, read audit log, export CSV | ban themselves or another admin, change their own role, act inside a group as a member (no implicit group powers) |

### A3. Goals and Success Measures

**Table 3. Goals and measures**

| # | Goal | Measure (testable) | Result |
|---|---|---|---|
| G1 | Students submit and track jobs without visiting the counter | A logged-in student can create a request with a document and see its status and history | ✅ live check |
| G2 | Transparent, tamper-proof pricing | Stored `total_cost` = pages × copies × rate for 100% of requests; a client-sent price is ignored | ✅ `test_cost_payment.py`, live check |
| G3 | Staff process jobs from one queue | Every request is visible to staff, filterable by status, type, payment, file and date | ✅ S23 |
| G4 (security) | No user can read another user's data | Requesting another student's request ID returns 404 for view, edit and document | ✅ `test_rbac.py`, live check |
| G5 (security) | Sessions are short-lived and revocable | Access token lifetime ≤ 15 min; logout and revoke make the refresh token unusable (401) | ✅ `test_auth.py`, live check |
| G6 | Accountability | Every status, payment, ban, role, moderation and login event is written to the audit log | ✅ S15 |

### A4. Scope and Non-Goals

**In scope (implemented):** signup/login/refresh/logout, sessions, profile and password change; RBAC with ownership and group permissions; groups; print requests with PDF/DOCX upload; status workflow with rejection reason and history; printing cost and payment status; admin dashboard (statistics, users, all groups, moderation, audit log, failed-login security view, CSV export); dark/light theme; deployment on Vercel with Supabase PostgreSQL and Storage.

**Out of scope (and why):**
- Online payment gateway — payment is made at the counter; staff record it. A gateway needs merchant accounts outside the course scope.
- E-mail verification, password reset by e-mail and notifications — no e-mail service configured.
- Printer integration and multiple shops — the system models one shop's queue.
- Configurable price table — rates are fixed in `backend/pricing.py`.

**Assumptions and constraints:**
- Modern evergreen browsers (Chrome, Edge, Firefox) with JavaScript enabled.
- Vercel serverless functions: request body ≤ ~4.5 MB, so uploads are limited to 4,000,000 bytes; no local disk persistence, therefore hosted PostgreSQL and object storage are used.
- Supabase free tier (transaction pooler on port 6543 for the app).
- Development time: one semester; single developer.

### A5. User Stories

**Table 4. User stories**

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-01 | visitor | sign up with my e-mail and a strong password | I get my own student account |
| US-02 | student | log in and stay logged in safely, and log out | I don't re-enter my password every 15 minutes, and nobody keeps access after I leave |
| US-03 | student | see and revoke my active sessions | a lost device cannot keep access |
| US-04 | student | upload a PDF/DOCX with pages, copies and print type | the shop prints exactly what I need |
| US-05 | student | see the price before I submit | I know what I will pay |
| US-06 | student | follow my job's status and see a rejection reason | I know when to collect or what to fix |
| US-07 | student | be sure other students cannot see my requests | my documents stay private |
| US-08 | group owner | add members and choose create/edit/assign for each | the team shares jobs with controlled rights |
| US-09 | group member | create or edit team jobs only if I was allowed | the owner's decisions are respected |
| US-10 | group owner | be the only one who can rename, delete or manage members | the group cannot be taken over |
| US-11 | staff | filter the queue and move jobs through the workflow | I process jobs in order |
| US-12 | staff | mark a job Paid and undo a mistake | payment is recorded accurately |
| US-13 | admin | ban/unban users with a reason, change roles, revoke sessions | I can stop abuse immediately |
| US-14 | admin | see every student's groups and delete inappropriate requests or groups | the system stays clean |
| US-15 | admin | read an activity log and failed-login statistics | I can investigate incidents |
| US-16 | admin | export users, requests and activity as CSV | I can report to the department |
| US-17 | any user | switch between dark and light mode | the app is comfortable to use |

**High-level use cases** (detailed in B5): log in and refresh; submit a print job; change a member's permissions; denied action; process and pay a job; ban a user; read the audit log.

---

## Part B. Software Requirements (SRS)

### B1. Introduction

**Purpose.** This part specifies precisely what PrintPoint shall do. Every requirement has an ID that is reused in the tests (B7, C11) and screenshots (Part D).
**Intended readers.** The course instructor, reviewers and future maintainers.
**System overview.** A single-page React application served by Vercel calls a FastAPI REST API under `/api` on the same domain. The API stores data in Supabase PostgreSQL and documents in a private Supabase Storage bucket.

**Table B1. Definitions**

| Term | Meaning |
|---|---|
| JWT | JSON Web Token (RFC 7519): a signed, base64url-encoded set of claims |
| Access token | short-lived JWT (≤ 15 min) sent as `Authorization: Bearer …` on each API call |
| Refresh token | long random secret in an httpOnly cookie, exchanged for a new access token; stored only as a SHA-256 hash |
| Session | one row in `refresh_sessions` (one device/browser login) |
| RBAC | Role-Based Access Control |
| Role | `user` (student) or `admin` (print-shop staff) |
| Permission | a named right (e.g. `request:update_payment`) granted to roles |
| Group flag | per-member right inside a group: `can_create`, `can_edit`, `can_assign` |
| Audit log | append-only table of security-relevant actions (`audit_logs`) |
| Pepper | server-side secret mixed into every password hash, stored outside the database |

**References:** RFC 7519 (JWT), RFC 6749 §10.4 (refresh token rotation), OWASP ASVS 4.0, OWASP Password Storage / Session Management / CSRF cheat sheets, FastAPI, SQLModel, Supabase and Vercel documentation.

### B2. Functional Requirements

**Table 5. Authentication and sessions (FR-AUTH)**

| ID | Requirement |
|---|---|
| FR-AUTH-01 | The system shall let a visitor sign up with a unique e-mail (case-insensitive), full name and password; signup always creates role `user`. |
| FR-AUTH-02 | The system shall reject passwords shorter than 10 characters, longer than 128, without a letter, without a digit, or equal to the e-mail (422). |
| FR-AUTH-03 | The system shall store passwords as Argon2id(HMAC-SHA256(pepper, password)) with a random per-hash salt, and never return or log them. |
| FR-AUTH-04 | The system shall issue on login an HS256 access token with claims `sub`, `role`, `sid`, `type`, `iat`, `exp`, `jti`, lifetime `ACCESS_TOKEN_MINUTES` (1–15, default 15). |
| FR-AUTH-05 | The system shall set an httpOnly, SameSite=Lax, Secure (on HTTPS) refresh cookie `pp_refresh` with path `/api/auth`, valid `REFRESH_TOKEN_DAYS` (default 7). |
| FR-AUTH-06 | The system shall rotate the refresh token on every `/api/auth/refresh`; presenting an already-rotated token after a 30-second grace window shall revoke the session (reuse detection). |
| FR-AUTH-07 | The system shall require the header `X-Requested-With: XMLHttpRequest` on `/refresh` and `/logout` (CSRF protection), otherwise 403. |
| FR-AUTH-08 | The system shall revoke the session on logout so that both the refresh cookie and the access token stop working immediately (401). |
| FR-AUTH-09 | The system shall reject missing, malformed, wrongly signed, expired or revoked-session tokens with 401. |
| FR-AUTH-10 | The system shall lock an account for 15 minutes after 5 consecutive failed logins and return 429 when one IP has 20 failures within 15 minutes; login errors shall be generic ("Invalid email or password"). |
| FR-AUTH-11 | The system shall let a user list their active sessions, revoke one, or revoke all others. |
| FR-AUTH-12 | The system shall let a user update the profile; changing e-mail or password requires the current password, and a password change revokes other sessions. |

**Table 6. Authorization and groups (FR-RBAC)**

| ID | Requirement |
|---|---|
| FR-RBAC-01 | The system shall define permissions once (`Permission` enum) and map them to roles (`ROLE_PERMISSIONS`); admins hold every permission. |
| FR-RBAC-02 | The system shall check permissions on the server for every protected endpoint (`require_permission`), returning 403 to users without the permission. |
| FR-RBAC-03 | The system shall show a student only their own requests and requests of groups they belong to; any other request ID shall return 404 (view, edit, delete, document). |
| FR-RBAC-04 | The system shall let a group member create, edit or assign group requests only with the matching flag (`can_create`, `can_edit`, `can_assign`), otherwise 403. |
| FR-RBAC-05 | The system shall allow only the group owner to rename or delete the group and to add, update or remove members. |
| FR-RBAC-06 | The system shall prevent an admin from banning themselves, banning another admin or changing their own role (403). |
| FR-RBAC-07 | The system shall reload the user from the database on every request so a ban or role change applies on the next request. |
| FR-RBAC-08 | The system shall give admins no implicit powers inside a group; admin access to groups is only through the separate, audited moderation endpoints. |

**Table 7. Admin (FR-ADM)**

| ID | Requirement |
|---|---|
| FR-ADM-01 | The system shall show statistics: total users, banned users, admins, requests by status, groups, new users/requests in 7 days, failed logins in 24 h. |
| FR-ADM-02 | The system shall list users with search (name/e-mail), role and status filters and pagination (`X-Total-Count`). |
| FR-ADM-03 | The system shall show a user's detail: profile, lock state, requests, groups (owned/member with flags), active sessions and recent activity. |
| FR-ADM-04 | The system shall let an admin ban (reason 3–500 characters) and unban users, individually or in bulk, revoking the banned user's sessions. |
| FR-ADM-05 | The system shall let an admin change a user's role and revoke all of a user's sessions. |
| FR-ADM-06 | The system shall list every group of every student with search, owner and has-requests filters, and show a group's members, their flags and its requests. |
| FR-ADM-07 | The system shall let an admin delete any request or group, singly or in bulk (group deletion keeps its requests, detached). |
| FR-ADM-08 | The system shall show the audit log with filters (event, user e-mail, IP, text, date range) and a failed-login view grouped by IP and by account. |
| FR-ADM-09 | The system shall export users, print requests (including cost and payment) and audit log as CSV, respecting the active filters. |
| FR-ADM-10 | The system shall write an audit entry for every admin action (ban, unban, role change, session revoke, moderation delete, export, payment, status change). |

**Table 8. Print requests, documents, workflow and payment (FR-DOM)**

| ID | Requirement |
|---|---|
| FR-DOM-01 | The system shall let a user create, list, view, edit and delete print requests with student name, document name, pages (1–1000), copies (1–999), print type (Black & White / Color), notes and optional group. |
| FR-DOM-02 | The system shall allow editing only while the request is Pending and not Paid. |
| FR-DOM-03 | The system shall calculate `total_cost = pages × copies × rate` (B&W Tk 2, Colour Tk 10) on the server at creation and whenever pages, copies or type change; a client-sent cost or payment status shall be ignored. `GET /api/print-requests/pricing` shall publish the rates. |
| FR-DOM-04 | The system shall allow only staff to change status, following `Pending → Processing → Ready → Collected` or `Pending → Rejected`; rejection requires a 5–500 character reason shown to the student. |
| FR-DOM-05 | The system shall record every status change (from, to, by, note, time) in the status history. |
| FR-DOM-06 | The system shall allow only staff (`request:update_payment`) to set payment Pending/Paid, set or clear `paid_at`, refuse Paid for a Rejected request (409) and write an audit entry with the amount. |
| FR-DOM-07 | The system shall accept one PDF or DOCX per request, up to 4,000,000 bytes, verified by file content (magic bytes), stored in a private bucket under a server-generated key. |
| FR-DOM-08 | The system shall provide document downloads only through a 60-second signed URL issued after the same visibility check as the request. |
| FR-DOM-09 | The system shall support search, filters (status, type, payment, has document, dates), sorting and pagination on request lists. |
| FR-DOM-10 | The system shall let a user switch between dark and light theme and remember the choice across reloads. |

**API requirements.** JSON over HTTPS under `/api`; interactive OpenAPI documentation at `/api/docs`; errors as `{"detail": "…"}` (validation errors as FastAPI's `detail` list); list endpoints paginate with `skip`/`limit` and return `X-Total-Count`.

**Database requirements.** PostgreSQL with schema managed only by Alembic migrations; foreign keys with explicit `ON DELETE` behaviour; indexes on lookup columns (e-mail, owner, status, created_at, token hash); Row Level Security enabled on every table.

### B3. Non-Functional Requirements

**Table 9. Non-functional requirements**

| ID | Category | Requirement | How it is met |
|---|---|---|---|
| NFR-01 | Security | Secrets only in environment variables; the API refuses to start on Vercel if `DATABASE_URL`, `JWT_SECRET` or `PASSWORD_PEPPER` is missing or shorter than 32 characters | `config.py`, `database.py` |
| NFR-02 | Security | Generic login errors; constant-time dummy hash for unknown e-mails | `auth/service.py`, `auth/security.py` |
| NFR-03 | Security | CORS limited to the configured frontend origins | `main.py` |
| NFR-04 | Security | Row Level Security on all tables; Supabase service key only on the server | migrations 0002, `storage.py` |
| NFR-05 | Performance | List endpoints paginated (`limit` ≤ 200, UI pages of 20); indexed filters | routers, models |
| NFR-06 | Usability | Responsive layout, loading and error states, confirmation dialogs for destructive actions, dark/light theme without flash | frontend |
| NFR-07 | Reliability | Data persists across serverless restarts (hosted PostgreSQL, object storage) | Supabase |
| NFR-08 | Maintainability | One RBAC module; UI receives the same permission flags the server enforces; automated tests | `rbac.py`, tests |
| NFR-09 | Deployability | One Vercel project serves UI and API on one domain; deep links reload correctly | `vercel.json` |

### B4. Roles and Permission Matrix

**Table 10. Endpoint groups by role** (own = only own records or records of own groups)

| Endpoint group | Visitor | User | Group member | Group owner | Admin |
|---|---|---|---|---|---|
| `POST /api/auth/signup`, `/login` | yes | yes | yes | yes | yes |
| `/api/auth/refresh`, `/logout`, `/sessions`, `/api/users/me` | no | yes | yes | yes | yes |
| `GET /api/print-requests` (list, view, history, document) | no | own | own + group | own + group | all |
| `POST /api/print-requests` (personal) | no | yes | yes | yes | yes |
| `POST /api/print-requests` with `group_id` | no | no | if `can_create` | yes | only if member with flag |
| `PATCH/PUT /api/print-requests/{id}` (fields, while Pending & unpaid) | no | own | if `can_edit` | own requests / `can_edit` | no (unless owner/member) |
| `PATCH /api/print-requests/{id}` status change | no | no | no | no | yes |
| `PATCH /api/print-requests/{id}/payment` | no | no | no | no | yes |
| `PATCH /api/print-requests/{id}/assignee` | no | no | if `can_assign` | yes | no (unless member) |
| `DELETE /api/print-requests/{id}` | no | own | no | yes (group requests) | via moderation |
| `GET/POST /api/groups`, `GET /api/groups/{id}` | no | own groups | yes | yes | own groups only |
| `PATCH/DELETE /api/groups/{id}`, members endpoints | no | no | no | yes | no (moderation delete only) |
| `/api/admin/*` | no | no (403) | no (403) | no (403) | yes |

**Table 11. Group permissions**

| Flag / role | Allows |
|---|---|
| any member | view the group, its members and all its requests |
| `can_create` | create print requests in the group |
| `can_edit` | edit fields of group requests while Pending and unpaid (never status or payment) |
| `can_assign` | set or clear the assignee of a group request (assignee must be a member) |
| owner only | rename, delete the group; add/remove members; change member flags; delete group requests |

**Table 12. Admin rules**

| Rule | Enforcement |
|---|---|
| Admin cannot ban themselves | `assert_can_ban` → 403 |
| Admin cannot ban another admin | `assert_can_ban` → 403 (UI disables the button, S13) |
| Admin cannot change their own role | `assert_can_change_role` → 403 |
| Admin has no member powers inside a group | group checks use membership only (`group_flags`); admins see groups via `/api/admin/groups` (read-only + audited delete) |
| Banned user is rejected on the next request | `get_current_user` reloads the user and checks `is_banned`; ban also revokes sessions |

### B5. Use Cases

**Figure 1. Use case diagram**

```mermaid
flowchart LR
  V([Visitor]) --- UC1[Sign up / Log in]
  S([Student]) --- UC1
  S --- UC2[Submit print job and see cost]
  S --- UC3[Track status, history, payment]
  O([Group owner]) --- UC4[Manage members and permissions]
  M([Group member]) --- UC5[Create / edit group job within flags]
  S --- UC6[Denied action 403/404]
  A([Admin / Staff]) --- UC7[Process queue and record payment]
  A --- UC8[Ban / unban user]
  A --- UC9[Read audit log and security view]
  A --- UC10[Moderate groups and requests]
```

**Table 13. Use case descriptions**

**UC-01 Log in and refresh a session** — *Actor:* student or admin. *Pre:* account exists, not banned.
1. User submits e-mail and password on `/login`.
2. Server verifies the Argon2 hash, creates a `refresh_sessions` row, returns an access token and sets `pp_refresh`.
3. Frontend keeps the access token in memory and calls the API with `Authorization: Bearer`.
4. When the access token expires the API returns 401; the frontend calls `/api/auth/refresh` once, receives a new token and rotated cookie, and repeats the request.
*Alternatives:* wrong password → 401 generic message; 5 failures → account locked 15 min (429); banned → 403; reused old refresh token → 401 and session revoked. *Post:* active session listed in `/sessions`; `auth.login` audit entry.

**UC-02 Create a print request** — *Actor:* student. *Pre:* logged in.
1. Student opens *New Request*; the form loads `/pricing` and shows a live estimate.
2. Student enters document name, pages, copies, type, optional group and file; submits.
3. Server validates (422 on invalid values), computes `total_cost`, stores the request as Pending/Unpaid, uploads the file to the private bucket, writes `request.create` and history.
*Alternatives:* group without `can_create` → 403; non-PDF/DOCX or > 4 MB → 415/413/400. *Post:* request visible to owner (and group), staff queue.

**UC-03 Change a member's permissions** — *Actor:* group owner.
1. Owner opens the group page, ticks/unticks Create, Edit, Assign for a member.
2. Server checks ownership, updates `group_members`, writes `group.member_update`.
*Alternatives:* non-owner → 403; member not found → 404. *Post:* new flags apply on the member's next request.

**UC-04 Denied action** — *Actor:* student.
1. Student opens `/admin` or calls `GET /api/admin/stats`, or opens another student's request ID.
2. UI shows "Access denied"; the API returns 403 (admin endpoint) or 404 (foreign record).
*Post:* no data disclosed (S6a, S6b).

**UC-05 Process a job and record payment** — *Actor:* staff.
1. Staff filters the queue (S23), opens a Pending job, moves it to Processing → Ready.
2. Student pays at the counter; staff clicks *Mark as paid (Tk X)*; `paid_at` is set and `request.payment` audited.
3. Staff marks Collected.
*Alternatives:* reject without reason → 422; mark a Rejected job Paid → 409; invalid transition → 409/400.

**UC-06 Ban a user** — *Actor:* admin.
1. Admin opens a user, clicks *Ban*, enters a reason (≥ 3 characters).
2. Server checks admin rules, sets `is_banned`, revokes all sessions, writes `user.ban`.
*Alternatives:* target is admin or self → 403. *Post:* the banned user's next request returns 401/403; login refused.

**UC-07 Read the audit log** — *Actor:* admin.
1. Admin opens *Audit Log*, filters by event, e-mail, IP, text or dates; optionally exports CSV.
*Alternative:* student → 403. *Post:* `data.export` audited when exporting.

### B6. Acceptance Criteria

**Table 14. Acceptance criteria**

| # | Requirement | Given | When | Then |
|---|---|---|---|---|
| AC-01 | FR-AUTH-09 | an access token whose `exp` is in the past | it calls `/api/users/me` | 401 "Access token expired" (S7) |
| AC-02 | FR-AUTH-09 | a token signed with a different secret or altered payload | any protected call | 401 |
| AC-03 | FR-AUTH-06/08 | a refresh token that was rotated or a logged-out session | `/api/auth/refresh` | 401 |
| AC-04 | FR-RBAC-03 | student B and student A's request ID | B requests it | 404 |
| AC-05 | FR-RBAC-02 | a student token | `GET /api/admin/stats` | 403 (S6b) |
| AC-06 | FR-RBAC-04 | a view-only member | creates or edits a group request | 403; viewing is 200 |
| AC-07 | FR-RBAC-04 | a member without `can_assign` | sets an assignee | 403; owner succeeds |
| AC-08 | FR-RBAC-07 | a user who is banned | makes the next request / logs in | rejected |
| AC-09 | FR-RBAC-06 | admin A and admin B | A bans B | 403 |
| AC-10 | FR-DOM-03 | B&W, 5 pages × 2 copies, client sends `total_cost: 1` | request is created | `total_cost = 20`; changed to Colour → 100 |
| AC-11 | FR-DOM-06 | a student | marks a request Paid | 403; staff → 200, `paid_at` set, audit entry |
| AC-12 | FR-DOM-02 | a Paid request | the owner edits it | 403 |
| AC-13 | FR-DOM-04 | staff rejects without a reason | — | 422 |
| AC-14 | FR-AUTH-10 | 5 wrong passwords | 6th login | account locked (429) |
| AC-15 | FR-DOM-10 | dark theme chosen | page reloads | still dark |

### B7. Traceability Matrix

**Table 15. Requirement → implementation → test → evidence**

| Requirement | Endpoint / screen | Automated test | Evidence |
|---|---|---|---|
| FR-AUTH-01/02 | `POST /api/auth/signup`, Signup page | `test_auth.py` | S1 |
| FR-AUTH-03 | `auth/security.py` | `test_auth.py` | — |
| FR-AUTH-04/09 | `auth/tokens.py`, `auth/dependencies.py` | `test_auth.py` (expired, tampered, wrong type) | S7, live check |
| FR-AUTH-05/06/07/08 | `/api/auth/refresh`, `/logout` | `test_auth.py`, `test_auth_postgres_integration.py` | live check |
| FR-AUTH-10 | `/api/auth/login` | `test_auth.py` (lockout, IP limit) | S1b, S10 security view |
| FR-AUTH-11/12 | `/api/auth/sessions*`, Profile, Sessions pages | `test_auth.py` | S3, S4 |
| FR-RBAC-01/02 | `rbac.py`, `/api/admin/*` | `test_rbac.py`, `test_admin_dashboard.py` (every admin endpoint vs student/anon) | S6a, S6b |
| FR-RBAC-03 | `get_visible_request` | `test_rbac.py`, `test_rbac_postgres_integration.py` | live check |
| FR-RBAC-04/05 | groups router, Group page | `test_rbac.py` | S5 |
| FR-RBAC-06 | `assert_can_ban`, `assert_can_change_role` | `test_admin_dashboard.py` | S11, S13 |
| FR-RBAC-07 | `get_current_user` | `test_auth.py`, `test_admin_dashboard.py` | S11 (banned account) |
| FR-RBAC-08 | `group_flags`, `/api/admin/groups/{id}` | `test_admin_dashboard.py` | S14b |
| FR-ADM-01 | `/api/admin/stats`, Dashboard | `test_admin_dashboard.py` | S10 |
| FR-ADM-02/03/05 | `/api/admin/users*`, Users pages | `test_admin_dashboard.py` | S11, S12 |
| FR-ADM-04 | ban/unban/bulk | `test_admin_dashboard.py` | S11 |
| FR-ADM-06/07 | `/api/admin/groups*`, moderation | `test_admin_dashboard.py` | S14a, S14b, S14c |
| FR-ADM-08/10 | `/api/admin/audit-logs`, `/security/failed-logins` | `test_admin_dashboard.py` | S10, S15 |
| FR-ADM-09 | `/api/admin/export/*.csv` | `test_admin_dashboard.py` | live check |
| FR-DOM-01/02/09 | `/api/print-requests*`, Requests page | `test_print_requests.py`, `test_cost_payment.py` | S2 |
| FR-DOM-03/06 | `pricing.py`, `/payment` | `test_cost_payment.py`, `test_migrations.py` | S2, S23 |
| FR-DOM-04/05 | status PATCH, history | `test_workflow.py` | S23 |
| FR-DOM-07/08 | `/document` PUT/GET | `test_documents.py` | live check |
| FR-DOM-10 | `theme.ts`, ThemeToggle | `frontend/tests/theme.test.ts` | S22 |
| NFR-01 | `config.py`, `database.py` | `test_database_config.py` | — |

---

## Part C. Technical Design (TDD)

### C1. Technology Stack

**Table 16. Technology stack**

| Component | Technology | Version | Reason |
|---|---|---|---|
| Frontend | React + TypeScript | React 19.3, TypeScript 7.0 | component model, static typing of API data |
| Build tool | Vite | 8.3 | fast dev server with `/api` proxy, static build for Vercel |
| Routing | React Router | 7.18 | client-side routes and guards |
| UI | plain CSS with custom properties | — | no UI library needed; tokens make dark mode a variable swap |
| Backend | FastAPI | ≥ 0.115 | validation, dependency injection for auth/RBAC, automatic OpenAPI |
| ORM | SQLModel / SQLAlchemy | ≥ 0.0.21 | typed models shared by DB and API |
| Database | Supabase PostgreSQL (psycopg 3) | PostgreSQL 17 | managed, persistent, pooled connections for serverless |
| Migrations | Alembic | ≥ 1.13 | versioned schema changes 0001–0004 |
| Password hashing | argon2-cffi (Argon2id) + HMAC pepper | ≥ 25.1 | OWASP-recommended memory-hard hash |
| JWT | PyJWT (HS256) | ≥ 2.15 | standard, small |
| File storage | Supabase Storage (private bucket) | — | private objects + signed URLs |
| Testing | pytest, httpx TestClient; Node `node:test` | pytest ≥ 8 | API tests with in-memory SQLite; frontend logic tests without extra packages |
| Hosting | Vercel (services) | — | one domain for UI and API → no cross-site cookies |

### C2. System Architecture

**Figure 2. System architecture**

```mermaid
flowchart LR
  B[Browser<br/>React SPA] -- "HTTPS GET /, /admin …" --> VF[Vercel: frontend service<br/>Vite static build]
  B -- "HTTPS /api/* + Authorization: Bearer access token" --> VA[Vercel: backend service<br/>FastAPI Python 3.12]
  B -- "httpOnly cookie pp_refresh (path /api/auth)" --> VA
  VA -- "SQL via psycopg (pooler :6543)" --> DB[(Supabase PostgreSQL<br/>9 tables, RLS)]
  VA -- "insert audit_logs" --> DB
  VA -- "service key, upload / signed URL" --> ST[(Supabase Storage<br/>private bucket print-documents)]
  B -- "GET signed URL (60 s)" --> ST
```

- **Browser → frontend service:** Vercel serves the built `index.html` and assets; unknown paths fall back to `index.html` so React Router can render deep links.
- **Browser → API with Bearer token:** every protected call carries the in-memory access token; FastAPI verifies it and reloads the user.
- **Refresh cookie:** the browser sends `pp_refresh` only to `/api/auth/*`; JavaScript cannot read it.
- **API → PostgreSQL:** SQLModel sessions through the transaction pooler; every security-relevant action also inserts an `audit_logs` row.
- **API → Storage:** uploads use the service key on the server only; downloads are 60-second signed URLs issued after a permission check, fetched directly by the browser.

### C3. Backend and Frontend Structure

**Backend (two levels)**

```
backend/
├── main.py              FastAPI app, CORS, error handlers, routers, /api/health, /api/docs
├── config.py            settings from env; refuses missing/weak secrets on Vercel
├── database.py          engine (Supabase pooler or local SQLite), get_session
├── models.py            SQLModel tables and enums
├── schemas.py           request/response models
├── rbac.py              RBAC module: permissions, require_permission, ownership, groups, admin rules
├── crud.py              print-request queries, status workflow, payment, history, audit
├── pricing.py           rates and calculate_cost
├── documents.py         upload validation (size, extension, magic bytes)
├── storage.py           Supabase Storage client, signed URLs
├── audit.py             log_event helper
├── errors.py            consistent JSON error responses
├── auth/                router.py, service.py, security.py, tokens.py, dependencies.py, schemas.py
├── routers/             print_requests.py, groups.py, admin.py
├── migrations/versions/ 0001 … 0004
├── scripts/             create_admin.py, seed_demo.py, setup_storage_bucket.py, run_with_env.py
└── tests/               11 pytest modules
```

**Frontend (two levels)**

```
frontend/
├── index.html           theme bootstrap script (no white flash)
├── src/
│   ├── App.tsx          routes; RequireAuth / GuestOnly / RequireAdmin guards
│   ├── auth/            AuthContext (token in memory, silent refresh), guards, password rules
│   ├── api/             client.ts (fetch + retry-on-401), auth, printRequests, groups, admin
│   ├── components/      Layout, PrintRequestForm/Table, RequestDetails, StaffActions, badges, dialogs, ThemeToggle
│   ├── pages/           Login, Signup, PrintRequests, Groups, GroupDetail, Profile, Sessions,
│   │                    StaffQueue, AdminDashboard, AdminUsers, AdminUserDetail, AdminModeration,
│   │                    AdminGroupDetail, AdminAudit, NotFound
│   ├── types/           shared TypeScript types
│   └── theme.ts         dark/light logic
└── tests/theme.test.ts
```

Routes live in `routers/` and `auth/router.py`; business logic in `crud.py` and `auth/service.py`; authorization only in `rbac.py`; admin code in `routers/admin.py`. On the frontend, pages call typed clients in `api/`, the auth context owns the token, and guards only control what is shown — the server enforces everything.

### C4. Data Model

**Figure 3. Entity relationship diagram**

```mermaid
erDiagram
  USERS ||--o{ REFRESH_SESSIONS : has
  USERS ||--o{ LOGIN_ATTEMPTS : "attempted by"
  USERS ||--o{ AUDIT_LOGS : "actor of"
  USERS ||--o{ GROUPS : owns
  GROUPS ||--o{ GROUP_MEMBERS : has
  USERS ||--o{ GROUP_MEMBERS : "is member"
  USERS ||--o{ PRINT_REQUESTS : owns
  GROUPS |o--o{ PRINT_REQUESTS : contains
  USERS |o--o{ PRINT_REQUESTS : "assigned to"
  PRINT_REQUESTS ||--o{ PRINT_REQUEST_STATUS_HISTORY : records
  USERS {
    int id PK
    string email UK
    string full_name
    string password_hash
    enum role
    bool is_banned
    string ban_reason
    int failed_login_count
    datetime locked_until
  }
  REFRESH_SESSIONS {
    int id PK
    int user_id FK
    string token_hash UK
    string previous_token_hash
    datetime expires_at
    datetime revoked_at
  }
  GROUPS {
    int id PK
    string name
    int owner_id FK
  }
  GROUP_MEMBERS {
    int id PK
    int group_id FK
    int user_id FK
    bool can_create
    bool can_edit
    bool can_assign
  }
  PRINT_REQUESTS {
    int id PK
    int owner_id FK
    int group_id FK
    int assignee_id FK
    int pages
    int copies
    enum print_type
    enum status
    int total_cost
    enum payment_status
    string storage_path
  }
  PRINT_REQUEST_STATUS_HISTORY {
    int id PK
    int print_request_id FK
    enum from_status
    enum to_status
    int changed_by_id FK
    string note
  }
  AUDIT_LOGS {
    int id PK
    int actor_id FK
    string action
    string target_type
    string target_id
    json details
    string ip_address
  }
  LOGIN_ATTEMPTS {
    int id PK
    string email_attempted
    int user_id FK
    string ip_address
    bool success
  }
```

**Table 17. `users`**

| Column | Type | Constraints / index | Purpose |
|---|---|---|---|
| id | integer | PK | |
| email | varchar(255) | unique, index, stored lower-case | login ID |
| full_name | varchar(200) | not null | |
| password_hash | varchar(255) | not null | Argon2id hash (never the password) |
| role | enum `user`/`admin` | index, default `user` | RBAC role |
| is_banned, ban_reason, banned_at, banned_by_id | bool, text, timestamptz, FK users | index on is_banned | ban state and who banned |
| failed_login_count, locked_until | int, timestamptz | | lockout |
| password_changed_at, created_at, updated_at | timestamptz | index on created_at | |

**Table 18. `refresh_sessions`** — `user_id` FK (CASCADE), `token_hash` varchar(64) unique (SHA-256 of the cookie value), `previous_token_hash` (reuse detection), `ip_address`, `user_agent`, `created_at`, `last_used_at`, `expires_at`, `revoked_at`, `revoked_reason`.

**Table 19. `groups` and `group_members`** — `groups(id, name 1–100, description ≤ 500, owner_id FK RESTRICT, created_at, updated_at)`; `group_members(group_id FK CASCADE, user_id FK CASCADE, can_create, can_edit, can_assign, added_by_id, joined_at)`, unique (group_id, user_id). Membership with flags is stored per row; ownership is `groups.owner_id`.

**Table 20. `print_requests`** — `owner_id` FK RESTRICT (required since 0003), `group_id` FK SET NULL, `assignee_id` FK SET NULL, `student_name`, `document_name`, `pages` 1–1000, `copies` 1–999, `print_type` enum, `status` enum (index), `notes`, `total_cost` integer ≥ 0 (Taka), `payment_status` enum `pending`/`paid`, `paid_at`, document metadata (`storage_path`, `original_filename`, `content_type`, `file_size_bytes`, `uploaded_at`), timestamps.

**Table 21. `print_request_status_history`, `audit_logs`, `login_attempts`** — history stores each transition and the rejection reason (`note`); `audit_logs` stores `actor_id`, `action` (e.g. `request.payment`, `user.ban`, `moderation.group_delete`), target, JSON `details`, IP and user agent; `login_attempts` stores every login try for lockout, IP rate limiting and the security view.

**Migrations:** `0001_create_print_requests` (mid project) → `0002_core_security_schema` (users, sessions, attempts, audit, groups, members, history, owner/group/assignee columns, RLS on all tables) → `0003_owner_required` → `0004_cost_and_payment` (pages, total_cost, `paymentstatus` enum, paid_at; back-fills cost for existing rows).

### C5. API Design

All endpoints are under `/api` (no version prefix; the API is consumed only by this frontend). Errors: `{"detail": "message"}`; validation errors: `{"detail": [ … ]}` with 422.

**Table 22. Endpoint list**

| Method and path | Auth | Role / permission | Body | Success | Errors |
|---|---|---|---|---|---|
| GET /api/health | no | — | — | 200 | — |
| POST /api/auth/signup | no | — | email, full_name, password | 201 token + cookie | 409, 422 |
| POST /api/auth/login | no | — | email, password | 200 token + cookie | 401, 403 banned, 429 |
| POST /api/auth/refresh | cookie + X-Requested-With | — | — | 200 new token | 401, 403 |
| POST /api/auth/logout | token + cookie + X-Requested-With | — | — | 204 | 401, 403 |
| GET /api/auth/me, GET/PATCH /api/users/me | yes | any | profile fields (+ current_password for e-mail) | 200 | 400, 401, 409, 422 |
| POST /api/users/me/password | yes | any | current_password, new_password | 200 | 400, 422 |
| GET /api/auth/sessions; DELETE /sessions/{id}; POST /sessions/revoke-others | yes | own sessions | — | 200/204 | 401, 404 |
| GET /api/print-requests | yes | own/group; all for staff | query: q, status, print_type, payment_status, has_document, dates, sort, skip, limit | 200 + X-Total-Count | 401, 422 |
| POST /api/print-requests | yes | `request:create`; group needs `can_create` | request fields | 201 | 403, 404, 422 |
| GET /api/print-requests/pricing | yes | any | — | 200 | 401 |
| GET /api/print-requests/{id}, /{id}/history | yes | visible | — | 200 | 404 |
| PUT/PATCH /api/print-requests/{id} | yes | owner / `can_edit`; status needs `request:update_status` | fields or status (+reason) | 200 | 403, 404, 409, 422 |
| PATCH /api/print-requests/{id}/payment | yes | `request:update_payment` | payment_status | 200 | 403, 404, 409, 422 |
| PATCH /api/print-requests/{id}/assignee | yes | `can_assign` | assignee_id | 200 | 403, 404, 422 |
| PUT /api/print-requests/{id}/document | yes | owner / `can_edit` | multipart file | 200 | 400, 403, 404, 413, 415 |
| GET /api/print-requests/{id}/document | yes | visible | — | 200 signed URL | 404 |
| DELETE /api/print-requests/{id} | yes | owner / group owner | — | 204 | 403, 404 |
| GET/POST /api/groups; GET /api/groups/{id} | yes | member (GET), any (POST) | name, description | 200/201 | 403, 404, 422 |
| PATCH/DELETE /api/groups/{id} | yes | owner | name, description | 200/204 | 403, 404 |
| POST/PATCH/DELETE /api/groups/{id}/members[/{user_id}] | yes | owner | email + flags / flags | 201/200 | 403, 404, 409 |
| GET /api/admin/stats | yes | admin (`user:read`) | — | 200 | 401, 403 |
| GET /api/admin/users, /users/{id} | yes | `user:read` | q, role, status, skip, limit | 200 | 403, 404 |
| POST /api/admin/users/{id}/ban, /unban, /bulk-ban, /bulk-unban | yes | `user:ban` | reason / user_ids | 200 | 403, 404, 422 |
| PATCH /api/admin/users/{id}/role | yes | `user:change_role` | role | 200 | 403 |
| POST /api/admin/users/{id}/revoke-sessions | yes | `user:revoke_sessions` | — | 200 | 403, 404 |
| GET /api/admin/groups, /groups/{id} | yes | `content:moderate` | q, owner_id, has_requests | 200 | 403, 404 |
| DELETE /api/admin/print-requests/{id}, /groups/{id}; POST …/bulk-delete | yes | `content:moderate` | ids | 204/200 | 403, 404 |
| GET /api/admin/audit-logs, /security/failed-logins | yes | `audit:read` | filters | 200 | 403 |
| GET /api/admin/export/users.csv, print-requests.csv, audit-logs.csv | yes | `data:export` | same filters as lists | 200 text/csv | 403 |

Every print-request response contains a `permissions` object (`view, edit, delete, change_status, assign, update_payment`) computed by the same function used for enforcement, so the UI only shows buttons the server will accept.

### C6. JWT Authentication Design

**Figure 4. Login, protected request, expiry, refresh, reuse and logout**

```mermaid
sequenceDiagram
  participant B as Browser (React)
  participant A as FastAPI
  participant D as PostgreSQL
  B->>A: POST /api/auth/login {email, password}
  A->>D: load user, verify Argon2id(HMAC(pepper, pw))
  A->>D: insert refresh_sessions(token_hash)
  A-->>B: 200 {access_token} + Set-Cookie pp_refresh (httpOnly, /api/auth)
  B->>A: GET /api/print-requests (Authorization: Bearer access)
  A->>A: verify signature, exp, type
  A->>D: session sid active? user exists, not banned
  A-->>B: 200 data
  Note over B,A: 15 minutes later the access token expires
  B->>A: GET /api/print-requests (expired token)
  A-->>B: 401 Access token expired
  B->>A: POST /api/auth/refresh (cookie + X-Requested-With)
  A->>D: find session by hash, rotate token_hash, keep previous_token_hash
  A-->>B: 200 new access token + new cookie
  B->>A: retry original request → 200
  Note over B,A: an attacker replays the OLD refresh cookie
  B->>A: POST /api/auth/refresh (old cookie, > 30 s later)
  A->>D: matches previous_token_hash → revoke session
  A-->>B: 401
  B->>A: POST /api/auth/logout
  A->>D: revoked_at = now
  A-->>B: 204 + cookie cleared
```

**Table 23. Access token claims**

| Claim | Value | Purpose |
|---|---|---|
| `sub` | user id (string) | who the token belongs to |
| `role` | `user` / `admin` | informational; the server re-reads the role from the database |
| `sid` | refresh-session id | lets logout/revoke invalidate the access token immediately |
| `type` | `access` | prevents using another token type as an access token |
| `iat`, `exp` | issued / expiry (≤ 15 min) | lifetime |
| `jti` | random hex | unique token id |

- **Algorithm and secret:** HS256 with `JWT_SECRET` (≥ 32 characters, environment only).
- **Lifetimes:** access 15 min (course limit, small damage window); refresh 7 days (students should not log in every visit), revocable at any time.
- **Storage:** the access token lives only in React memory (not localStorage) → not readable after an XSS-free reload and not persisted; the refresh token is in an httpOnly cookie → JavaScript cannot read it. CSRF on the cookie endpoints is blocked by the `X-Requested-With` header requirement plus strict CORS and SameSite=Lax.
- **Server checks on every request:** signature, expiry, `type`, session `sid` not revoked/expired, user exists, user not banned (`auth/dependencies.py`).
- **Frontend on 401:** `api/client.ts` calls `/api/auth/refresh` once and retries; if refresh fails the user is logged out and sent to `/login`.

### C7. RBAC Design

**Figure 5. Authorization flow for one request**

```mermaid
flowchart TD
  R[HTTP request] --> T{Bearer token valid?<br/>signature, exp, type}
  T -- no --> E401[401]
  T -- yes --> U{session active,<br/>user exists, not banned?}
  U -- no --> E401
  U -- yes --> P{route needs a role permission?<br/>require_permission}
  P -- missing --> E403[403]
  P -- ok / none --> O{object visible?<br/>owner, group member or read_all}
  O -- no --> E404[404 - hides existence]
  O -- yes --> G{action allowed?<br/>owner / group flag / staff permission,<br/>Pending & unpaid for edits}
  G -- no --> E403
  G -- yes --> H[handler runs, audit log written]
```

**Roles and permission constants** (`backend/rbac.py`): students hold `request:create`, `request:read_own`, `request:update_own`, `request:delete_own`, `group:create`; admins hold all of these plus `request:read_all`, `request:update_status`, `request:update_payment`, `content:moderate`, `user:read`, `user:ban`, `user:change_role`, `user:revoke_sessions`, `audit:read`, `data:export`.

**Code excerpt — the reusable permission check**

```python
ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.user: frozenset(_STUDENT),
    UserRole.admin: frozenset(Permission),  # every permission
}

def has_permission(user: User, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.role, frozenset())

def require_permission(*permissions: Permission):
    """FastAPI dependency factory: `user = Depends(require_permission(Permission.USER_BAN))`."""
    def dependency(user: User = Depends(get_current_user)) -> User:
        missing = [p for p in permissions if not has_permission(user, p)]
        if missing:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail="You do not have permission to perform this action")
        return user
    return dependency
```

- **Ownership in queries:** list queries are filtered in SQL — a student's list is `owner_id = me OR group_id IN (my groups)` (`visible_group_ids`), so foreign rows are never loaded; single-object routes use `get_visible_request`, which returns 404 for invisible objects.
- **Adding a role or permission:** add a value to `Permission`, add it to the role's set in `ROLE_PERMISSIONS`, and protect the route with `Depends(require_permission(Permission.X))`; tests in `test_rbac.py` pin the matrix.
- **Admin and banned users:** admin safety rules in `assert_can_ban` / `assert_can_change_role`; banned users fail in `get_current_user`; a ban also revokes all sessions.

**Figure 6. Group permission enforcement**

```mermaid
flowchart LR
  Q[Group action] --> M{caller is owner?}
  M -- yes --> OK[allowed]
  M -- no --> N{caller is member?}
  N -- no --> X404[404 group / request not visible]
  N -- yes --> F{action}
  F -- view --> OK
  F -- create --> C{can_create?}
  F -- edit --> D{can_edit and Pending and unpaid?}
  F -- assign --> S{can_assign?}
  F -- rename / delete / members --> X403[403 owner only]
  C -- yes --> OK
  D -- yes --> OK
  S -- yes --> OK
  C -- no --> X403
  D -- no --> X403
  S -- no --> X403
```

**Figure 7. Print request workflow**

```mermaid
stateDiagram-v2
  [*] --> Pending: student creates (cost calculated, Unpaid)
  Pending --> Processing: staff
  Pending --> Rejected: staff + reason (5-500 chars)
  Processing --> Ready: staff
  Ready --> Collected: staff
  Collected --> [*]
  Rejected --> [*]
  note right of Pending: owner / can_edit may edit only here and only while Unpaid
  note right of Ready: staff marks Paid (paid_at, audit request.payment)
```

**Payment calculation design.** `backend/pricing.py` holds `RATES_PER_PAGE = {Black & White: 2, Color: 10}` and `calculate_cost(pages, copies, print_type) = pages × copies × rate`. `crud.create_print_request` and `crud.update_print_request` call it; the client's `total_cost`/`payment_status` fields are not part of the input schemas, so over-posting is impossible. `crud.update_payment_status` returns 409 for Rejected → Paid, sets/clears `paid_at` and logs `request.payment` with `{from, to, amount}`. A paid request's `permissions.edit` becomes false.

**File storage architecture.** Upload: `PUT /{id}/document` → permission check → `documents.validate_document` (size ≤ 4,000,000 bytes, extension `.pdf`/`.docx`, magic bytes `%PDF-` or a ZIP containing `word/document.xml`) → stored at a server-generated key in the private bucket `print-documents` → metadata saved. Download: `GET /{id}/document` → same visibility check → 60-second signed URL. The service-role key exists only in the backend environment.

### C8. Admin Dashboard Design

**Figure 8. Admin pages and the endpoints they call**

```mermaid
flowchart LR
  D[Dashboard /admin] --> s1[GET /api/admin/stats]
  D --> s2[GET /api/admin/security/failed-logins]
  Q[Staff Queue /staff/queue] --> q1[GET /api/print-requests?filters]
  Q --> q2[PATCH /api/print-requests/id status]
  Q --> q3[PATCH /api/print-requests/id/payment]
  U[Users /admin/users] --> u1[GET /api/admin/users]
  U --> u2[POST bulk-ban / bulk-unban, ban, unban]
  UD[User detail /admin/users/id] --> u3[GET /api/admin/users/id]
  UD --> u4[PATCH role, POST revoke-sessions]
  G[All Groups /admin/groups] --> g1[GET /api/admin/groups]
  GD[Group detail /admin/groups/id] --> g2[GET /api/admin/groups/id]
  M[Moderation /admin/moderation] --> m1[DELETE + bulk-delete requests / groups]
  L[Audit Log /admin/audit] --> l1[GET /api/admin/audit-logs]
  U & L & M --> x1[GET /api/admin/export/*.csv]
```

**Table 24. Admin pages, filters, actions and audit events**

| Page | Filters / pagination | Actions | Audit events |
|---|---|---|---|
| Dashboard | failed-login window (hours) | — | — |
| Staff Queue | status tabs, search, type, payment, file, date range, sort; paginated | change status, reject with reason, mark paid / undo | `request.status_change`, `request.payment` |
| Users | search, role, status; checkbox selection; paginated | ban (reason), unban, bulk ban/unban, change role, CSV | `user.ban`, `user.unban`, `user.role_change`, `data.export` |
| User detail | — | ban/unban, change role, revoke sessions | `user.sessions_revoke` |
| All Groups / Group detail | search, has-requests, owner; paginated | view, delete, bulk delete | `moderation.group_delete` |
| Moderation | requests: search, status; groups: search | delete one / many requests or groups | `moderation.request_delete`, `moderation.group_delete` |
| Audit Log | event, user e-mail, IP, text, date range; paginated | CSV export | `data.export` |

Bulk actions return `{done: [...], skipped: [{id, reason}]}` and the UI reports how many succeeded and why others were skipped (e.g. "admins cannot ban other admins"). CSV exports call the same query builder as the on-screen list, so they respect the active filters.

### C9. Security Design and Threats

**Table 25. Threats, defences and location**

| Threat | Defence | Where |
|---|---|---|
| Password database leak | Argon2id with per-hash salt + HMAC pepper stored outside the DB | `auth/security.py`, env `PASSWORD_PEPPER` |
| Stolen access token | 15-min lifetime, in-memory only, bound to a revocable session (`sid`) | `auth/tokens.py`, `auth/dependencies.py` |
| Stolen refresh token | httpOnly cookie scoped to `/api/auth`, hashed at rest, rotation + reuse detection, logout/revoke | `auth/service.py`, `auth/router.py` |
| Brute-force login | account lockout (5 → 15 min), per-IP limit (20 / 15 min → 429), generic errors, dummy hash timing | `auth/service.py` |
| Privilege escalation | role never accepted from clients; signup always `user`; admin rules; role reloaded each request | `rbac.py`, `auth/service.py` |
| Access to another user's record (IDOR) | SQL-level owner/group filtering; 404 for invisible objects | `rbac.py`, `crud.py` |
| Cross-site scripting | React escapes output; no `dangerouslySetInnerHTML`; tokens not in localStorage | frontend |
| Cross-site request forgery | Bearer header for data APIs; `X-Requested-With` on cookie endpoints; SameSite=Lax | `auth/router.py` |
| CORS misuse | explicit origin list, credentials only for those origins | `main.py` |
| Secrets in the repository | `.env*` git-ignored; only `.env.example` with names; startup check for weak secrets | `.gitignore`, `config.py` |
| SQL injection | SQLAlchemy parameterised queries only | `crud.py`, routers |
| Over-posting of fields | separate Pydantic input schemas without `owner_id`, `role`, `total_cost`, `payment_status` | `schemas.py`, `auth/schemas.py` |
| Malicious uploads | size limit, magic-byte check, private bucket, short signed URLs | `documents.py`, `storage.py` |
| Direct database API access | Row Level Security enabled on every table | migration 0002 |

### C10. Deployment on Vercel

**Figure 9. Deployment layout**

```mermaid
flowchart TB
  GH[GitHub main branch] -- push triggers build --> V[Vercel project 2331428]
  V --> FE["frontend service<br/>root frontend, Vite build<br/>SPA fallback to index.html"]
  V --> BE["backend service<br/>root backend, FastAPI main:app<br/>Python 3.12"]
  U["https://2331428.vercel.app"] --> R{vercel.json rewrites}
  R -- /api/* --> BE
  R -- everything else --> FE
  BE --> PG[(Supabase printpoint-prod<br/>PostgreSQL, us-east-1)]
  BE --> SB[(Supabase Storage<br/>print-documents)]
```

One Vercel project (Git-integrated) hosts two services defined in `vercel.json`. Because the UI and API share the domain, the frontend calls relative `/api/...` URLs and the refresh cookie is first-party. A push to `main` builds and deploys Production; a redeploy can also be triggered from the Vercel dashboard or `vercel redeploy`. Database migrations are applied with Alembic (session pooler, port 5432) before deploying code that needs them. Development uses a separate Supabase project.

**Table 26. Environment variable names** (values are set in Vercel → Settings → Environment Variables, Production)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Supabase transaction-pooler connection string (port 6543) |
| `JWT_SECRET` | HS256 signing key (≥ 32 chars) |
| `PASSWORD_PEPPER` | server-side pepper for password hashing (≥ 32 chars) |
| `ACCESS_TOKEN_MINUTES` | access token lifetime (1–15) |
| `REFRESH_TOKEN_DAYS` | refresh session lifetime |
| `COOKIE_SECURE` | secure cookie flag (forced on Vercel) |
| `CORS_ORIGINS` | allowed frontend origin(s) |
| `SUPABASE_URL` | Supabase project URL for Storage |
| `SUPABASE_SERVICE_ROLE_KEY` | server-only Storage key |
| `SUPABASE_STORAGE_BUCKET` | bucket name (`print-documents`) |
| `MIGRATION_DATABASE_URL` | local only: session pooler for Alembic |

### C11. Testing

**Strategy.** (1) Automated API tests with pytest and FastAPI's TestClient on in-memory SQLite, one fixture per test; (2) opt-in PostgreSQL integration tests (`RUN_PG_INTEGRATION=1`) against the development Supabase database; (3) frontend logic tests with Node's built-in runner; (4) scripted end-to-end checks against the live Production deployment.

**How to run:** `cd backend && python -m pytest -q` · `cd frontend && npm test`.

**Table 27. Automated test results (run on 27 Nov 2026)**

| Test module | What it checks (requirements) | Result |
|---|---|---|
| `test_auth.py` | signup rules, hashing, login, lockout, IP limit, missing/invalid/tampered/expired/wrong-type tokens (401), refresh rotation and reuse, CSRF header, logout, sessions, profile and password change (FR-AUTH-01…12) | 35 passed |
| `test_rbac.py` | own vs other records (404), group permission matrix (create/edit/assign, owner-only), admin rules, banned users, permissions object (FR-RBAC-01…08) | 22 passed |
| `test_admin_dashboard.py` | every admin endpoint rejects students (403) and anonymous (401), stats, users, ban/bulk, role, revoke, all-groups list/detail/filters, moderation, audit, CSV (FR-ADM-01…10) | 13 passed |
| `test_cost_payment.py` | rates, cost on create/edit, client price ignored, staff-only payment, paid lock, 409 for rejected, filters (FR-DOM-03, 06) | 15 passed |
| `test_workflow.py` | allowed/forbidden transitions, rejection reason, history (FR-DOM-04, 05) | 17 passed |
| `test_documents.py` | PDF/DOCX validation, size limit, signed links, visibility (FR-DOM-07, 08) | 13 passed |
| `test_print_requests.py` | CRUD, validation, pagination (FR-DOM-01, 09) | 12 passed |
| `test_migrations.py` | 0001→0004 upgrade/downgrade, cost back-fill (database requirements) | 10 passed |
| `test_database_config.py` | missing/weak secrets refused on Vercel (NFR-01) | 11 passed |
| `test_auth_postgres_integration.py`, `test_rbac_postgres_integration.py` | same flows on real PostgreSQL | 20 skipped by default (passed when run on the dev database during development) |
| `frontend/tests/theme.test.ts` | saved choice, system preference, blocked storage, toggle (FR-DOM-10) | 7 passed |
| **Total** | | **148 passed, 20 skipped (backend); 7 passed (frontend)** |

**Live Production verification (27 Nov 2026).** A script exercised https://2331428.vercel.app with the demo accounts and temporary accounts that were removed afterwards: **71/71 checks passed** (health and docs, signup/login, refresh rotation and replay rejection, logout, expired and forged tokens, CORS, RBAC 403/404, cost and payment, upload and signed download, workflow, group permissions, admin ban/unban, moderation, audit log, CSV exports, deep-link reload). After the admin group-management change a second script passed **18/18 checks** (multiple student groups visible to admins, filters, detail with member flags, students refused, group rules unchanged, audited delete and bulk delete).

---

## Part D. Evidence: Screenshots of the Running Application

All screenshots were taken on the deployed site **https://2331428.vercel.app** on 27 November 2026 with a headless Chrome browser (Playwright) using the existing demo accounts. Headless capture has no address bar, so each caption states the URL. IP addresses and non-demo e-mail addresses were masked (•••) in the page before capture; tokens are never shown (Swagger masks the Bearer value and the curl box was hidden).

### D1. User Side

**S1 — Signup validation (FR-AUTH-02).** `/signup`: a 5-character password is rejected with the password rules.
<!-- screenshot: S01_signup_validation -->
*Screenshot S1 — included in the PDF report submitted through the course Google Form.*

**S1b — Login error (FR-AUTH-10).** `/login`: a wrong password gives the generic message, without revealing whether the account exists.
<!-- screenshot: S01b_login_error -->
*Screenshot S1b — included in the PDF report submitted through the course Google Form.*

**S2 — A student's own requests with cost and payment (FR-RBAC-03, FR-DOM-01/03).** `/requests` as Demo Student One: only own and group requests are listed, with the server-calculated cost (e.g. 2 × 30 × Tk 2 = Tk 120) and Paid/Unpaid badge; Edit appears only for the Pending, unpaid request.
<!-- screenshot: S02_student_requests -->
*Screenshot S2 — included in the PDF report submitted through the course Google Form.*

**S3 — Wrong current password rejected (FR-AUTH-12).** `/profile`: changing the password with an incorrect current password is refused.
<!-- screenshot: S03_profile_wrong_current_password -->
*Screenshot S3 — included in the PDF report submitted through the course Google Form.*

**S4 — Sessions with revoke (FR-AUTH-11).** `/sessions`: every login of this account with *Revoke* and *Log out all other devices*.
<!-- screenshot: S04_sessions -->
*Screenshot S4 — included in the PDF report submitted through the course Google Form.*

**S5 — Group members and permissions (FR-RBAC-04/05).** `/groups/1` as the owner: Demo Student Two can create and edit, Demo Student Three is view-only; owner-only rename/delete/add-member forms.
<!-- screenshot: S05_group_members_permissions -->
*Screenshot S5 — included in the PDF report submitted through the course Google Form.*

**S6a — RBAC denial in the app (FR-RBAC-02).** `/admin` opened by a student shows *Access denied*.
<!-- screenshot: S06a_student_admin_denied_ui -->
*Screenshot S6a — included in the PDF report submitted through the course Google Form.*

**S6b — RBAC denial by the API (FR-RBAC-02).** Live Swagger UI `/api/docs`, authorised with Demo Student One's token: `GET /api/admin/stats` returns **403** `"You do not have permission to perform this action"`.
<!-- screenshot: S06b_student_admin_api_403 -->
*Screenshot S6b — included in the PDF report submitted through the course Google Form.*

### D2. Security Behaviour

**S7 — Expired access token rejected (FR-AUTH-09).** Live Swagger UI: `GET /api/users/me` with an access token whose `exp` is 5 minutes in the past returns **401** `"Access token expired"`.
<!-- screenshot: S07_expired_token_401 -->
*Screenshot S7 — included in the PDF report submitted through the course Google Form.*

**Banned user (FR-RBAC-07).** S11 shows an account in the *Banned* state (banned through the live admin UI); the rejection of a banned user's login and next request is covered by `test_auth.py`/`test_admin_dashboard.py` and the live check (D-limitations below).

### D3. Admin Dashboard

**S10 — Statistics and security view (FR-ADM-01/08).** `/admin` as Demo Staff One: totals, requests by status and failed logins grouped by IP (masked) and by account.
<!-- screenshot: S10_admin_dashboard -->
*Screenshot S10 — included in the PDF report submitted through the course Google Form.*

**S11 — Users list (FR-ADM-02/04, FR-RBAC-06).** `/admin/users`: search, role and status filters, bulk selection, a banned account with *Unban*, and disabled *Ban* buttons for admins.
<!-- screenshot: S11_admin_users -->
*Screenshot S11 — included in the PDF report submitted through the course Google Form.*

**S12 — User detail (FR-ADM-03).** `/admin/users/{id}` for Demo Student One: profile, requests, groups with role, active sessions and recent activity.
<!-- screenshot: S12_admin_user_detail -->
*Screenshot S12 — included in the PDF report submitted through the course Google Form.*

**S13 — Admin cannot ban another admin (FR-RBAC-06).** `/admin/users/{id}` for Demo Staff Two viewed by Demo Staff One: the *Ban* button is disabled; the API also returns 403.
<!-- screenshot: S13_admin_cannot_ban_admin -->
*Screenshot S13 — included in the PDF report submitted through the course Google Form.*

**S14a — All student groups (FR-ADM-06).** `/admin/groups`: every group with owner, member and request counts, search/filter, View/Delete and bulk selection.
<!-- screenshot: S14a_admin_all_groups -->
*Screenshot S14a — included in the PDF report submitted through the course Google Form.*

**S14b — Group detail for moderation (FR-ADM-06, FR-RBAC-08).** `/admin/groups/1`: owner, each member's Create/Edit/Assign permissions and the group's requests.
<!-- screenshot: S14b_admin_group_detail -->
*Screenshot S14b — included in the PDF report submitted through the course Google Form.*

**S14c — Content moderation (FR-ADM-07).** `/admin/moderation`: all print requests with search, status filter and bulk delete.
<!-- screenshot: S14c_moderation_requests -->
*Screenshot S14c — included in the PDF report submitted through the course Google Form.*

**S15 — Activity / audit log (FR-ADM-08/10).** `/admin/audit`: filters and the events produced by the steps above (logins, failed login, failed password change), IPs masked.
<!-- screenshot: S15_audit_log -->
*Screenshot S15 — included in the PDF report submitted through the course Google Form.*

**S23 — Staff queue with cost and payment (FR-DOM-03/04/06).** `/staff/queue`: status tabs with counts, filters (type, payment, file, dates), cost and payment status.
<!-- screenshot: S23_staff_queue_cost_payment -->
*Screenshot S23 — included in the PDF report submitted through the course Google Form.*

**S22 — Dark mode (FR-DOM-10).** `/requests` after clicking the theme toggle.
<!-- screenshot: S22_dark_mode -->
*Screenshot S22 — included in the PDF report submitted through the course Google Form.*

### D4. Deployment

**S20 — Live API documentation.** `/api/docs` on the production domain.
<!-- screenshot: S20_api_docs -->
*Screenshot S20 — included in the PDF report submitted through the course Google Form.*

The Vercel dashboard (S18/S19) was not captured because no browser session is logged in to Vercel on the build machine. Equivalent evidence was collected with the authenticated Vercel CLI: `vercel ls --environment production` shows the production deployment as **Ready** and aliased to `https://2331428.vercel.app`, and `vercel env ls production` lists exactly the ten variable names of Table 26 with values shown as *Hidden*.

### D5. Tests

Test output (copied from the terminal on 27 Nov 2026):

```text
$ cd backend && python -m pytest -q
........................................................................ [ 42%]
........................................................................ [ 85%]
sssssss.................                                                 [100%]
148 passed, 20 skipped in 30.29s

$ cd frontend && npm test
ℹ tests 7
ℹ pass 7
ℹ fail 0
```

**Evidence limitations.** Not captured as screenshots: the refresh request and httpOnly cookie in DevTools (S8), a banned user being rejected live (S9 — it would require banning a demo account), the ban dialog itself (it is a native browser prompt), a downloaded CSV (S17) and the Vercel dashboard (S18/S19). Each of these behaviours is covered by the automated tests and the live scripted checks listed in C11.

---

## Part E. Project Management and Conclusion

### E1. How to Run and Test

**Prerequisites:** Python 3.12+, Node.js 22.18+ (or 24), Git, a PostgreSQL database (e.g. a Supabase project) — or none for a quick local SQLite run.

```bash
git clone https://github.com/JannatulFerdous24/2331428_PrintPoint-Campus-Printing-Management-System.git
cd 2331428_PrintPoint-Campus-Printing-Management-System/backend
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                 # macOS/Linux: cp .env.example .env
```

Edit `backend/.env` (example values only):

```env
DATABASE_URL=postgresql://user:password@host:6543/postgres   # leave empty locally to use SQLite
MIGRATION_DATABASE_URL=postgresql://user:password@host:5432/postgres
JWT_SECRET=<at least 32 random characters>
PASSWORD_PEPPER=<at least 32 random characters>
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
CORS_ORIGINS=http://localhost:5173
COOKIE_SECURE=false
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<server-only key>
SUPABASE_STORAGE_BUCKET=print-documents
```

```bash
alembic upgrade head
python scripts/create_admin.py --email you@example.com --name "Your Name"   # asks for the password
uvicorn main:app --reload --port 8000           # API on http://localhost:8000, docs /api/docs

cd ../frontend
npm install
npm run dev                                     # http://localhost:5173 (proxies /api to :8000)

cd ../backend && python -m pytest -q            # backend tests
cd ../frontend && npm test                      # frontend tests
```

**Logging in with the test accounts:** two admin (print-shop staff) accounts and three user (student) accounts exist on the live site. Their user IDs and roles are in the README and Appendix A; passwords are given only in the submitted PDF / submission form, never in this file.

### E2. GitHub Work

**Table 28. Pull requests, branches and commits**

| Item | Link / ref | What it delivered |
|---|---|---|
| PR #3 (merged) | [#3](https://github.com/JannatulFerdous24/2331428_PrintPoint-Campus-Printing-Management-System/pull/3) | Mid project MVP: FastAPI backend, React frontend, documentation |
| PR #4 (merged) | [#4](https://github.com/JannatulFerdous24/2331428_PrintPoint-Campus-Printing-Management-System/pull/4) | Print-request CRUD (MVP), tests, Postman collection |
| Tag `mid-project-final` | `e607491` | Snapshot of the mid assessment (API docs moved to `/api/docs`) |
| Branch `feature/2-auth-rbac-supabase` | `fbad9dd` | JWT auth, sessions, RBAC module, groups, status workflow, documents, admin dashboard, Supabase migrations |
| | `c6f02a6` | Printing cost and payment tracking, dark/light mode |
| | `e265a6d` | Final report v1; SPA deep-link fix on Vercel |
| | `9955bff` | Admin group management (All Groups page, group detail, filters) |
| | `d883d9c` | Final report (PRD/SRS/TDD), README reorganisation |
| `main` | fast-forwarded from the feature branch | Production deployment source |

**Work timeline and attribution.** Single-member project. October 2026: mid project (CRUD, SQLite, Vercel). November 2026: authentication and RBAC (Supabase setup, migrations 0002–0003), workflows and documents, admin dashboard (viva on 26 Nov), then cost/payment, theme, production deployment and documentation (27 Nov). All commits are authored by the GitHub account JannatulFerdous24; AI assistance is declared in E5.

### E3. Limitations

- Payment is recorded manually by staff; there is no online payment.
- No e-mail verification, password reset by e-mail or notifications.
- Rates are fixed in code; changing them requires a deployment.
- Rate limiting is database-based (per account / per IP), not an edge-level limiter; IPs behind a shared NAT share the limit.
- Uploads are limited to 4 MB by Vercel's request size; only PDF and DOCX.
- No HTTP security headers middleware (CSP, X-Frame-Options) beyond Vercel's defaults (HSTS is sent by Vercel).
- No browser-level end-to-end test suite (Playwright/Cypress) in the repository; UI flows were verified with scripted API checks and the screenshots above.
- The demo accounts use a simple shared password chosen for grading; it is shorter than the app's own password policy because it was set directly by an administrator script.

### E4. Future Work

1. Online payment (bKash / card) — removes manual payment recording.
2. Notifications when a job is Ready — the most requested student feature.
3. Admin-editable price table — rates change each semester.
4. Browser E2E tests in CI — protects the UI flows on every push.
5. Security headers (CSP) and edge rate limiting — defence in depth.
6. Document preview and page-count detection from the file — fewer input mistakes.

### E5. Sources, Libraries and Tools

**Table 29. Sources, libraries and tools**

| Name | Version / link | Used for |
|---|---|---|
| FastAPI | ≥ 0.115 · fastapi.tiangolo.com | REST API, dependencies, OpenAPI docs |
| SQLModel / SQLAlchemy | ≥ 0.0.21 · sqlmodel.tiangolo.com | ORM and models |
| Alembic | ≥ 1.13 · alembic.sqlalchemy.org | migrations |
| psycopg | ≥ 3.2 | PostgreSQL driver |
| argon2-cffi | ≥ 25.1 | Argon2id hashing |
| PyJWT | ≥ 2.15 · RFC 7519 | JWT |
| pytest, httpx | ≥ 8.0, ≥ 0.27 | backend tests |
| React, React Router, Vite, TypeScript | 19.3, 7.18, 8.3, 7.0 | frontend |
| Supabase | supabase.com/docs | PostgreSQL, pooling, RLS, Storage signed URLs |
| Vercel | vercel.com/docs (services, rewrites, env vars, CLI) | hosting |
| OWASP Cheat Sheets / ASVS | owasp.org | password storage, sessions, CSRF, threat table |
| Mermaid | mermaid.js.org | diagrams in this report |
| Playwright (Python) | playwright.dev | capturing the live screenshots in Part D |
| Instructor reference | github.com/sayef-reyadh-labs/smarter-todo | report structure |
| **AI assistance** | Claude (Anthropic), via Claude Code | help with implementation, tests, deployment debugging, screenshots and drafting this documentation. All code and text were reviewed, run and tested by the student; test results and screenshots come from real runs. |

### Conclusion

PrintPoint now covers the full path of a campus print job — submission with a transparent price, staff processing, payment and collection — for students, teams and staff, with security designed in rather than added on: short-lived JWTs with revocable, rotating sessions, one RBAC module that enforces ownership and fine-grained group permissions on the server, and an admin dashboard whose every action is audited. The application is live on Vercel with a persistent Supabase backend, verified by 148 automated backend tests, 7 frontend tests and scripted checks against the production site.

---

## Appendix A. Test Accounts

| User ID (e-mail) | Role | Notes |
|---|---|---|
| demo.admin1@uni.edu | admin (Print-Shop Staff) | dashboard, users, groups, moderation, audit log, staff queue |
| demo.admin2@uni.edu | admin (Print-Shop Staff) | second admin (shows "admins cannot ban other admins") |
| demo.student1@uni.edu | user (Student) | owner of the group "CSE309 Project Team" |
| demo.student2@uni.edu | user (Student) | group member: can create + edit, cannot assign |
| demo.student3@uni.edu | user (Student) | group member: view only |

