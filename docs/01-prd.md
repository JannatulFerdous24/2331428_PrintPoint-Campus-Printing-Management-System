# Product Requirements Document (PRD)

| Attribute | Value |
| --- | --- |
| Project Title | PrintPoint - Campus Printing Management System |
| Version | MVP + Beta |
| Releases | MVP – Mid-term, Beta – Final |
| Related Docs | [SRS](02-srs.md), [TDD](03-tdd.md) |

## 1. Release Plan & Scope
- **MVP (Mid-Term Demo):** Core print order management via REST APIs (CRUD), file upload configuration, local SQLite DB.
- **Beta (Final Demo):** JWT Auth, Role-Based Access Control (Student/Admin), User Dashboard, Live Deployment.

## 2. Problem Statement & Goals
- **Problem:** Long queues at campus print shops, manual page/cost calculation errors, and delays in file transfers.
- **Goal:** Allow students to upload documents and customize print settings remotely while providing operators an organized queue.

## 3. User Stories
- **US-01 (MVP):** As a student, I want to upload PDF/DOCX files and specify print settings (copies, color/B&W).
- **US-02 (MVP):** As a print shop admin, I want to view all incoming print orders.
- **US-03 (Beta):** As a user, I want to log in securely so that my print history is saved.

## 4. Feature List (MoSCoW)
- **Must Have (MVP):** File upload, print options configuration, order CRUD REST APIs.
- **Must Have (Beta):** User authentication, Student/Admin roles, Order status updates.
