# Software Requirements Specification (SRS)

| Field | Value |
|---|---|
| **Project Title** | PrintPoint – Campus Printing Management System |
| **Version** | 1.0 (MVP) |
| **Date** | November 2026 |
| **Author** | PrintPoint Development Team |
| **Related Docs** | [PRD.md](./PRD.md) · [TDD.md](./TDD.md) |

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification describes the functional and non-functional requirements for the PrintPoint Campus Printing Management System, MVP release. It is intended as the authoritative reference for developers, testers, and stakeholders to understand what the system must do, how it must behave under various conditions, and what constitutes correct implementation.

### 1.2 Scope

PrintPoint is a full-stack web application that allows university students to submit and track print requests, and allows print-shop staff to manage those requests through a defined status lifecycle. The MVP covers the core Print Request CRUD operations and the status-tracking workflow. Authentication, file upload, and role-based access control are deferred to the Beta release.

The system comprises:
- A **FastAPI (Python) REST API** serving all data operations under the `/api` prefix.
- A **React 19 + TypeScript single-page application** served by Vite in development and built for static hosting in production.
- A **SQLite database** for local development, with production deployment targeting PostgreSQL via Vercel.

### 1.3 Definitions and Terminology

| Term | Definition |
|---|---|
| **Print Request** | A record representing a student's request for a document to be printed; the core entity of the system |
| **Status** | The current lifecycle stage of a Print Request: one of `Pending`, `Processing`, `Ready`, `Collected`, `Rejected` |
| **CRUD** | Create, Read, Update, Delete — the four standard data operations |
| **REST** | Representational State Transfer — architectural style for the HTTP API |
| **SPA** | Single-Page Application — the React frontend that renders dynamically in the browser without full page reloads |
| **ORM** | Object-Relational Mapper — SQLModel maps Python classes to database tables |
| **JWT** | JSON Web Token — planned authentication mechanism for Beta |
| **Pydantic** | Python data validation library underpinning FastAPI request/response schemas |
| **SQLModel** | Python library combining SQLAlchemy and Pydantic for database models |
| **Vite** | Fast JavaScript build tool and development server used for the React frontend |
| **MVP** | Minimum Viable Product — the current in-scope release |
| **Beta** | Next planned release adding authentication, file upload, and role-based access |

### 1.4 References

- FastAPI documentation: https://fastapi.tiangolo.com
- SQLModel documentation: https://sqlmodel.tiangolo.com
- React 19 documentation: https://react.dev
- Vite documentation: https://vitejs.dev
- Vercel documentation: https://vercel.com/docs
- [PRD.md](./PRD.md) — Product Requirements Document
- [TDD.md](./TDD.md) — Technical Design Document

### 1.5 Document Overview

Section 2 describes the overall product context. Section 3 details functional requirements with IDs, priorities, and implementation status. Section 4 covers non-functional requirements. Section 5 provides detailed use cases. Sections 6–8 cover interface, API, and database requirements. Sections 9–11 address error handling, acceptance criteria, and traceability.

---

## 2. Overall Description

### 2.1 Product Perspective

PrintPoint is a new, standalone web application. It does not integrate with any existing university system in the MVP. It replaces manual, paper-based print-job tracking at the campus print shop. The system is self-contained: the API and database are deployed as a single Vercel project alongside the static frontend. Future versions may integrate with university SSO (SAML/OAuth), student billing systems, and physical printer hardware.

### 2.2 Product Functions Summary

- Accept new print request submissions via a web form.
- Store and retrieve print requests from a persistent database.
- Allow requests to be viewed as a list or individually by ID.
- Allow request details to be updated (partial updates).
- Allow requests to be deleted.
- Track request status through a defined workflow.
- Serve a health-check endpoint for deployment monitoring.

### 2.3 User Classes and Characteristics

