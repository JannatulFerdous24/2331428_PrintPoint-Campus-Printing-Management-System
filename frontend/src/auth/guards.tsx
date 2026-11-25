/**
 * Route guards. They only decide what the browser SHOWS.
 * Real security is on the server: every protected API call is checked there
 * (token, ban status, session), whatever the frontend does.
 */
import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useAuth } from "./AuthContext"

export function FullPageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="full-loader" role="status" aria-live="polite">
      <div className="spinner" />
      <span>{label}</span>
    </div>
  )
}

/** Only for logged-in users; others go to /login and come back afterwards. */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === "loading") return <FullPageLoader label="Restoring your session…" />
  if (status === "guest") {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}

/** Login/signup pages: a logged-in user is sent straight to the app. */
export function GuestOnly() {
  const { status } = useAuth()
  if (status === "loading") return <FullPageLoader label="Restoring your session…" />
  if (status === "authenticated") return <Navigate to="/requests" replace />
  return <Outlet />
}

/** Admin-only pages. Students see a clear "access denied" message.
 *  (The admin API returns 403 to students anyway - this is only the UI side.) */
export function RequireAdmin() {
  const { user } = useAuth()
  if (user?.role !== "admin") {
    return (
      <div className="page">
        <div className="alert alert-error" role="alert">
          Access denied: this page is only for print-shop staff (admins).
        </div>
      </div>
    )
  }
  return <Outlet />
}
