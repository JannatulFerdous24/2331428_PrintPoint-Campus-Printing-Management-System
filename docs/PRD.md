# Product Requirements Document (PRD)

| Field | Value |
|---|---|
| **Project Title** | PrintPoint – Campus Printing Management System |
| **Version** | 1.0 (MVP) |
| **Date** | November 2026 |
| **Author** | PrintPoint Development Team |
| **Related Docs** | [SRS.md](./SRS.md) · [TDD.md](./TDD.md) |

---

## 1. Project Overview

PrintPoint is a web-based campus printing management system designed to streamline how students submit, track, and collect print jobs at university print shops. In its current form, most campus printing operations rely on informal processes: students hand-deliver USB drives or email documents to staff, staff manually maintain paper logs, and there is no standardised way to communicate job status back to students. PrintPoint replaces these fragmented workflows with a single, accessible web application.

The system provides a central dashboard where students can submit print requests — specifying the document name, number of copies, print type (black-and-white or colour), and any special notes — and track their request as it moves through the fulfilment lifecycle. Print-shop staff use the same interface to view the incoming queue, update job statuses, and manage completed or rejected jobs. The result is a transparent, auditable pipeline that eliminates guesswork on both sides.

PrintPoint is built as a full-stack application with a React + TypeScript frontend and a FastAPI (Python) backend backed by SQLite for development and PostgreSQL for production. Deployment is handled by Vercel, making the system accessible from any modern browser on any device without requiring software installation by the end user.

---

## 2. Problem Statement

University print shops face a common set of operational pain points that PrintPoint directly addresses:

- **Physical queues and wait times.** Students must physically visit the print shop to submit jobs and again to check whether the job is ready. During peak periods (exam season, assignment deadlines) this creates significant queues and wasted student time.
- **Manual errors and lost requests.** Paper-based or verbal logging of print jobs is error-prone. Jobs are lost, misread, or forgotten. There is no authoritative record of what was requested.
- **No real-time status tracking.** Neither students nor staff have a reliable way to know at a glance how many jobs are pending, which are in progress, or which are ready for collection. Staff must cross-reference handwritten notes, email inboxes, and memory.
- **No accountability or audit trail.** If a dispute arises (wrong number of copies, wrong print type, lost job) there is no timestamped record to refer to. This creates friction between students and staff.
- **Inefficient staff workflows.** Staff spend time answering status inquiries that could be answered by the system, reducing time available for actual printing work.

PrintPoint eliminates these problems by digitising the entire request-to-collection workflow.

---

## 3. Product Purpose and Objectives

The purpose of PrintPoint is to reduce friction, errors, and wait times in the campus print-shop workflow by providing a purpose-built digital management interface for both students and print-shop staff.

**Measurable objectives:**

1. **Reduce in-person status inquiries by 70%** within three months of deployment by giving students self-service access to their request status online.
2. **Achieve zero lost print requests** by replacing paper logs with a persistent, database-backed record of every submission.
3. **Improve staff throughput by 30%** — measured as print requests processed per staff-hour — by providing a structured queue instead of ad-hoc intake.
4. **Deliver API response times under 2 seconds** for 95% of requests under normal campus load conditions.
5. **Achieve a System Usability Scale (SUS) score of ≥ 75** from both student and staff user groups in post-launch testing.

---

## 4. Target Users

### 4.1 Students

| Attribute | Details |
|---|---|
| **Demographics** | Undergraduate and postgraduate students, 18–35 years old, diverse international mix |
| **Technical Literacy** | Moderate to high — comfortable with web forms and mobile apps |
| **Frequency of Use** | Occasional to regular; spikes around assignment and exam deadlines |
| **Primary Needs** | Submit print requests quickly, track status without visiting the shop, know when jobs are ready |
| **Pain Points** | Not knowing if a job was received; having to queue twice (submit + collect) |

### 4.2 Print-Shop Staff

| Attribute | Details |
|---|---|
| **Demographics** | Full-time and part-time campus employees, varied age ranges |
| **Technical Literacy** | Low to moderate — comfortable with basic web interfaces; no developer knowledge expected |
| **Frequency of Use** | Daily, continuously throughout their shift |
| **Primary Needs** | See all pending jobs at a glance, update job status as work progresses, resolve or reject problematic requests |
| **Pain Points** | Managing a disorganised paper queue; answering constant status-check enquiries from students |