| User Class | Description | Frequency of Use | Technical Expertise |
|---|---|---|---|
| **Student** | Submits print requests and tracks their status | Occasional to frequent (deadline-driven spikes) | Moderate — comfortable with web forms |
| **Print-Shop Staff** | Manages the request queue; updates statuses | Daily, continuous during shift | Low to moderate — no developer knowledge |
| **Administrator** *(Beta)* | Oversees operations; manages users and settings | Periodic | Moderate to high |

### 2.4 Operating Environment

| Environment Aspect | Requirement |
|---|---|
| **Browser** | Chrome 120+, Firefox 121+, Safari 17+, Edge 120+ |
| **Operating System** | Any (browser-based; no OS-specific requirements) |
| **Network** | Stable internet connection required; no offline mode |
| **Screen Resolution** | Minimum 1024 × 768; responsive design recommended |
| **Backend Runtime** | Python 3.10+ |
| **Frontend Build** | Node.js 22+ (for local development and build) |
| **Database (dev)** | SQLite 3.x (included with Python) |
| **Database (prod)** | PostgreSQL 15+ (Vercel Postgres or equivalent) |

### 2.5 Design and Implementation Constraints

- The backend must be implemented in Python using FastAPI and SQLModel.
- The frontend must be implemented in TypeScript using React 19 and Vite.
- The deployment platform is Vercel; the `vercel.json` configuration defines service routing.
- Authentication is explicitly excluded from the MVP; all endpoints are unauthenticated.
- File storage is excluded from MVP; the document name is captured as a text field only.
- The system must use SQLite for local development and must be compatible with PostgreSQL for production.
- The API must follow REST conventions and return JSON.

### 2.6 Assumptions and Dependencies

- Users have access to a supported browser and a network connection.
- Vercel provides adequate serverless function execution time for all API calls.
- SQLModel's compatibility layer handles both SQLite and PostgreSQL without code changes.
- The Python virtual environment is managed by the developer locally (using `venv` or `poetry`).

---

## 3. Functional Requirements

### 3.1 Print Request Management

| ID | Title | Description | Priority | Status |
|---|---|---|---|---|
| FR-01 | Create Print Request | The system shall accept a POST request with `student_name`, `document_name`, `copies`, `print_type`, and optional `notes`, persist the record, and return the created object with its assigned ID and timestamps. | High | Planned (Sprint) |
| FR-02 | Persist Request with Auto-ID | Each print request shall be assigned a unique auto-incrementing integer ID by the database. | High | Planned (Sprint) |
| FR-03 | Record Timestamps | The system shall automatically set `created_at` and `updated_at` to the current UTC datetime on creation, and update `updated_at` on every modification. | High | Planned (Sprint) |
| FR-04 | List All Print Requests | The system shall return all print requests as a JSON array via GET `/api/print-requests`. | High | Planned (Sprint) |
| FR-05 | Retrieve Single Request | The system shall return the full details of a single print request by ID via GET `/api/print-requests/{id}`. Return 404 if not found. | High | Planned (Sprint) |
| FR-06 | Update Print Request | The system shall allow partial update of any writable field (including status) via PATCH `/api/print-requests/{id}`. Return 404 if not found. | High | Planned (Sprint) |
| FR-07 | Delete Print Request | The system shall permanently delete a print request by ID via DELETE `/api/print-requests/{id}`. Return 204 on success, 404 if not found. | High | Planned (Sprint) |
| FR-08 | Status Workflow Enforcement | The system shall only permit valid status transitions. Invalid transitions shall return 422 Unprocessable Entity with a descriptive error message. | Medium | Planned (Sprint) |

### 3.2 User Interface

