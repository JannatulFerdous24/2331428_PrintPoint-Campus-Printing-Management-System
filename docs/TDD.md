# Technical Design Document (TDD)

| Field | Value |
|---|---|
| **Project Title** | PrintPoint – Campus Printing Management System |
| **Version** | 1.0 (MVP) |
| **Date** | November 2026 |
| **Author** | PrintPoint Development Team |
| **Related Docs** | [PRD.md](./PRD.md) · [SRS.md](./SRS.md) |

---

## 1. Purpose and Technical Overview

This Technical Design Document describes the architecture, technology choices, module design, API contract, database schema, deployment configuration, and development workflows for the PrintPoint system at the MVP milestone.

The goals driving the technical design are:

- **Simplicity over premature abstraction** — the MVP is a small CRUD application; the architecture reflects that without over-engineering.
- **Separation of concerns** — frontend and backend are independent services that communicate only via a well-defined REST API.
- **Fast local iteration** — Vite's dev server and FastAPI's `--reload` flag mean changes reflect in under a second.
- **Production-ready deployment path** — the same codebase that runs locally deploys to Vercel with no environment-specific branches.
- **Extendability** — the module structure (separate models, schemas, crud, routers) makes adding authentication, file upload, and other Beta features straightforward.

---

## 2. System Architecture

