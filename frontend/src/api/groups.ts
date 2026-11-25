import type { GroupDetail, GroupSummary, MemberFlags, PrintRequest } from "../types"
import { apiFetch } from "./client"

const json = (body: unknown) => JSON.stringify(body)

export const groupsApi = {
  list: () => apiFetch<GroupSummary[]>("/api/groups"),
  get: (id: number) => apiFetch<GroupDetail>(`/api/groups/${id}`),
  create: (name: string, description?: string) =>
    apiFetch<GroupDetail>("/api/groups", { method: "POST", body: json({ name, description: description || null }) }),
  rename: (id: number, name: string, description?: string | null) =>
    apiFetch<GroupDetail>(`/api/groups/${id}`, { method: "PATCH", body: json({ name, description }) }),
  remove: (id: number) => apiFetch<void>(`/api/groups/${id}`, { method: "DELETE" }),
  addMember: (id: number, email: string, flags: MemberFlags) =>
    apiFetch<GroupDetail>(`/api/groups/${id}/members`, { method: "POST", body: json({ email, ...flags }) }),
  updateMember: (id: number, userId: number, flags: MemberFlags) =>
    apiFetch<GroupDetail>(`/api/groups/${id}/members/${userId}`, { method: "PATCH", body: json(flags) }),
  removeMember: (id: number, userId: number) =>
    apiFetch<GroupDetail>(`/api/groups/${id}/members/${userId}`, { method: "DELETE" }),
  requests: (id: number) => apiFetch<PrintRequest[]>(`/api/print-requests?group_id=${id}`),
  setAssignee: (requestId: number, assigneeId: number | null) =>
    apiFetch<PrintRequest>(`/api/print-requests/${requestId}/assignee`, {
      method: "PATCH",
      body: json({ assignee_id: assigneeId }),
    }),
}

// Admin calls live in ./admin.ts
