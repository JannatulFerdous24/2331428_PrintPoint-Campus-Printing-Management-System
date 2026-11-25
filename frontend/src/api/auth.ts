import type { AuthResponse, SessionInfo, User } from "../types"
import { apiFetch } from "./client"

const json = (body: unknown) => JSON.stringify(body)
const AJAX = { "X-Requested-With": "XMLHttpRequest" }

export const authApi = {
  signup: (full_name: string, email: string, password: string) =>
    apiFetch<AuthResponse>(
      "/api/auth/signup",
      { method: "POST", body: json({ full_name, email, password }) },
      { retryOn401: false },
    ),

  login: (email: string, password: string) =>
    apiFetch<AuthResponse>(
      "/api/auth/login",
      { method: "POST", body: json({ email, password }) },
      { retryOn401: false },
    ),

  logout: () =>
    apiFetch<void>("/api/auth/logout", { method: "POST", headers: AJAX }, { retryOn401: false }),

  sessions: () => apiFetch<SessionInfo[]>("/api/auth/sessions"),

  revokeSession: (id: number) => apiFetch<void>(`/api/auth/sessions/${id}`, { method: "DELETE" }),

  revokeOtherSessions: () =>
    apiFetch<{ revoked: number }>("/api/auth/sessions/revoke-others", { method: "POST" }),

  updateProfile: (data: { full_name?: string; email?: string; current_password?: string }) =>
    apiFetch<User>("/api/users/me", { method: "PATCH", body: json(data) }),

  changePassword: (current_password: string, new_password: string) =>
    apiFetch<{ detail: string; other_sessions_revoked: number }>("/api/users/me/password", {
      method: "POST",
      body: json({ current_password, new_password }),
    }),
}
