import type {
  AdminGroup,
  AdminGroupDetail,
  AdminStats,
  AdminUser,
  AdminUserDetail,
  AuditLogEntry,
  BulkResult,
  FailedLogins,
  UserRole,
} from "../types"
import { apiFetch, apiPage, downloadFile, queryString } from "./client"

type Params = Record<string, string | number | boolean | null | undefined>
const json = (body: unknown) => JSON.stringify(body)
const post = <T>(path: string, body?: unknown) =>
  apiFetch<T>(path, { method: "POST", ...(body === undefined ? {} : { body: json(body) }) })

/** Every call here is checked by the server: 401 when logged out, 403 for students. */
export const adminApi = {
  stats: () => apiFetch<AdminStats>("/api/admin/stats"),

  users: (params: Params = {}) => apiPage<AdminUser>(`/api/admin/users${queryString(params)}`),
  user: (id: number) => apiFetch<AdminUserDetail>(`/api/admin/users/${id}`),
  ban: (id: number, reason: string) => post<AdminUser>(`/api/admin/users/${id}/ban`, { reason }),
  unban: (id: number) => post<AdminUser>(`/api/admin/users/${id}/unban`),
  setRole: (id: number, role: UserRole) =>
    apiFetch<AdminUser>(`/api/admin/users/${id}/role`, { method: "PATCH", body: json({ role }) }),
  revokeSessions: (id: number) => post<{ revoked: number }>(`/api/admin/users/${id}/revoke-sessions`),
  bulkBan: (ids: number[], reason: string) => post<BulkResult>("/api/admin/users/bulk-ban", { user_ids: ids, reason }),
  bulkUnban: (ids: number[]) => post<BulkResult>("/api/admin/users/bulk-unban", { user_ids: ids }),

  groups: (params: Params = {}) => apiPage<AdminGroup>(`/api/admin/groups${queryString(params)}`),
  group: (id: number) => apiFetch<AdminGroupDetail>(`/api/admin/groups/${id}`),
  deleteRequest: (id: number) => apiFetch<void>(`/api/admin/print-requests/${id}`, { method: "DELETE" }),
  deleteGroup: (id: number) => apiFetch<void>(`/api/admin/groups/${id}`, { method: "DELETE" }),
  bulkDeleteRequests: (ids: number[]) => post<BulkResult>("/api/admin/print-requests/bulk-delete", { ids }),
  bulkDeleteGroups: (ids: number[]) => post<BulkResult>("/api/admin/groups/bulk-delete", { ids }),

  auditLogs: (params: Params = {}) => apiPage<AuditLogEntry>(`/api/admin/audit-logs${queryString(params)}`),
  failedLogins: (hours = 24) => apiFetch<FailedLogins>(`/api/admin/security/failed-logins?hours=${hours}`),

  /** CSV export with the SAME filters as the table on screen. */
  exportCsv: (kind: "users" | "print-requests" | "audit-logs", params: Params = {}) =>
    downloadFile(`/api/admin/export/${kind}.csv${queryString(params)}`, `printpoint-${kind}.csv`),
}
