# Software Requirements Specification (SRS)

| Attribute | Value |
| --- | --- |
| Project Title | PrintPoint - Campus Printing Management System |
| Version | MVP + Beta |
| Related Docs | [PRD](01-prd.md), [TDD](03-tdd.md) |

## 1. Roles & Permissions
- **Student (Beta):** Upload files, create orders, view personal order history.
- **Admin / Vendor (Beta):** View all orders, update status (`PENDING` -> `PRINTING` -> `READY` -> `COMPLETED`).

## 2. Functional Requirements
- **FR-01 (MVP):** System shall allow students to upload documents and set page count, color mode, and copies.
- **FR-02 (MVP):** System shall provide REST endpoints to Create, Read, Update, and Delete print orders.
- **FR-03 (Beta):** System shall authenticate users via JWT tokens.
- **FR-04 (Beta):** System shall restrict order status modification to Admin users only.

## 3. Non-Functional Requirements
- **NFR-01 (Performance):** API responses and file upload confirmation shall be under 2 seconds.
- **NFR-02 (Security):** Passwords must be hashed; API endpoints protected via authorization tokens in Beta.
