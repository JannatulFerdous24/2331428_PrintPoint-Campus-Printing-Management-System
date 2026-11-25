/**
 * One place for every call to the PrintPoint API.
 *
 * - The ACCESS token lives only in this module's memory (never localStorage),
 *   so other scripts on the page cannot read it from storage.
 * - The REFRESH token is an httpOnly cookie: JavaScript cannot read it at all;
 *   the browser sends it automatically, only to /api/auth/*.
 * - If the server answers 401 (e.g. the 15-minute access token expired), we call
 *   /api/auth/refresh ONCE and retry the request. If refreshing fails too, the
 *   user is logged out.
 */
import type { AuthResponse } from "../types"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

/**
 * API base URL from the environment (frontend/.env.local or Vercel settings).
 * Empty (the default) = same origin: in development Vite proxies /api to the
 * backend, and on Vercel /api is routed to the backend service (vercel.json).
 * Never point a production build at localhost.
 */
const API_BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "").replace(/\/+$/, "")
// Cookies (the refresh token) must also be sent when the API is on another origin.
const CREDENTIALS: RequestCredentials = API_BASE ? "include" : "same-origin"

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

let accessToken: string | null = null
let onSessionExpired: (() => void) | null = null
let refreshInFlight: Promise<AuthResponse | null> | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler
}

/** Turn any error body into a readable sentence (fixes "[object Object]"). */
export async function readErrorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    const detail = body?.detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) {
      // FastAPI validation errors: [{loc: ["body","email"], msg: "..."}]
      return detail
        .map((e: { loc?: unknown[]; msg?: string }) => {
          const field = Array.isArray(e.loc) ? e.loc.filter((p) => p !== "body").join(".") : ""
          const msg = (e.msg ?? "Invalid value").replace(/^Value error, /, "")
          return field ? `${field}: ${msg}` : msg
        })
        .join("; ")
    }
    return `Request failed (HTTP ${res.status})`
  } catch {
    return res.statusText || `Request failed (HTTP ${res.status})`
  }
}

/**
 * Ask the server for a new access token using the refresh cookie.
 * Concurrent callers share ONE request: sending the same refresh token twice
 * would look like token theft to the server (rotation + reuse detection).
 */
export function refreshSession(): Promise<AuthResponse | null> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(apiUrl("/api/auth/refresh"), {
      method: "POST",
      credentials: CREDENTIALS,
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(async (res) => {
        if (!res.ok) {
          accessToken = null
          return null
        }
        const data = (await res.json()) as AuthResponse
        accessToken = data.access_token
        return data
      })
      .catch(() => {
        accessToken = null
        return null
      })
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

function send(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers)
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  // JSON by default; FormData (file uploads) must let the browser set its own multipart header.
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  return fetch(apiUrl(path), { ...init, headers, credentials: CREDENTIALS })
}

interface ApiOptions {
  /** false for login/signup: a 401 there means "wrong password", not "token expired". */
  retryOn401?: boolean
}

/** Sends a request with the access token; on 401 refreshes ONCE and retries. Returns the raw
 *  Response (for headers such as X-Total-Count, or file downloads). Throws ApiError if not ok. */
export async function apiResponse(path: string, init: RequestInit = {}, options: ApiOptions = {}): Promise<Response> {
  const { retryOn401 = true } = options
  let res = await send(path, init)

  if (res.status === 401 && retryOn401) {
    const refreshed = await refreshSession()
    if (refreshed) res = await send(path, init)
    if (!refreshed || res.status === 401) {
      onSessionExpired?.()
      throw new ApiError(401, "Your session has expired. Please log in again.")
    }
  }

  if (!res.ok) throw new ApiError(res.status, await readErrorMessage(res))
  return res
}

export async function apiFetch<T>(path: string, init: RequestInit = {}, options: ApiOptions = {}): Promise<T> {
  const res = await apiResponse(path, init, options)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** A page of results plus the total from the server's X-Total-Count header. */
export interface Page<T> {
  items: T[]
  total: number
}

export async function apiPage<T>(path: string): Promise<Page<T>> {
  const res = await apiResponse(path)
  const items = (await res.json()) as T[]
  return { items, total: Number(res.headers.get("X-Total-Count") ?? items.length) }
}

/** Builds "?a=1&b=x" from an object, skipping empty values. */
export function queryString(params: Record<string, string | number | boolean | null | undefined>): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v))
  }
  const s = qs.toString()
  return s ? `?${s}` : ""
}

/** Downloads a protected file (e.g. a CSV export) with the access token and saves it. */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const res = await apiResponse(path)
  const blob = await res.blob()
  const match = /filename="?([^"]+)"?/.exec(res.headers.get("Content-Disposition") ?? "")
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = match?.[1] ?? fallbackName
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Friendly text for errors shown in the UI. */
export function errorText(err: unknown, fallback = "Something went wrong"): string {
  if (err instanceof ApiError) {
    if (err.status === 403 && !err.message) return "Access denied."
    return err.message
  }
  if (err instanceof TypeError) return "Cannot reach the server. Check your connection."
  return err instanceof Error ? err.message : fallback
}
