import { type FormEvent, useCallback, useEffect, useState } from "react"
import { adminApi } from "../api/admin"
import { errorText } from "../api/client"
import { Pagination } from "../components/Pagination"
import type { AuditLogEntry } from "../types"

const LIMIT = 50
const ACTIONS = [
  ["", "All events"], ["auth.", "All login/logout events"], ["auth.login", "Login"], ["auth.login_failed", "Failed login"],
  ["auth.logout", "Logout"], ["user.password_change", "Password change"], ["user.role_change", "Role change"],
  ["user.ban", "Ban"], ["user.unban", "Unban"], ["user.sessions_revoke", "Sessions revoked by admin"],
  ["request.delete", "Request deleted (owner)"], ["moderation.", "Moderation deletes"], ["request.status_change", "Status change"],
  ["request.document_upload", "Document upload"], ["data.export", "CSV export"],
] as const

interface Filters { action: string; actor: string; ip: string; q: string; date_from: string; date_to: string }
const EMPTY: Filters = { action: "", actor: "", ip: "", q: "", date_from: "", date_to: "" }

export function AdminAuditPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY)
  const [applied, setApplied] = useState<Filters>(EMPTY)
  const [skip, setSkip] = useState(0)
  const [rows, setRows] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [open, setOpen] = useState<number | null>(null)

  // date inputs give "YYYY-MM-DD": include the whole "to" day
  const params = useCallback((f: Filters) => ({
    ...f,
    date_from: f.date_from ? `${f.date_from}T00:00:00` : "",
    date_to: f.date_to ? `${f.date_to}T23:59:59` : "",
  }), [])

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const page = await adminApi.auditLogs({ ...params(applied), skip, limit: LIMIT })
      setRows(page.items)
      setTotal(page.total)
    } catch (err) {
      setError(errorText(err, "Could not load the activity log"))
    } finally {
      setLoading(false)
    }
  }, [applied, skip, params])

  useEffect(() => {
    load()
  }, [load])

  function apply(e: FormEvent) {
    e.preventDefault()
    setSkip(0)
    setApplied({ ...filters })
  }

  const set = (k: keyof Filters) => (e: { target: { value: string } }) => setFilters({ ...filters, [k]: e.target.value })

  return (
    <div className="page">
      <h1 className="page-title">Activity / audit log</h1>
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      <form className="filters" onSubmit={apply}>
        <select aria-label="Event type" value={filters.action} onChange={set("action")}>
          {ACTIONS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
        <input placeholder="User email" value={filters.actor} onChange={set("actor")} maxLength={100} />
        <input placeholder="IP address" value={filters.ip} onChange={set("ip")} maxLength={45} />
        <input placeholder="Search (action, target, IP, browser)" value={filters.q} onChange={set("q")} maxLength={100} />
        <label className="inline-label">From <input type="date" value={filters.date_from} onChange={set("date_from")} /></label>
        <label className="inline-label">To <input type="date" value={filters.date_to} onChange={set("date_to")} /></label>
        <button className="btn btn-primary">Apply</button>
        <button type="button" className="btn btn-secondary"
          onClick={() => adminApi.exportCsv("audit-logs", params(applied)).catch((err) => setError(errorText(err)))}>
          Export CSV
        </button>
      </form>

      {loading ? (
        <div className="loading">Loading activity…</div>
      ) : rows.length === 0 ? (
        <p className="empty-state">No events match these filters.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead><tr><th>Time</th><th>Event</th><th>User</th><th>Target</th><th>IP address</th><th>Browser</th><th></th></tr></thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td>{new Date(a.created_at).toLocaleString()}</td>
                  <td>{a.action}</td>
                  <td>{a.actor_email ?? (typeof a.details?.email === "string" ? `${a.details.email} (not logged in)` : "—")}</td>
                  <td>{a.target_type ? `${a.target_type} #${a.target_id}` : "—"}</td>
                  <td>{a.ip_address ?? "—"}</td>
                  <td className="doc-name" title={a.user_agent ?? ""}>{a.user_agent ? a.user_agent.slice(0, 40) : "—"}</td>
                  <td>
                    {a.details && (
                      <button className="btn btn-sm btn-secondary" onClick={() => setOpen(open === a.id ? null : a.id)}>
                        {open === a.id ? "Hide" : "Details"}
                      </button>
                    )}
                    {open === a.id && <pre className="details-pre">{JSON.stringify(a.details, null, 2)}</pre>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination skip={skip} limit={LIMIT} total={total} onChange={setSkip} />
    </div>
  )
}