| ID | Title | Description | Priority | Status |
|---|---|---|---|---|
| FR-09 | Request List Page | The frontend shall display all print requests in a table or card list showing ID, student name, document name, copies, print type, status (with visual badge), and creation date. | High | Planned (Sprint) |
| FR-10 | Create Request Form | The frontend shall provide a form for submitting a new print request with client-side validation for required fields and valid copy count (≥ 1). | High | Planned (Sprint) |
| FR-11 | Request Detail Page | The frontend shall display all fields of a single print request and provide navigation back to the list. | High | Planned (Sprint) |
| FR-12 | Edit Request Form | The frontend shall pre-populate a form with existing request data and allow submission of changes via PATCH. | High | Planned (Sprint) |

### 3.3 System

| ID | Title | Description | Priority | Status |
|---|---|---|---|---|
| FR-13 | Health Check Endpoint | The API shall expose GET `/api/health` returning `{"status": "ok"}` with HTTP 200. | High | Implemented |
| FR-14 | Structured Error Responses | All API errors shall return JSON with at least a `detail` field describing the error. | High | Planned (Sprint) |
| FR-15 | CORS Support | The backend shall configure CORS middleware to permit requests from the frontend origin (localhost in dev, Vercel domain in prod). | High | Planned (Sprint) |

---

## 4. Non-Functional Requirements

| ID | Category | Requirement | Target |
|---|---|---|---|
| NFR-01 | Performance | API response time (p95) for all CRUD endpoints | < 2 seconds under normal load |
| NFR-02 | Performance | Frontend initial page load time | < 3 seconds on a 10 Mbps connection |
| NFR-03 | Security | All API inputs shall be validated by Pydantic schemas before processing | 100% input validation coverage |
| NFR-04 | Security | SQL queries shall be issued through SQLModel/SQLAlchemy ORM only; no raw string-interpolated SQL | No raw SQL concatenation |
| NFR-05 | Usability | The UI shall be navigable without documentation by a first-time user | SUS score ≥ 75 |
| NFR-06 | Usability | Error messages shall be displayed in plain language in the UI | Validated in usability testing |
| NFR-07 | Reliability | The system shall have no data loss for successfully persisted requests | 0 lost records |
| NFR-08 | Maintainability | Backend code shall be organised into separate modules (models, schemas, crud, routers) with no cross-layer imports in the wrong direction | Module separation enforced |
| NFR-09 | Compatibility | The API shall be compatible with PostgreSQL in addition to SQLite without code changes | SQLModel dialect compatibility |
| NFR-10 | Compatibility | The frontend shall function correctly in Chrome 120+, Firefox 121+, Safari 17+, Edge 120+ | Cross-browser testing |

---

## 5. Use Cases

### UC-01: Student Creates a Print Request

| Field | Details |
|---|---|
| **ID** | UC-01 |
| **Name** | Create Print Request |
| **Actor** | Student |
| **Preconditions** | The PrintPoint web app is open in a browser. The backend API is running. |
| **Main Flow** | 1. Student clicks "New Print Request" or navigates to the create form. 2. Student fills in: student name (required), document name (required), number of copies (required, ≥ 1), print type — Black & White or Colour (required), notes (optional). 3. Student clicks "Submit". 4. Frontend sends POST `/api/print-requests` with form data as JSON. 5. Backend validates input, creates a DB record with status `Pending`, returns 201 Created with the new request object. 6. Frontend displays a success message and redirects to the request detail or list page. |
| **Alternate Flow** | A2a. A required field is empty — frontend shows inline validation error; form is not submitted. A2b. Backend returns 422 — frontend displays the error detail to the user. |
| **Postconditions** | A new print request exists in the database with status `Pending` and a unique ID. |

### UC-02: Student Views Print Request List

| Field | Details |
|---|---|
| **ID** | UC-02 |
| **Name** | View Print Request List |
| **Actor** | Student / Staff |
| **Preconditions** | PrintPoint is open in a browser. |
| **Main Flow** | 1. User navigates to the home / list page. 2. Frontend sends GET `/api/print-requests`. 3. Backend returns a JSON array of all requests. 4. Frontend renders each request as a row in a table or card with status badge. |
| **Alternate Flow** | A3a. No requests exist — frontend shows a "No print requests yet" empty state message. A3b. Network error — frontend displays an error message and a retry button. |
| **Postconditions** | User can see all current print requests and their statuses. |