### 2.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User's Browser                           │
│                                                                 │
│   ┌───────────────────────────────────────┐                     │
│   │       React 19 + TypeScript SPA       │                     │
│   │           (served by Vite)            │                     │
│   │                                       │                     │
│   │  PrintRequestsPage                    │                     │
│   │  PrintRequestDetailPage               │                     │
│   │  PrintRequestForm                     │                     │
│   │  PrintRequestTable                    │                     │
│   │  StatusBadge  ConfirmDialog           │                     │
│   └────────────────┬──────────────────────┘                     │
└────────────────────┼────────────────────────────────────────────┘
                     │ HTTP/JSON  (/api/*)
                     │ (Vite proxy in dev; Vercel rewrite in prod)
┌────────────────────▼────────────────────────────────────────────┐
│                    FastAPI Application                           │
│                    (backend/main.py)                             │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │               Router: /api/print-requests                │  │
│   │            (routers/print_requests.py)                   │  │
│   └─────────────────┬────────────────────────────────────────┘  │
│                     │                                            │
│   ┌─────────────────▼────────────────────────────────────────┐  │
│   │                  CRUD Layer (crud.py)                    │  │
│   │   create / get_all / get_one / update / delete           │  │
│   └─────────────────┬────────────────────────────────────────┘  │
│                     │                                            │
│   ┌─────────────────▼────────────────────────────────────────┐  │
│   │              SQLModel / SQLAlchemy ORM                   │  │
│   │                   (database.py)                          │  │
│   └─────────────────┬────────────────────────────────────────┘  │
└─────────────────────┼──────────────────────────────────────────-┘
                      │ SQL
          ┌───────────▼───────────┐
          │      SQLite (dev)      │
          │   PostgreSQL (prod)   │
          └───────────────────────┘
```

### 2.2 Component Descriptions

| Component | Technology | Responsibility |
|---|---|---|
| **SPA (Frontend)** | React 19, TypeScript, Vite | All user-facing UI; communicates with backend via fetch API |
| **FastAPI App** | Python, FastAPI | HTTP routing, request validation, response serialisation |
| **Router** | FastAPI APIRouter | Groups all `/api/print-requests` endpoints |
| **CRUD Layer** | Python functions, SQLModel | Pure data-access functions; no HTTP concerns |
| **Models** | SQLModel (table=True) | Database table definition; source of truth for schema |
| **Schemas** | SQLModel / Pydantic | Request/response shapes; separate from DB model |
| **Database** | SQLite / PostgreSQL | Persistent storage |

### 2.3 Data Flow Description

**Create request example:**
1. User submits the React form → `fetch("POST /api/print-requests", body)`
2. Vite proxy (dev) or Vercel rewrite (prod) forwards the request to FastAPI.
3. FastAPI router calls the schema validator (Pydantic); returns 422 on failure.
4. Router calls `crud.create_print_request(session, data)`.
5. CRUD function creates a `PrintRequest` SQLModel instance, adds it to the session, commits, refreshes, and returns it.
6. FastAPI serialises the returned model to JSON and responds 201 Created.
7. React receives the response, updates local state, and redirects to the detail page.

---

## 3. Project Structure

The target file tree for the MVP sprint (`feature/1-print-request-crud`):

```
Printpoint_Campus_Printing_Management_System/
├── backend/
│   ├── main.py                     # FastAPI app instance, CORS, router registration
│   ├── database.py                 # Engine creation, session factory, create_db_and_tables()
│   ├── models.py                   # PrintRequest SQLModel table model
│   ├── schemas.py                  # PrintRequestCreate, PrintRequestUpdate, PrintRequestRead
│   ├── crud.py                     # create / list / get / update / delete functions
│   ├── requirements.txt            # Python dependencies
│   ├── .env.example                # Example environment variables
│   ├── routers/
│   │   ├── __init__.py
│   │   └── print_requests.py       # APIRouter with all CRUD endpoints
│   └── tests/
│       ├── __init__.py
│       └── test_print_requests.py  # pytest test suite using TestClient + in-memory SQLite
├── frontend/
│   ├── index.html                  # Vite entry point HTML
│   ├── package.json                # npm scripts and dependencies
│   ├── tsconfig.json               # TypeScript compiler configuration
│   ├── vite.config.ts              # Vite config with /api proxy
│   └── src/
│       ├── main.tsx                # React root render
│       ├── App.tsx                 # Root component / route switching (MVP: conditional render)
│       ├── index.css               # Global styles
│       ├── api/
│       │   └── printRequests.ts    # Typed fetch wrapper functions for all API calls
│       ├── types/
│       │   └── index.ts            # TypeScript interfaces (PrintRequest, PrintRequestCreate, etc.)
│       ├── components/
│       │   ├── PrintRequestForm.tsx    # Reusable create/edit form component
│       │   ├── PrintRequestTable.tsx   # Table listing all requests
│       │   ├── StatusBadge.tsx         # Colour-coded status chip component
│       │   └── ConfirmDialog.tsx       # Reusable "Are you sure?" modal
│       └── pages/
│           ├── PrintRequestsPage.tsx       # List page — fetches all, renders table
│           └── PrintRequestDetailPage.tsx  # Detail/edit page — fetches one, renders form
├── docs/
│   ├── PRD.md
│   ├── SRS.md
│   └── TDD.md
├── vercel.json         # Vercel services config and URL rewrites
├── pyproject.toml      # Python project metadata (Poetry / pip)
├── README.md
└── .gitignore
```

> **Note:** The structure above reflects the planned MVP sprint deliverable. The current `main` branch contains only the starter template (`backend/main.py`, `frontend/src/App.tsx`). The full structure is being built on the `feature/1-print-request-crud` branch.

---

## 4. Technology Stack and Justification

| Layer | Technology | Version | Justification |
|---|---|---|---|
| **Backend Framework** | FastAPI | ≥ 0.115 | High performance, async-ready, automatic OpenAPI docs, native Pydantic integration |
| **Backend ORM** | SQLModel | ≥ 0.0.21 | Combines SQLAlchemy and Pydantic; single class defines both DB schema and API schema; eliminates duplication |
| **Backend Language** | Python | 3.10+ | Team familiarity; excellent ecosystem for web APIs and future ML/data features |
| **Database (dev)** | SQLite | 3.x (stdlib) | Zero-setup local development; no external service needed |
| **Database (prod)** | PostgreSQL | 15+ | Production-grade concurrency, ACID compliance, Vercel Postgres integration |
| **Frontend Framework** | React | 19.3 | Industry standard; large community; composable component model |
| **Frontend Language** | TypeScript | 7.x | Type safety catches API contract mismatches at compile time |
| **Frontend Build Tool** | Vite | 8.x | Near-instant HMR; fast production build; built-in proxy for API calls |
| **Testing (backend)** | pytest + httpx | 8.x / 0.27 | pytest is the Python standard; httpx's TestClient drives FastAPI without a real server |
| **Testing (frontend)** | *(Planned — Beta)* | — | Vitest + React Testing Library planned for Beta |
| **Deployment** | Vercel | — | Zero-config deployment for both FastAPI (serverless) and Vite (static); automatic HTTPS, CDN |
| **Dependency management** | pip / poetry | — | pip for simplicity in CI; poetry for local development lock files |

---

## 5. Frontend Design

### 5.1 Component Hierarchy

```
App
├── PrintRequestsPage          (list view)
│   ├── PrintRequestTable
│   │   └── StatusBadge        (per row)
│   └── [Link to Create Form]
│
└── PrintRequestDetailPage     (detail / edit view)
    ├── PrintRequestForm       (create or edit mode)
    ├── StatusBadge
    └── ConfirmDialog          (shown on delete)
```

| Component | Role |
|---|---|
| `App.tsx` | Root component; manages which page is shown (MVP uses state-based routing; no router library in MVP) |
| `PrintRequestsPage` | Fetches all requests on mount, displays them in a table, provides a "New Request" action |
| `PrintRequestDetailPage` | Fetches a single request by ID, shows details, provides edit and delete actions |
| `PrintRequestForm` | Controlled form with validation; used for both creating and editing (receives optional initial data) |
| `PrintRequestTable` | Renders a table of requests; each row links to the detail page |
| `StatusBadge` | Colour-coded chip/pill displaying the status string; maps status → CSS class |
| `ConfirmDialog` | Modal overlay asking the user to confirm a destructive action (deletion) |

### 5.2 Pages Description

**PrintRequestsPage** — the primary landing page. On mount it calls `GET /api/print-requests` and renders the result in `PrintRequestTable`. An empty state message is shown if the array is empty. A "New Print Request" button/link navigates to the create form.

**PrintRequestDetailPage** — shown when the user clicks a specific request or navigates to a create URL. In view mode it displays all fields. In edit mode it renders `PrintRequestForm` pre-populated with the current data. The delete button triggers `ConfirmDialog` and then `DELETE /api/print-requests/{id}`.

### 5.3 State Management Approach

The MVP uses React's built-in `useState` and `useEffect` hooks only — no external state management library (Redux, Zustand, etc.) is needed at this scale.

- Each page component owns its local data state (`printRequests`, `loading`, `error`).
- `useEffect` triggers the initial data fetch on page mount.
- Form state is managed with a single `useState` object holding all field values.
- Navigation between pages is handled by a top-level `page` state variable in `App.tsx` (MVP pragmatism; React Router to be added in Beta).

### 5.4 API Integration Pattern

All API calls are centralised in `src/api/printRequests.ts`. This module exports typed async functions:

```typescript
// Example shape (not exhaustive)
export async function listPrintRequests(): Promise<PrintRequest[]>
export async function getPrintRequest(id: number): Promise<PrintRequest>
export async function createPrintRequest(data: PrintRequestCreate): Promise<PrintRequest>
export async function updatePrintRequest(id: number, data: Partial<PrintRequestCreate>): Promise<PrintRequest>
export async function deletePrintRequest(id: number): Promise<void>
```

Each function uses the native `fetch` API, checks `res.ok`, and throws a typed error if the response is not successful. Pages call these functions inside `useEffect` or event handlers, managing loading and error state locally.

---

## 6. Backend Design

### 6.1 Module Descriptions

| Module | Responsibility |
|---|---|
| `main.py` | Creates the `FastAPI()` app instance, registers CORS middleware, includes the print-requests router, mounts the static frontend (in production), and calls `create_db_and_tables()` on startup. |
| `database.py` | Reads `DATABASE_URL` from environment (defaulting to `sqlite:///./printpoint.db`), creates the SQLAlchemy engine, defines the `get_session()` dependency generator, and exports `create_db_and_tables()`. |
| `models.py` | Defines the `PrintRequest` SQLModel class with `table=True`. This is the single source of truth for the DB schema. Includes all column definitions, defaults, and constraints. |
| `schemas.py` | Defines `PrintRequestCreate` (fields required for creation), `PrintRequestUpdate` (all fields optional for PATCH), and `PrintRequestRead` (fields returned to the client, including `id` and timestamps). |
| `crud.py` | Pure functions that accept a `Session` and input data. No HTTP or FastAPI concepts here — just database operations. Makes the CRUD layer independently testable. |
| `routers/print_requests.py` | FastAPI `APIRouter` with all five CRUD endpoints. Calls CRUD functions, raises `HTTPException` for 404/422 cases, and specifies response models. |

### 6.2 Request Handling Flow

1. HTTP request arrives at the FastAPI ASGI server.
2. CORS middleware evaluates the `Origin` header; adds appropriate headers or rejects.
3. FastAPI routes the request to the matching endpoint function in the router.
4. FastAPI validates the path parameters and request body against the Pydantic schema; returns 422 automatically on failure.
5. The endpoint function calls `get_session()` (dependency injection) to obtain a DB session.
6. The endpoint calls the appropriate CRUD function with the session and validated data.
7. The CRUD function issues SQLAlchemy ORM calls; commits and returns the result.
8. The endpoint function returns the result; FastAPI serialises it using the `response_model`.
9. The HTTP response is sent back to the client.

### 6.3 Dependency Injection — `get_session`

```python
# database.py (illustrative)
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

FastAPI's `Depends(get_session)` injects a fresh session into each request handler. The `with` block guarantees the session is closed (and any open transaction is rolled back on error) after the handler returns, even if an exception is raised.

### 6.4 Error Handling Strategy

- **Validation errors** (missing fields, wrong types, invalid enum values) are handled automatically by Pydantic/FastAPI and return 422.
- **Not-found errors** are raised explicitly in CRUD functions or router handlers as `HTTPException(status_code=404, detail="Print request not found")`.
- **Invalid status transitions** are detected in the update CRUD function; raise `HTTPException(status_code=422, detail="Invalid status transition: ...")`.
- **Unexpected exceptions** (database connection failure, etc.) propagate to FastAPI's default 500 handler.
- All error responses follow the `{"detail": "..."}` JSON format.

---

## 7. Database Schema

### 7.1 `print_requests` Table

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, NOT NULL, AUTO INCREMENT | — | Unique record identifier |
| `student_name` | VARCHAR | NOT NULL | — | Name of the requesting student |
| `document_name` | VARCHAR | NOT NULL | — | Human-readable name of the document to print |
| `copies` | INTEGER | NOT NULL, ≥ 1 | — | Number of copies requested |
| `print_type` | VARCHAR | NOT NULL | — | `'Black & White'` or `'Colour'` |
| `status` | VARCHAR | NOT NULL | `'Pending'` | Current lifecycle status |
| `notes` | VARCHAR | NULLABLE | `NULL` | Optional instructions from the student |
| `created_at` | DATETIME | NOT NULL | `utcnow()` | UTC datetime of record creation |
| `updated_at` | DATETIME | NOT NULL | `utcnow()` | UTC datetime of last modification |

### 7.2 SQLModel Class (Illustrative)

```python
class PrintRequest(SQLModel, table=True):
    __tablename__ = "print_requests"

    id: int | None = Field(default=None, primary_key=True)
    student_name: str
    document_name: str
    copies: int = Field(ge=1)
    print_type: str
    status: str = Field(default="Pending")
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 7.3 Indexes

| Index | Column(s) | Type | Notes |
|---|---|---|---|
| `pk_print_requests` | `id` | Primary Key | Auto-created by SQLModel |
| *(Planned Beta)* | `status` | B-Tree | For fast queue filtering |
| *(Planned Beta)* | `created_at` | B-Tree | For efficient chronological ordering |

---

## 8. REST API Design

### POST /api/print-requests

**Create a new print request.**

Request body:
```json
{
  "student_name": "Alice Smith",
  "document_name": "Thesis_Chapter3.pdf",
  "copies": 2,
  "print_type": "Black & White",
  "notes": "Double-sided please"
}
```

Response (201 Created):
```json
{
  "id": 1,
  "student_name": "Alice Smith",
  "document_name": "Thesis_Chapter3.pdf",
  "copies": 2,
  "print_type": "Black & White",
  "status": "Pending",
  "notes": "Double-sided please",
  "created_at": "2026-11-04T08:30:00Z",
  "updated_at": "2026-11-04T08:30:00Z"
}
```

Status codes: `201` success, `422` validation failure.

---

### GET /api/print-requests

**List all print requests.**

Response (200 OK):
```json
[
  {
    "id": 1,
    "student_name": "Alice Smith",
    "document_name": "Thesis_Chapter3.pdf",
    "copies": 2,
    "print_type": "Black & White",
    "status": "Pending",
    "notes": "Double-sided please",
    "created_at": "2026-11-04T08:30:00Z",
    "updated_at": "2026-11-04T08:30:00Z"
  }
]
```

Status codes: `200` success.

---

### GET /api/print-requests/{id}

**Get a single print request by ID.**

Response (200 OK): same as single object above.

Status codes: `200` success, `404` not found.

---

### PATCH /api/print-requests/{id}

**Partially update a print request.**

Request body (any subset of fields):
```json
{
  "status": "Processing"
}
```

Response (200 OK): full updated print request object.

Status codes: `200` success, `404` not found, `422` invalid transition or validation failure.

---

### DELETE /api/print-requests/{id}

**Permanently delete a print request.**

Response: `204 No Content` (empty body).

Status codes: `204` success, `404` not found.

---

### GET /api/health

**Liveness check for Vercel and monitoring.**

Response (200 OK):
```json
{"status": "ok"}
```

---

## 9. Authentication and Authorization Design

### 9.1 Current State (MVP)

Authentication is **not implemented** in the MVP. All API endpoints are publicly accessible without credentials. This is an accepted risk for the MVP, which is intended to operate in a controlled campus environment (not exposed to the public internet).

### 9.2 Planned Design (Beta)

- **Mechanism:** JSON Web Tokens (JWT) issued on login via a `POST /api/auth/login` endpoint.
- **Library:** `python-jose` for JWT encoding/decoding; `passlib` for password hashing (bcrypt).
- **Token storage:** HttpOnly cookie or `Authorization: Bearer <token>` header.
- **User model:** New `User` table with `id`, `email`, `hashed_password`, `role` (`student` | `staff` | `admin`).
- **Integration:** A `get_current_user` FastAPI dependency replaces the direct `get_session` dependency on protected routes.
- **Role enforcement:** Students may only read/create/update their own requests. Staff may update status on any request. Admins may delete any request.

---

## 10. File Upload Design

### 10.1 Current State (MVP)

File upload is **not implemented** in the MVP. The `document_name` field stores a plain text string (the document's name or filename) provided by the student. Students must deliver the actual file separately (e.g., via email or USB drive).

### 10.2 Planned Design (Beta)

- **Storage:** Vercel Blob Storage or AWS S3 (depending on cost).
- **API change:** `POST /api/print-requests` will accept `multipart/form-data` instead of JSON; the file binary is uploaded alongside the metadata fields.
- **Backend:** FastAPI `UploadFile` parameter; the file is streamed to object storage; the returned storage URL is saved in a `document_url` column on the `print_requests` table.
- **Frontend:** The create form gains a file picker (`<input type="file">`); the form uses `FormData` instead of `JSON.stringify`.
- **Security:** File type validation (allow-list: PDF, DOCX, DOC); maximum file size enforced (e.g., 50 MB); virus scanning considered for v2.

---

## 11. Request Status Workflow

### 11.1 State Machine Diagram

```
                    ┌─────────┐
             ┌─────►│ Pending │──────────────────────────┐
             │      └────┬────┘                          │
             │           │ Staff starts job              │
             │           ▼                               │
             │     ┌───────────┐                         │ Staff rejects
             │     │Processing │─────────────────────────┤
             │     └─────┬─────┘                         │
             │           │ Staff finishes printing        │
             │           ▼                               │
             │       ┌───────┐                           │
             │       │ Ready │────────────────────────── ┤
             │       └───┬───┘                           │
             │           │ Student collects              ▼
             │           ▼                         ┌──────────┐
             │     ┌───────────┐                   │ Rejected │ (terminal)
             │     │ Collected │ (terminal)         └──────────┘
             │     └───────────┘
             │
          [any state can transition to Rejected]
```

### 11.2 Valid Transitions Table

| From | To | Triggered By |
|---|---|---|
| `Pending` | `Processing` | Staff |
| `Pending` | `Rejected` | Staff |
| `Processing` | `Ready` | Staff |
| `Processing` | `Rejected` | Staff |
| `Ready` | `Collected` | Staff (on student collection) |
| `Ready` | `Rejected` | Staff |
| `Collected` | *(none)* | — |
| `Rejected` | *(none)* | — |

### 11.3 Enforcement

The `update_print_request` CRUD function checks the current status against a transition allowlist before applying the update. If the requested transition is not in the allowlist, it raises an `HTTPException(422)` with a message like:
`"Invalid status transition: cannot move from 'Collected' to 'Processing'."`

---

## 12. Security Considerations

### 12.1 Input Validation

All incoming data is validated by Pydantic schemas before reaching the CRUD layer. Invalid types, missing required fields, and out-of-range values are rejected with 422 automatically by FastAPI.

### 12.2 SQL Injection Prevention

All database queries are issued through SQLModel/SQLAlchemy ORM methods (`session.add`, `session.get`, `select()`). No raw SQL strings are constructed from user input, eliminating SQL injection at the framework level.

### 12.3 CORS Configuration

The backend uses FastAPI's `CORSMiddleware` configured to allow requests from:
- `http://localhost:5173` (Vite dev server)
- The Vercel production domain (set via `CORS_ORIGINS` environment variable)

Only the methods used by the application (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS`) are allowed.

### 12.4 Future Security Enhancements (Beta / v2)

- **HTTPS everywhere:** Vercel enforces HTTPS in production automatically.
- **JWT authentication:** Prevents unauthorised access and enforces per-user data isolation.
- **Rate limiting:** Middleware (e.g., `slowapi`) to prevent abuse of the API.
- **Content-Security-Policy headers:** Mitigate XSS in the React app.
- **File upload scanning:** Antivirus scanning on uploaded documents before storage.

---

## 13. Testing Strategy

### 13.1 Backend Unit Tests (pytest)

Tests live in `backend/tests/test_print_requests.py` and use:
- **`pytest`** as the test runner.
- **`httpx.TestClient`** (wrapped by FastAPI) to make real HTTP requests to the app without a network socket.
- **In-memory SQLite** (`sqlite:///:memory:`) injected via dependency override so tests are fully isolated and leave no files on disk.

Each test function:
1. Overrides `get_session` with a fresh in-memory session.
2. Calls `create_db_and_tables()` to set up the schema.
3. Uses `TestClient` to send HTTP requests.
4. Asserts response status codes and JSON body fields.

### 13.2 Test Coverage Areas

| Area | Test Cases |
|---|---|
| Health endpoint | Returns 200 `{"status": "ok"}` |
| Create request | 201 with correct fields; 422 on missing required field |
| List requests | Empty list; list after creates |
| Get single | 200 with correct data; 404 for non-existent ID |
| Update | 200 with updated fields; 404 for non-existent; 422 for invalid transition |
| Delete | 204 on success; subsequent GET returns 404 |
| Status transitions | All valid transitions succeed; all invalid transitions return 422 |

### 13.3 How to Run Tests

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
pytest tests/ -v
```

---

## 14. Local Development Setup

### 14.1 Prerequisites

| Tool | Minimum Version | Install |
|---|---|---|
| Python | 3.10 | https://www.python.org/downloads/ |
| Node.js | 22 | https://nodejs.org/ |
| npm | bundled with Node.js | — |
| Git | any recent | https://git-scm.com/ |

### 14.2 Backend Setup

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
cp .env.example .env               # edit DATABASE_URL if needed
fastapi dev main.py                # starts on http://localhost:8000 with auto-reload
```

**macOS / Linux (bash/zsh):**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
fastapi dev main.py
```

- API is available at `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`

### 14.3 Frontend Setup

```bash
cd frontend
npm install
npm run dev                        # starts Vite on http://localhost:5173
```

- Opens at `http://localhost:5173`
- `/api/*` requests are automatically proxied to `http://localhost:8000`

### 14.4 Full-Stack via Vercel CLI (optional)

To simulate the production Vercel environment locally:

```bash
npm install -g vercel
vercel dev -L                      # runs both services together
```

---

## 15. Environment Variables and Configuration

### 15.1 Backend Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | `sqlite:///./printpoint.db` | No | SQLAlchemy connection string. Set to a PostgreSQL URL in production. |
| `CORS_ORIGINS` | `http://localhost:5173` | No | Comma-separated list of allowed CORS origins. |

These are read at startup using `python-dotenv` from a `.env` file in the `backend/` directory (not committed to source control).

**`.env.example`:**
```env
DATABASE_URL=sqlite:///./printpoint.db
CORS_ORIGINS=http://localhost:5173
```

### 15.2 Frontend Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `VITE_API_URL` | *(empty — uses Vite proxy)* | No | Explicit API base URL; only needed if not using the Vite proxy. |

Vite exposes variables prefixed with `VITE_` to the browser bundle. In production, the Vercel rewrite handles API routing so no explicit URL is needed.

---

## 16. Deployment and Production Configuration

### 16.1 Vercel Configuration (`vercel.json`)

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "backend": {
      "root": "backend",
      "framework": "fastapi",
      "entrypoint": "main:app"
    },
    "frontend": {
      "root": "frontend",
      "framework": "vite"
    }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "backend" } },
    { "source": "/(.*)", "destination": { "service": "frontend" } }
  ]
}
```

**How it works:**
- Vercel builds the `frontend/` as a static Vite project and serves it from its global CDN.
- Vercel deploys the `backend/` as a FastAPI serverless function (Python runtime).
- Requests to `/api/*` are rewritten to the backend service; all other requests go to the frontend static files.
- Both services share the same domain — no CORS issues in production (same origin).

### 16.2 Step-by-Step Vercel Deployment

1. **Push to GitHub.** Ensure `main` branch is up to date.
2. **Create a Vercel project.** Go to https://vercel.com/new and import the GitHub repository.
3. **Set Root Directory** to `./` (the project root, not `frontend/` or `backend/`).
4. **Set environment variables** in the Vercel project settings:
   - `DATABASE_URL` → your PostgreSQL connection string (e.g., from Vercel Postgres)
   - `CORS_ORIGINS` → your Vercel deployment URL (e.g., `https://printpoint.vercel.app`)
5. **Click Deploy.** Vercel runs both builds automatically.
6. **Subsequent deploys:** Every push to `main` triggers an automatic redeploy. Manual deploy: `vercel --prod` from the project root.

### 16.3 Production Database

For production, provision a PostgreSQL database (Vercel Postgres, Supabase, or Railway). Set `DATABASE_URL` to the connection string in Vercel environment variables. SQLModel is compatible with PostgreSQL out of the box — no code changes are needed.

---

## 17. Known Limitations and Future Technical Improvements

### 17.1 MVP Limitations

| Limitation | Details | Planned Fix |
|---|---|---|
| No authentication | All endpoints are unauthenticated; anyone with the URL can read/modify/delete any request | JWT auth in Beta |
| No file upload | Document is referenced by name only; files must be delivered out-of-band | Vercel Blob / S3 in Beta |
| SQLite in dev | SQLite does not support high concurrency; not suitable for multiple simultaneous writers | PostgreSQL is already the production target |
| No pagination | `GET /api/print-requests` returns all records; will be slow with a large dataset | Offset/limit pagination in Beta |
| No filtering/sorting | Cannot filter by status or sort by date via the API | Query parameter filtering in Beta |
| State-based routing | MVP uses a `useState` variable in `App.tsx` to switch pages instead of URL routing | React Router to be added in Beta |
| No notification system | Staff and students have no way to be alerted of status changes without refreshing | WebSocket or email notifications in Beta |
| No error boundary | Unhandled React errors may crash the whole UI | React `ErrorBoundary` component in Beta |

### 17.2 Beta Improvements Planned

- JWT authentication and session management.
- Role-based access control (student, staff, admin roles).
- File upload with Vercel Blob storage.
- React Router for URL-based navigation.
- Pagination and filtering on the list endpoint.
- Email notifications on status changes (SendGrid or Resend).
- Admin dashboard with aggregate metrics.
- Frontend unit tests with Vitest and React Testing Library.
- CI/CD pipeline with GitHub Actions (lint, test, build on every PR).
