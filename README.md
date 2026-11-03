# PrintPoint — Campus Printing Management System

[![Frontend](https://img.shields.io/badge/Frontend-React_19_+_TypeScript_+_Vite-61dafb?logo=react)](https://react.dev/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-SQLite_%2F_PostgreSQL-003B57?logo=sqlite)](https://www.sqlite.org/)
[![Deployment](https://img.shields.io/badge/Deploy-Vercel-black?logo=vercel)](https://vercel.com/)

PrintPoint is a modern web-based campus printing management system that enables university students to submit, customize, and track printing requests online without physically standing in line at the campus print shop. Print-shop staff and administrators manage incoming requests through an organized digital queue with a robust status lifecycle.

---

## 📚 Project Documentation

Detailed project specifications and architectural designs are available in the [`docs/`](./docs) folder:

- 📋 **[Product Requirements Document (PRD)](./docs/PRD.md)**: Product purpose, target users (students, staff, admin), measurable success metrics, full feature scope, user journeys, risks, and roadmap.
- 📐 **[Software Requirements Specification (SRS)](./docs/SRS.md)**: IEEE-standard specification covering functional requirements (FR-01 to FR-15), non-functional requirements (NFR-01 to NFR-10), use cases (UC-01 to UC-05), API specifications, database design, acceptance criteria, and traceability matrix.
- 🏗️ **[Technical Design Document (TDD)](./docs/TDD.md)**: Technical architecture, directory structure, module breakdown, SQLModel database schema, REST API design, state transitions, security, testing strategy, and Vercel deployment configuration.

---

## 🚀 Features (Mid-Project MVP)

### Print Request Management (Full CRUD)
- **Create**: Students submit requests specifying student name, document name, copies (1–999), print type (Black & White or Color), and optional notes.
- **Read List**: Real-time tabular view showing request ID, student name, document title, copy count, print type, color-coded status badge, and timestamps.
- **Read Single**: Dedicated detail view inspecting all metadata of any print request.
- **Update**: Edit copy count, print type, student name, document name, notes, and advance request status according to business transition rules.
- **Delete**: Remove requests with a safe confirmation modal dialog.

### Request Status Lifecycle
Requests advance through an enforced state machine:
`Pending` ➔ `Processing` ➔ `Ready` ➔ `Collected` (or `Rejected` from any active state).

---

## 🛠️ Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Frontend** | React 19, TypeScript, Vite | Modern functional components, responsive UI, loading states, error boundaries |
| **Backend** | FastAPI, Python 3.10+ | High-performance asynchronous REST API with Pydantic validation |
| **ORM / DB** | SQLModel (SQLAlchemy) | SQLite for local development, PostgreSQL-ready for production |
| **Testing** | pytest, HTTPX TestClient | Automated backend unit and integration test suite |
| **Deployment** | Vercel | Monorepo configuration via `vercel.json` routing `/api` to backend and `/*` to Vite |

---

## 📁 Project Structure

```
Printpoint_Campus_Printing_Management_System/
├── backend/
│   ├── main.py                  # FastAPI entry point, CORS, lifespan, static mounting
│   ├── database.py              # SQLite / PostgreSQL engine and session dependency
│   ├── models.py                # SQLModel table definitions (PrintRequest, enums)
│   ├── schemas.py               # Pydantic validation schemas (Create, Read, Update)
│   ├── crud.py                  # Database CRUD logic and status transition validation
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example             # Environment variable template
│   ├── routers/
│   │   ├── __init__.py
│   │   └── print_requests.py    # REST API route handlers (/api/print-requests)
│   └── tests/
│       ├── __init__.py
│       └── test_print_requests.py # Pytest test suite with in-memory SQLite
├── frontend/
│   ├── index.html               # HTML entry point
│   ├── package.json             # NPM dependencies and scripts
│   ├── tsconfig.json            # TypeScript configuration
│   ├── vite.config.ts           # Vite config with /api reverse proxy
│   └── src/
│       ├── main.tsx             # React DOM root
│       ├── App.tsx              # Application shell
│       ├── index.css            # Custom CSS styling and responsive layout
│       ├── api/
│       │   └── printRequests.ts # Typed API client for FastAPI endpoints
│       ├── types/
│       │   └── index.ts         # TypeScript interfaces, enums, transition maps
│       ├── components/
│       │   ├── PrintRequestForm.tsx  # Create / Edit request form
│       │   ├── PrintRequestTable.tsx # Tabular list of requests
│       │   ├── StatusBadge.tsx       # Color-coded status badge
│       │   └── ConfirmDialog.tsx     # Delete confirmation modal
│       └── pages/
│           └── PrintRequestsPage.tsx # Master CRUD page
├── docs/
│   ├── PRD.md                   # Product Requirements Document
│   ├── SRS.md                   # Software Requirements Specification
│   └── TDD.md                   # Technical Design Document
├── vercel.json                  # Multi-service Vercel deployment configuration
├── pyproject.toml               # Python project configuration
├── README.md                    # Project documentation
└── .gitignore                   # Git ignore patterns
```

---

## 💻 Local Development Setup

### Prerequisites
- **Node.js** 20+ and **npm**
- **Python** 3.10+ (with `pip` and `venv`)

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the backend development server
fastapi dev main.py
# or: uvicorn main:app --reload --port 8000
```

The backend will start at `http://localhost:8000`.
- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc documentation: `http://localhost:8000/redoc`

### 2. Frontend Setup

In a separate terminal:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run the Vite development server
npm run dev
```

The frontend will run at `http://localhost:5173`. Vite automatically proxies `/api/*` calls to `http://localhost:8000`.

### 3. Running Production Build Locally

```bash
# Build the React frontend
cd frontend
npm run build

# Start FastAPI (it automatically serves frontend/dist as static files)
cd ../backend
uvicorn main:app --port 8000
```
Open `http://localhost:8000` to use the fully combined production build.

---

## ⚙️ Environment Variables

Create `.env` in the `backend/` directory (see `backend/.env.example`):

```env
# Database connection string (defaults to local SQLite if omitted)
DATABASE_URL=sqlite:///./printpoint.db

# Allowed CORS origins (comma-separated)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

For the frontend (optional in `frontend/.env`):
```env
# Optional API override (defaults to relative /api when omitted)
VITE_API_URL=
```

---

## 🧪 Running Automated Tests

Run the backend test suite:

```bash
cd backend
python -m pytest tests/ -v
```

The test suite covers:
- ✅ Request creation (`POST /api/print-requests`)
- ✅ Input validation rejection (missing fields, zero/negative copies)
- ✅ Request listing (`GET /api/print-requests`)
- ✅ Single request retrieval (`GET /api/print-requests/{id}`)
- ✅ Nonexistent ID handling (`404 Not Found`)
- ✅ Request updates (`PATCH /api/print-requests/{id}`)
- ✅ Valid status transitions (`Pending` ➔ `Processing`)
- ✅ Invalid status transition rejection (`422 Unprocessable Entity`)
- ✅ Request deletion and verification (`DELETE /api/print-requests/{id}`)
- ✅ Status filtering (`GET /api/print-requests?status=Pending`)

---

## 📡 REST API Reference

| Method | Endpoint | Description | Request Body | Status Codes |
|---|---|---|---|---|
| `POST` | `/api/print-requests` | Create new print request | `PrintRequestCreate` JSON | `201`, `422` |
| `GET` | `/api/print-requests` | List all print requests | Query: `status`, `skip`, `limit` | `200` |
| `GET` | `/api/print-requests/{id}` | Get single request details | None | `200`, `404` |
| `PATCH` | `/api/print-requests/{id}` | Update request details / status | `PrintRequestUpdate` JSON | `200`, `404`, `422` |
| `DELETE` | `/api/print-requests/{id}` | Delete a print request | None | `204`, `404` |
| `GET` | `/api/health` | Health check endpoint | None | `200` |

---

## ☁️ Deployment to Vercel

The project is preconfigured for zero-config Vercel deployment using `vercel.json`:

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

### Steps to Deploy:
1. Push your changes to the GitHub repository:
   ```bash
   git push origin main
   ```
2. In [Vercel](https://vercel.com/new), click **Add New Project** and import your repository.
3. Keep the **Root Directory** as `./`.
4. Add environment variables if using a hosted database:
   - `DATABASE_URL`: `postgresql://user:password@host:port/database`
5. Click **Deploy**. Vercel will automatically build the Vite frontend and deploy the FastAPI backend service.

---

## 🎓 University Assessment & Viva Guide

### Architecture Overview
PrintPoint follows a clean, decoupled architecture:
1. **Presentation Layer (React + TypeScript)**: Responsive single-page application communicating via asynchronous `fetch` requests with JSON payloads.
2. **API & Business Logic (FastAPI + Pydantic)**: Enforces input validation, CORS policies, and state machine validation.
3. **Persistence Layer (SQLModel + SQLite/PostgreSQL)**: Type-safe database mapping with automatic schema migrations.

### How to Demonstrate in Browser
1. Open `http://localhost:5173` (or the deployed Vercel URL).
2. **Create**: Click `+ New Request`, fill out student name, document name, copies, choose `Color` or `Black & White`, click `Create Request`.
3. **Read List**: Observe the new row immediately rendered in the table with a yellow `Pending` badge.
4. **Read Single**: Click `View` to see full metadata including created/updated timestamps and notes.
5. **Update**: Click `Edit`, update the copy count or transition status from `Pending` to `Processing`, click `Save Changes`.
6. **Delete**: Click `Delete`, confirm in the modal dialog, observe the item disappear from the table.
7. **Developer Tools**: Press `F12` > Network tab to show POST/GET/PATCH/DELETE requests with `201`, `200`, `204` status codes.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
