export type PrintType = "Black & White" | "Color"

export type RequestStatus = "Pending" | "Processing" | "Ready" | "Collected" | "Rejected"

export const PRINT_TYPES: PrintType[] = ["Black & White", "Color"]

export type PaymentStatus = "Pending" | "Paid"
export const PAYMENT_STATUSES: PaymentStatus[] = ["Pending", "Paid"]

/** Rates come from the server (GET /api/print-requests/pricing); the server recalculates the cost. */
export interface Pricing {
  currency: string
  rates_per_page: Record<PrintType, number>
}

export const MAX_PAGES = 1000

export function formatTaka(amount: number): string {
  return `Tk ${amount.toLocaleString("en-US")}`
}

export const REQUEST_STATUSES: RequestStatus[] = [
  "Pending",
  "Processing",
  "Ready",
  "Collected",
  "Rejected",
]

// Valid transitions (mirror of backend/models.py; the server enforces them):
//   Pending -> Processing -> Ready -> Collected      Pending -> Rejected
export const VALID_TRANSITIONS: Record<RequestStatus, RequestStatus[]> = {
  Pending: ["Processing", "Rejected"],
  Processing: ["Ready"],
  Ready: ["Collected"],
  Collected: [],
  Rejected: [],
}

export interface PrintRequest {
  id: number
  student_name: string
  document_name: string
  copies: number
  print_type: PrintType
  status: RequestStatus
  notes: string | null
  created_at: string
  updated_at: string
  owner_id?: number | null
  group_id?: number | null
  assignee_id?: number | null
  /** Why staff rejected the request; null unless status is Rejected. */
  rejection_reason?: string | null
  /** Uploaded document metadata (the private storage key is never sent to the browser). */
  has_document?: boolean
  original_filename?: string | null
  content_type?: string | null
  file_size_bytes?: number | null
  uploaded_at?: string | null
  /** Pages in the document; total_cost (Taka) = pages x copies x rate, calculated by the server. */
  pages?: number
  total_cost?: number
  payment_status?: PaymentStatus
  paid_at?: string | null
  /** What the current user may do, computed by the server (backend/rbac.py). */
  permissions?: RequestPermissions
}

export interface RequestPermissions {
  view: boolean
  edit: boolean
  delete: boolean
  change_status: boolean
  assign: boolean
  update_payment?: boolean
}

export interface CreatePrintRequestData {
  student_name: string
  document_name: string
  copies: number
  pages: number
  print_type: PrintType
  notes?: string
  group_id?: number
}

export interface UpdatePrintRequestData {
  student_name?: string
  document_name?: string
  copies?: number
  pages?: number
  print_type?: PrintType
  status?: RequestStatus
  notes?: string
  /** Staff note for a status change; required (5-500 characters) when rejecting. */
  reason?: string
}

export const MIN_REJECTION_REASON = 5

// ---------------------------------------------------------------------------
// Authentication
// ---------------------------------------------------------------------------

/** Stored roles. Shown to people as "Student" and "Print-Shop Staff (Admin)". */
export type UserRole = "user" | "admin"

export const ROLE_LABELS: Record<UserRole, string> = {
  user: "Student",
  admin: "Print-Shop Staff (Admin)",
}

export interface User {
  id: number
  email: string
  full_name: string
  role: UserRole
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: "bearer"
  expires_in: number
  user: User
}

export interface SessionInfo {
  id: number
  ip_address: string | null
  user_agent: string | null
  created_at: string
  last_used_at: string
  expires_at: string
  current: boolean
}

// ---------------------------------------------------------------------------
// Groups (class / club / student team) and admin
// ---------------------------------------------------------------------------

export interface GroupPermissions {
  is_owner: boolean
  is_member: boolean
  can_create: boolean
  can_edit: boolean
  can_assign: boolean
  can_manage: boolean
}

export interface GroupSummary {
  id: number
  name: string
  description: string | null
  owner_id: number
  owner_name: string
  member_count: number
  created_at: string
  my_permissions: GroupPermissions
}

export interface GroupMemberInfo {
  user_id: number
  full_name: string
  email: string
  is_owner: boolean
  can_create: boolean
  can_edit: boolean
  can_assign: boolean
  joined_at: string
}

export interface GroupDetail extends GroupSummary {
  members: GroupMemberInfo[]
}

export interface MemberFlags {
  can_create: boolean
  can_edit: boolean
  can_assign: boolean
}

export interface AdminUser {
  id: number
  email: string
  full_name: string
  role: UserRole
  is_banned: boolean
  ban_reason: string | null
  banned_at: string | null
  created_at: string
}

export * from "./dashboard"