### UC-03: Student Views Single Request Detail

| Field | Details |
|---|---|
| **ID** | UC-03 |
| **Name** | View Single Request Detail |
| **Actor** | Student / Staff |
| **Preconditions** | PrintPoint is open. The user knows or has clicked on a specific request ID. |
| **Main Flow** | 1. User clicks on a request in the list, or navigates to the detail page. 2. Frontend sends GET `/api/print-requests/{id}`. 3. Backend returns the full request object. 4. Frontend renders all fields: ID, student name, document name, copies, print type, status, notes, created at, updated at. |
| **Alternate Flow** | A2a. Backend returns 404 — frontend shows "Request not found" message. |
| **Postconditions** | User can read all details of the specific print request. |

### UC-04: Staff Updates Request Status

| Field | Details |
|---|---|
| **ID** | UC-04 |
| **Name** | Update Request Status |
| **Actor** | Print-Shop Staff |
| **Preconditions** | Staff has the PrintPoint interface open. A print request exists with a non-terminal status. |
| **Main Flow** | 1. Staff views the request detail or list. 2. Staff selects a new status from a dropdown (e.g., `Processing`). 3. Staff clicks "Save" or confirms the update. 4. Frontend sends PATCH `/api/print-requests/{id}` with `{"status": "Processing"}`. 5. Backend validates the transition, updates the record, and returns the updated object. 6. Frontend displays the updated status. |
| **Alternate Flow** | A4a. Staff selects an invalid status transition — backend returns 422; frontend displays the error. |
| **Postconditions** | The print request's status and `updated_at` timestamp are updated in the database. |

### UC-05: Staff / Admin Deletes a Request

| Field | Details |
|---|---|
| **ID** | UC-05 |
| **Name** | Delete Print Request |
| **Actor** | Print-Shop Staff / Administrator |
| **Preconditions** | Staff has PrintPoint open. The target request exists. |
| **Main Flow** | 1. Staff navigates to the request detail or list. 2. Staff clicks "Delete". 3. Frontend shows a confirmation dialog. 4. Staff confirms deletion. 5. Frontend sends DELETE `/api/print-requests/{id}`. 6. Backend permanently removes the record and returns 204 No Content. 7. Frontend removes the item from the list and displays a success message. |
| **Alternate Flow** | A3a. Staff cancels the confirmation dialog — no request is sent; nothing is deleted. A5a. Backend returns 404 — request was already deleted; frontend shows an informational message and refreshes the list. |
| **Postconditions** | The print request no longer exists in the database. |

---

## 6. External Interface Requirements

### 6.1 User Interface

The frontend is a React 19 single-page application served by Vite in development and as a static build in production. It communicates with the backend exclusively via the REST API (no server-rendered HTML). The UI must:
- Be accessible at the root URL (`/`) in both development and production.
- Proxy all `/api/*` requests to the backend (via Vite proxy in dev; Vercel rewrites in prod).
- Display a status badge using colour-coding for visual clarity (e.g., orange for Pending, blue for Processing, green for Ready, grey for Collected, red for Rejected).

### 6.2 API Interface

The backend exposes a JSON REST API under the `/api` prefix. All request and response bodies use `Content-Type: application/json`. The API is documented interactively at `/docs` (Swagger UI) in development. See Section 7 for endpoint specifications.

### 6.3 Database Interface

The backend communicates with the database exclusively through SQLModel (which wraps SQLAlchemy). No raw SQL strings are constructed at runtime. Database sessions are managed via FastAPI dependency injection using a `get_session` generator function.

---

## 7. API Requirements

### POST /api/print-requests — Create Print Request