### 4.3 Administrator *(Planned — Beta)*

| Attribute | Details |
|---|---|
| **Demographics** | Print-shop supervisor or IT administrator |
| **Technical Literacy** | Moderate to high |
| **Frequency of Use** | Periodic oversight and reporting |
| **Primary Needs** | Monitor overall queue health, review historical data, manage user accounts and permissions |
| **Pain Points** | No aggregate view of throughput or bottlenecks |

---

## 5. Product Scope

### 5.1 In Scope — MVP (Current Sprint: `feature/1-print-request-crud`)

- **Print request submission** — students submit a new request via a web form.
- **Print request CRUD** — full Create, Read (list and single), Update, Delete operations exposed via REST API and consumed by the frontend.
- **Status tracking** — requests move through a defined status workflow: `Pending → Processing → Ready → Collected / Rejected`.
- **Document name storage** — the document name is stored as a plain-text field (no file upload in MVP).
- **Request detail view** — any user can view the full details of a single print request.
- **Basic form validation** — required fields enforced on the frontend and backend.

### 5.2 In Scope — Beta (Planned)

- **Authentication** — JWT-based login for students and staff; session management.
- **Role-based access control** — students can only view/edit their own requests; staff can view and update all requests.
- **File upload** — students attach the actual document file (PDF/DOCX); stored in cloud object storage.
- **Admin dashboard** — aggregate statistics, throughput charts, bulk operations.
- **Email/push notifications** — automated status-change notifications to students.

### 5.3 Out of Scope

- Native mobile application (iOS/Android)
- Payment or billing integration
- Multi-campus or multi-institution support
- Direct hardware integration with printers
- Document editing or preview within the application

---

## 6. User Journeys

### 6.1 Student Journey — Submitting and Tracking a Print Request

1. Student opens PrintPoint in their browser.
2. Student navigates to the "New Print Request" form.
3. Student fills in their name, document name, number of copies, print type (B&W or Colour), and optional notes.
4. Student submits the form. The system creates the request with status `Pending` and shows confirmation.
5. Student returns later to the request list and can see the current status (`Pending`, `Processing`, `Ready`).
6. When status is `Ready`, student visits the print shop to collect their job.
7. Staff marks the request `Collected`. The student can see the final status if they check again.

### 6.2 Staff Journey — Processing a Queue of Requests

1. Staff member opens PrintPoint and views the list of all print requests, sorted by creation time.
2. Staff picks up the next `Pending` job, locates the associated document file (from the student in MVP, or from uploaded file in Beta), and begins printing.
3. Staff updates the request status to `Processing`.
4. When printing is complete and the job is ready for collection, staff updates status to `Ready`.
5. When the student arrives to collect, staff marks the request `Collected`.
6. If the job cannot be completed (missing file, insufficient credit, unreadable document), staff marks it `Rejected` and adds a note explaining the reason.

---

## 7. Use Cases

| ID | Name | Primary Actor | Brief Description |
|---|---|---|---|
| UC-01 | Create Print Request | Student | Student submits a new print job through the web form |
| UC-02 | View Request List | Student / Staff | User views the full list of print requests |
| UC-03 | View Request Detail | Student / Staff | User views full details of a single request |
| UC-04 | Update Request Status | Staff | Staff advances or rejects a request through the status workflow |
| UC-05 | Edit Request Details | Student | Student corrects details on a Pending request |
| UC-06 | Delete Request | Staff / Admin | A request is permanently removed from the system |

---

## 8. Functional Requirements

### 8.1 Print Request Management

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | The system shall allow a user to create a new print request with fields: student name, document name, number of copies, print type, and optional notes. | High |
| FR-02 | The system shall persist print requests in a database and assign each a unique integer ID and a UTC creation timestamp. | High |
| FR-03 | The system shall return a list of all print requests ordered by creation date descending. | High |
| FR-04 | The system shall return the full details of a single print request by its ID. | High |
| FR-05 | The system shall allow partial or full update of a print request (PATCH semantics). | High |
| FR-06 | The system shall allow deletion of a print request by ID, returning 204 No Content on success. | High |
| FR-07 | The system shall enforce a status workflow: only valid transitions are permitted (`Pending → Processing`, `Processing → Ready`, `Ready → Collected`, `* → Rejected`). | Medium |
| FR-08 | The system shall record an `updated_at` timestamp whenever a print request is modified. | Medium |

