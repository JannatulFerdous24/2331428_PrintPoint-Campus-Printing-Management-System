import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { adminApi } from "../api/admin"
import { errorText } from "../api/client"
import { REQUEST_STATUSES, type AdminStats, type FailedLogins } from "../types"

/** Admin overview. Every number comes from the database (GET /api/admin/stats) - nothing is made up. */
export function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [security, setSecurity] = useState<FailedLogins | null>(null)
  const [hours, setHours] = useState(24)
  const [error, setError] = useState("")

  useEffect(() => {
    adminApi.stats().then(setStats).catch((err) => setError(errorText(err, "Could not load statistics")))
  }, [])

  useEffect(() => {
    setSecurity(null)
    adminApi.failedLogins(hours).then(setSecurity).catch((err) => setError(errorText(err, "Could not load failed logins")))
  }, [hours])

  const cards: [string, number | undefined, string?][] = [
    ["Total users", stats?.total_users, "/admin/users"],
    ["Banned users", stats?.banned_users, "/admin/users"],
    ["Print requests", stats?.total_requests, "/staff/queue"],
    ["Groups", stats?.total_groups, "/admin/groups"],
    ["New users (7 days)", stats?.new_users_7d],
    ["New requests (7 days)", stats?.new_requests_7d],
    ["Failed logins (24 h)", stats?.failed_logins_24h, "/admin/audit"],
  ]

  return (
    <div className="page">
      <h1 className="page-title">Admin dashboard</h1>
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      {!stats && !error ? (
        <div className="loading">Loading statistics…</div>
      ) : stats && (
        <>
          <div className="stat-grid">
            {cards.map(([label, value, to]) => {
              const body = (<><div className="stat-value">{value ?? "—"}</div><div className="stat-label">{label}</div></>)
              return to ? <Link key={label} to={to} className="stat-card">{body}</Link> : <div key={label} className="stat-card">{body}</div>
            })}
          </div>
          <p className="muted">
            Requests by status:{" "}
            {REQUEST_STATUSES.map((s) => `${s} ${stats.requests_by_status[s]}`).join(" · ")}
          </p>
        </>
      )}

      <div className="section-header section-header-split spaced">
        <h2>Security: failed logins</h2>
        <select value={hours} onChange={(e) => setHours(Number(e.target.value))} aria-label="Time window">
          <option value={24}>Last 24 hours</option>
          <option value={168}>Last 7 days</option>
          <option value={720}>Last 30 days</option>
        </select>
      </div>
      {!security ? (
        <div className="loading">Loading…</div>
      ) : security.total_failed === 0 ? (
        <p className="empty-state">No failed logins in this period.</p>
      ) : (
        <div className="two-col">
          <div className="table-wrapper">
            <h3>By IP address</h3>
            <table>
              <thead><tr><th>IP address</th><th>Failures</th><th>Accounts tried</th><th>Last attempt</th></tr></thead>
              <tbody>
                {security.by_ip.map((r) => (
                  <tr key={r.ip_address ?? "unknown"}>
                    <td>{r.ip_address ?? "unknown"}</td><td>{r.failures}</td><td>{r.accounts_tried}</td>
                    <td>{new Date(r.last_attempt).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-wrapper">
            <h3>By account</h3>
            <table>
              <thead><tr><th>Email tried</th><th>Failures</th><th>Account</th><th>Last attempt</th></tr></thead>
              <tbody>
                {security.by_account.map((r) => (
                  <tr key={r.email}>
                    <td>{r.user_id ? <Link to={`/admin/users/${r.user_id}`}>{r.email}</Link> : r.email}</td>
                    <td>{r.failures}</td>
                    <td>{!r.known_account ? "No such account" : r.locked_until && new Date(r.locked_until) > new Date() ? "Locked" : "Exists"}</td>
                    <td>{new Date(r.last_attempt).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