| Field | Value |
|---|---|
| **Method** | POST |
| **Path** | `/api/print-requests` |
| **Request Body** | `{ "student_name": "string (required)", "document_name": "string (required)", "copies": "integer ≥ 1 (required)", "print_type": "string: 'Black & White' | 'Colour' (required)", "notes": "string (optional)" }` |
| **Success Response** | 201 Created — full PrintRequest object including `id`, `status`, `created_at`, `updated_at` |
| **Error Responses** | 422 Unprocessable Entity — validation failure |

### GET /api/print-requests — List All Requests

| Field | Value |
|---|---|
| **Method** | GET |
| **Path** | `/api/print-requests` |
| **Query Params** | None (filtering/pagination is a Beta feature) |
| **Success Response** | 200 OK — JSON array of PrintRequest objects |

### GET /api/print-requests/{id} — Get Single Request

| Field | Value |
|---|---|
| **Method** | GET |
| **Path** | `/api/print-requests/{id}` |
| **Path Params** | `id` — integer |
| **Success Response** | 200 OK — single PrintRequest object |
| **Error Responses** | 404 Not Found |

### PATCH /api/print-requests/{id} — Update Request

| Field | Value |
|---|---|
| **Method** | PATCH |
| **Path** | `/api/print-requests/{id}` |
| **Path Params** | `id` — integer |
| **Request Body** | Any subset of writable fields: `student_name`, `document_name`, `copies`, `print_type`, `notes`, `status` |
| **Success Response** | 200 OK — updated PrintRequest object |
| **Error Responses** | 404 Not Found; 422 Unprocessable Entity (invalid status transition or field value) |

### DELETE /api/print-requests/{id} — Delete Request

| Field | Value |
|---|---|
| **Method** | DELETE |
| **Path** | `/api/print-requests/{id}` |
| **Path Params** | `id` — integer |
| **Success Response** | 204 No Content |
| **Error Responses** | 404 Not Found |

### GET /api/health — Health Check

| Field | Value |
|---|---|
| **Method** | GET |
| **Path** | `/api/health` |
| **Success Response** | 200 OK — `{"status": "ok"}` |

---

## 8. Database Requirements

