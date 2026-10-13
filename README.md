# PrintPoint - Campus Printing Management System

PrintPoint is a web-based campus printing management system built with React (TypeScript) and FastAPI (Python). It allows students to upload documents and configure print settings remotely, while providing print shop operators with an organized order management queue.

## 📚 Project Documentation
- 📄 [Product Requirements Document (PRD)](docs/01-prd.md)
- 📄 [Software Requirements Specification (SRS)](docs/02-srs.md)
- 📄 [Technical Design Document (TDD)](docs/03-tdd.md)

## 🛠️ Tech Stack
- **Frontend:** React + TypeScript (Vite)
- **Backend:** FastAPI (Python)
- **Database:** SQLite (Local Development) / PostgreSQL

## 🚀 Release Scope & Features

### MVP (Mid-Term Demo)
- Document Upload & Print Configuration (Copies, Page Range, Color/B&W).
- Core REST APIs for handling print orders (CRUD operations).
- Order storage in local database.

### Beta (Final Demo)
- User Authentication (JWT) & Profile Dashboard.
- Role-Based Access Control (RBAC: Student vs. Admin/Vendor).
- Admin Print Queue Management & Live Deployment.

## 💻 How to Run Locally

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
cd frontend
npm install
npm run dev
