// Types for documents, the staff queue and the admin dashboard (Prompts 8b, 8c, 9).
// Re-exported from ./index, so pages import everything from "../types".
import type { AdminUser, PaymentStatus, PrintType, RequestStatus } from "./index"

/** Same limits as the server (backend/documents.py); the server re-checks every upload. */
export const MAX_UPLOAD_BYTES = 4_000_000
export const ALLOWED_EXTENSIONS = [".pdf", ".docx"]

export interface DocumentLink {
  url: string
  expires_in: number
  filename: string
}

export interface StatusHistoryEntry {
  from_status: RequestStatus | null
  to_status: RequestStatus
  changed_by_id: number | null
  changed_by_name: string | null
  note: string | null
  changed_at: string
}

export interface RequestQuery {
  q?: string
  status?: RequestStatus | ""
  print_type?: PrintType | ""
  payment_status?: PaymentStatus | ""
  has_document?: "" | "true" | "false"
  created_from?: string
  created_to?: string
  sort?: "newest" | "oldest"
  skip?: number
  limit?: number
}

export interface AdminStats {
  total_users: number
  banned_users: number
  admins: number
  total_requests: number
  requests_by_status: Record<RequestStatus, number>
  total_groups: number
  new_users_7d: number
  new_requests_7d: number
  failed_logins_24h: number
}

export interface AuditLogEntry {
  id: number
  created_at: string
  action: string
  actor_id: number | null
  actor_email: string | null
  target_type: string | null
  target_id: string | null
  ip_address: string | null
  user_agent: string | null
  details: Record<string, unknown> | null
}

export interface AdminUserDetail {
  user: AdminUser
  locked_until: string | null
  failed_login_count: number
  requests_total: number
  requests: { id: number; document_name: string; status: RequestStatus; copies: number; print_type: PrintType; created_at: string }[]
  groups: { id: number; name: string; role: "owner" | "member"; can_create?: boolean; can_edit?: boolean; can_assign?: boolean }[]
  sessions: { id: number; ip_address: string | null; user_agent: string | null; created_at: string; last_used_at: string; expires_at: string }[]
  activity: AuditLogEntry[]
}

export interface AdminGroup {
  id: number
  name: string
  description: string | null
  owner_id: number
  owner_email: string
  created_at: string
  member_count: number
  request_count: number
}

export interface BulkResult {
  done: number[]
  skipped: { id: number; reason: string }[]
}

export interface FailedLogins {
  hours: number
  total_failed: number
  by_ip: { ip_address: string | null; failures: number; accounts_tried: number; last_attempt: string }[]
  by_account: {
    email: string
    user_id: number | null
    failures: number
    last_attempt: string
    known_account: boolean
    locked_until: string | null
  }[]
}
