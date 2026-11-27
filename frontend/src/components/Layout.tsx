import { useState } from "react"
import { NavLink, Outlet, useNavigate } from "react-router-dom"
import { useAuth } from "../auth/AuthContext"
import { ROLE_LABELS } from "../types"
import { ThemeToggle } from "./ThemeToggle"

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [loggingOut, setLoggingOut] = useState(false)

  async function handleLogout() {
    setLoggingOut(true)
    await logout()
    navigate("/login", { replace: true })
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/requests" className="topbar-brand">🖨️ PrintPoint</NavLink>
          <nav className="topbar-nav" aria-label="Main">
            {user?.role === "admin" && (
              <>
                <NavLink to="/admin" end>Dashboard</NavLink>
                <NavLink to="/staff/queue">Staff Queue</NavLink>
              </>
            )}
            <NavLink to="/requests">{user?.role === "admin" ? "All Requests" : "My Requests"}</NavLink>
            <NavLink to="/groups">{user?.role === "admin" ? "My Groups" : "Groups"}</NavLink>
            {user?.role === "admin" && (
              <>
                <NavLink to="/admin/users">Users</NavLink>
                <NavLink to="/admin/groups">All Groups</NavLink>
                <NavLink to="/admin/moderation">Moderation</NavLink>
                <NavLink to="/admin/audit">Audit Log</NavLink>
              </>
            )}
            <NavLink to="/profile">Profile</NavLink>
            <NavLink to="/sessions">Sessions</NavLink>
          </nav>
          <div className="topbar-user">
            <ThemeToggle />
            {user && (
              <span className="topbar-name" title={user.email}>
                {user.full_name} <span className="role-chip">{ROLE_LABELS[user.role]}</span>
              </span>
            )}
            <button className="btn btn-secondary btn-sm" onClick={handleLogout} disabled={loggingOut}>
              {loggingOut ? "Logging out…" : "Log out"}
            </button>
          </div>
        </div>
      </header>
      <Outlet />
    </>
  )
}