### 8.2 User Interface

| ID | Requirement | Priority |
|---|---|---|
| FR-09 | The frontend shall display a paginated or scrollable list of all print requests with status badges. | High |
| FR-10 | The frontend shall provide a form for creating a new print request with client-side validation. | High |
| FR-11 | The frontend shall provide a detail view showing all fields of a single print request. | High |
| FR-12 | The frontend shall provide an edit form pre-populated with existing request data. | High |

### 8.3 System

| ID | Requirement | Priority |
|---|---|---|
| FR-13 | The backend shall expose a `/api/health` endpoint returning `{"status": "ok"}` for deployment health checks. | High |
| FR-14 | The system shall return meaningful HTTP error responses (4xx/5xx) with a JSON body describing the error. | High |
| FR-15 | The backend shall use CORS middleware to allow requests from the frontend origin. | High |

---

## 9. Success Metrics

| Metric | Target | Measurement Method |
|---|---|---|
| API response time (p95) | < 2 seconds | Performance test with realistic load |
| Lost print requests | 0 | Audit comparison with manual logs |
| Staff throughput increase | ≥ 30% more requests processed per hour | Before/after time study |
| Student status-inquiry reduction | ≥ 70% fewer in-person status checks | Staff observation log |
| System Usability Scale (SUS) score | ≥ 75 / 100 | Post-launch usability survey |
| Frontend build success rate | 100% on main branch | CI pipeline pass rate |
| API error rate (5xx) | < 1% of all requests | Backend logging / monitoring |
| Time-to-submit (student) | < 2 minutes for new request | User testing sessions |

---

## 10. Assumptions and Constraints

**Assumptions:**
- All users have access to a modern browser (Chrome 120+, Firefox 121+, Safari 17+, Edge 120+).
- Network connectivity is available on campus; the system does not need to function offline.
- In MVP, there is no authentication; all requests are public (controlled environment, not public internet).
- Students and staff share the same interface in MVP; role separation is a Beta concern.
- The university network is reasonably reliable; the system does not need to handle extended outages.

**Constraints:**
- Development must use the approved technology stack: FastAPI, SQLModel, React 19, Vite, TypeScript, SQLite (dev), Vercel (deploy).
- No budget for paid third-party services in MVP (authentication, file storage, email) — these are Beta scope.
- The team is small (student project); complex infrastructure is deferred.

---

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| No authentication exposes all requests | High (MVP limitation) | Medium (controlled campus environment) | Deploy only within university network for MVP; add JWT auth in Beta |
| SQLite not suitable for concurrent production load | Medium | High | Use PostgreSQL on Vercel for production; SQLite only for local development |
| File upload complexity delayed to Beta | Low | Medium | Clearly communicate to users that document must be provided separately in MVP |
| Students submit incorrect details (wrong copies, etc.) | Medium | Low | Allow editing of Pending requests; add confirmation dialogs on submit |
| Vercel cold-start latency for serverless backend | Medium | Low | Health-check endpoint warms the function; acceptable for MVP traffic levels |
| Data loss from SQLite file corruption | Low | High | Automated database backups; switch to PostgreSQL in production |

---

## 12. Future Improvements / Roadmap

| Phase | Feature | Description |
|---|---|---|
| **Beta** | Authentication | JWT login for students and staff; session management |
| **Beta** | Role-Based Access Control | Students see only their own requests; staff see all |
| **Beta** | File Upload | Students upload PDF/DOCX; stored in Vercel Blob or S3 |
| **Beta** | Email Notifications | Automated email when status changes to Ready or Rejected |
| **Beta** | Admin Dashboard | Aggregate stats, throughput charts, export to CSV |
| **v2** | Mobile App | React Native app for iOS and Android |
| **v2** | Payment Integration | Student account debiting for print jobs |
| **v2** | Multi-Campus Support | Tenant isolation for multiple campus locations |
| **v2** | Printer Hardware Integration | Direct job dispatch to printer queue |
| **v2** | Analytics & Reporting | Historical trends, peak-period prediction |
