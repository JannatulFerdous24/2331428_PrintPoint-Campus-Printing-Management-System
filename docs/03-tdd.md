# Technical Design Document (TDD)

| Attribute | Value |
| --- | --- |
| Project Title | PrintPoint - Campus Printing Management System |
| Version | MVP + Beta |
| Related Docs | [PRD](01-prd.md), [SRS](02-srs.md) |

## 1. Tech Stack
- **Frontend:** React + TypeScript (Vite)
- **Backend:** FastAPI (Python)
- **Database:** SQLite (Local) / PostgreSQL
- **Auth (Beta):** JWT (JSON Web Tokens)

## 2. Architecture Diagram
[ Frontend: React (TS) ] <---> REST APIs (/api/v1) <---> [ Backend: FastAPI ] <---> [ Database ]
## 3. Data Model Schema

### User Entity (Beta)
- `id`: Integer (PK)
- `email`: String (Unique)
- `hashed_password`: String
- `role`: String (`student` | `admin`)

### PrintOrder Entity (MVP)
- `id`: Integer (PK)
- `file_name`: String
- `copies`: Integer
- `is_color`: Boolean
- `status`: String (`PENDING`, `PRINTING`, `READY`, `COMPLETED`)
- `created_at`: DateTime

## 4. API Endpoints Summary
- `POST /api/v1/orders/` — Create Order (MVP)
- `GET /api/v1/orders/` — List Orders (MVP)
- `PUT /api/v1/orders/{id}` — Update Order (MVP)
- `POST /api/v1/auth/login` — Authenticate User (Beta)