### 8.1 PrintRequest Table Schema

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTO INCREMENT, NOT NULL | Unique request identifier |
| `student_name` | VARCHAR | NOT NULL | Name of the student submitting the request |
| `document_name` | VARCHAR | NOT NULL | Name/title of the document to be printed |
| `copies` | INTEGER | NOT NULL, CHECK ≥ 1 | Number of copies required |
| `print_type` | VARCHAR | NOT NULL | `'Black & White'` or `'Colour'` |
| `status` | VARCHAR | NOT NULL, DEFAULT `'Pending'` | Current lifecycle status |
| `notes` | VARCHAR | NULLABLE | Optional special instructions |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | UTC timestamp of creation |
| `updated_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | UTC timestamp of last modification |

### 8.2 Indexes

| Index | Columns | Purpose |
|---|---|---|
| Primary Key | `id` | Unique lookup by ID |
| *(Planned Beta)* | `status` | Fast filtering by status for queue views |
| *(Planned Beta)* | `created_at` | Efficient ordering by creation time |

### 8.3 Status Transition Rules

| From Status | Allowed Transitions |
|---|---|
| `Pending` | `Processing`, `Rejected` |
| `Processing` | `Ready`, `Rejected` |
| `Ready` | `Collected`, `Rejected` |
| `Collected` | *(terminal — no further transitions)* |
| `Rejected` | *(terminal — no further transitions)* |

---

## 9. Error Handling

### 9.1 Standard Error Response Format

All error responses return a JSON body in FastAPI's standard format:

```json
{
  "detail": "Human-readable description of the error"
}
```

For validation errors (422), FastAPI returns an extended format:

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 9.2 HTTP Status Codes

| Code | Meaning | When Used |
|---|---|---|
| 200 OK | Success with response body | GET, PATCH |
| 201 Created | Resource created | POST (create print request) |
| 204 No Content | Success with no response body | DELETE |
| 400 Bad Request | Malformed request | Generic client errors |
| 404 Not Found | Resource does not exist | GET/PATCH/DELETE with unknown ID |
| 422 Unprocessable Entity | Validation failure | Invalid field values, invalid status transitions |
| 500 Internal Server Error | Unexpected server error | Database connection failure, unhandled exceptions |

---

## 10. Acceptance Criteria

| AC ID | FR ID | Acceptance Criterion |
|---|---|---|
| AC-01 | FR-01 | Given a valid POST body, the system returns 201 Created with a JSON object containing an auto-assigned `id`, `status: "Pending"`, and UTC timestamps. |
| AC-02 | FR-02 | Two successive POST requests return objects with different, sequentially increasing IDs. |
| AC-03 | FR-03 | The `updated_at` field of an updated record is strictly greater than its `created_at`. |
| AC-04 | FR-04 | GET `/api/print-requests` returns a JSON array; after creating 3 requests, the array has at least 3 elements. |
| AC-05 | FR-05 | GET `/api/print-requests/999` (non-existent) returns 404 with a `detail` field. |
| AC-06 | FR-06 | PATCH `/api/print-requests/{id}` with `{"copies": 5}` returns 200 with `copies: 5`; other fields are unchanged. |
| AC-07 | FR-07 | DELETE `/api/print-requests/{id}` returns 204; subsequent GET of the same ID returns 404. |
| AC-08 | FR-08 | PATCH with `{"status": "Collected"}` on a `Pending` request returns 422 (invalid transition). |
| AC-09 | FR-09 | The list page renders a row/card for each request returned by the API, showing at minimum: student name, document name, status. |
| AC-10 | FR-10 | Submitting the create form with an empty `student_name` field does not send a network request and shows an inline validation error. |
| AC-11 | FR-13 | GET `/api/health` returns 200 with body `{"status": "ok"}`. |
| AC-12 | FR-14 | All error responses include a JSON body with a `detail` key. |
| AC-13 | FR-15 | A CORS preflight (OPTIONS) request from the frontend origin receives an appropriate `Access-Control-Allow-Origin` header. |

---

## 11. Requirements Traceability Matrix

| FR ID | Description | Implemented? | Test ID | Notes |
|---|---|---|---|---|
| FR-01 | Create Print Request | Planned (Sprint) | test_create_print_request | POST endpoint + DB write |
| FR-02 | Auto-increment ID | Planned (Sprint) | test_create_print_request | SQLModel default |
| FR-03 | Timestamps on create/update | Planned (Sprint) | test_updated_at_changes | SQLModel datetime fields |
| FR-04 | List All Requests | Planned (Sprint) | test_list_print_requests | GET all endpoint |
| FR-05 | Single Request by ID | Planned (Sprint) | test_get_print_request, test_get_not_found | GET by ID + 404 |
| FR-06 | Update (PATCH) | Planned (Sprint) | test_update_print_request | Partial update semantics |
| FR-07 | Delete | Planned (Sprint) | test_delete_print_request | 204 + 404 on re-fetch |
| FR-08 | Status Workflow | Planned (Sprint) | test_invalid_status_transition | 422 on bad transition |
| FR-09 | Request List Page | Planned (Sprint) | Manual / E2E | React table component |
| FR-10 | Create Form | Planned (Sprint) | Manual / E2E | Client-side validation |
| FR-11 | Detail Page | Planned (Sprint) | Manual / E2E | React detail component |
| FR-12 | Edit Form | Planned (Sprint) | Manual / E2E | Pre-populated form |
| FR-13 | Health Endpoint | Implemented | test_health | Existing in main.py |
| FR-14 | Structured Errors | Planned (Sprint) | test_not_found_error | FastAPI HTTPException |
| FR-15 | CORS Middleware | Planned (Sprint) | test_cors_headers | FastAPI CORSMiddleware |
