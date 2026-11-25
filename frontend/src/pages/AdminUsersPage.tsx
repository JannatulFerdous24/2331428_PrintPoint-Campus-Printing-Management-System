import { type FormEvent, useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { adminApi } from "../api/admin"
import { errorText } from "../api/client"
import { useAuth } from "../auth/AuthContext"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { Pagination } from "../components/Pagination"
import { ROLE_LABELS, type AdminUser, type BulkResult } from "../types"

const LIMIT = 20
interface Filters { q: string; role: string; banned: string }
const EMPTY: Filters = { q: "", role: "", banned: "" }

/** Admin-only page. The route is guarded, AND every API call is checked by the
 *  server (403 for students), AND the safety rules are enforced server-side. */
export function AdminUsersPage() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [filters, setFilters] = useState<Filters>(EMPTY)
  const [applied, setApplied] = useState<Filters>(EMPTY)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState<{ text: string; run: () => Promise<void> } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const page = await adminApi.users({ ...applied, skip, limit: LIMIT })
      setUsers(page.items)
      setTotal(page.total)
    } catch (err) {
      setError(errorText(err, "Could not load users"))
    } finally {
      setLoading(false)
    }
  }, [applied, skip])

  useEffect(() => {
    load()
  }, [load])

  async function act(action: () => Promise<unknown>, success: string) {
    setBusy(true)
    setError("")
    setMessage("")
    try {
      await action()
      setMessage(success)
      setSelected(new Set())
      await load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const summary = (verb: string) => (r: BulkResult) =>
    `${r.done.length} user(s) ${verb}.` + (r.skipped.length ? ` Skipped ${r.skipped.length}: ${r.skipped.map((s) => `#${s.id} (${s.reason})`).join(", ")}` : "")

  function askReason(label: string): string | null {
    const reason = window.prompt(`Reason for banning ${label} (at least 3 characters):`)
    if (reason === null) return null
    if (reason.trim().length < 3) {
      setError("A ban reason of at least 3 characters is required")
      return null
    }
    return reason.trim()
  }

  function ban(u: AdminUser) {
    const reason = askReason(u.email)
    if (reason) act(() => adminApi.ban(u.id, reason), `${u.email} banned and logged out.`)
  }

  function bulkBan() {
    const reason = askReason(`${selected.size} selected user(s)`)
    if (!reason) return
    const ids = [...selected]
    setConfirm({
      text: `Ban ${ids.length} user(s)? They will be logged out immediately. Admins and yourself are skipped.`,
      run: async () => {
        let text = ""
        await act(async () => { text = summary("banned")(await adminApi.bulkBan(ids, reason)) }, "")
        setMessage(text)
      },
    })
  }

  async function bulkUnban() {
    const ids = [...selected]
    let text = ""
    await act(async () => { text = summary("unbanned")(await adminApi.bulkUnban(ids)) }, "")
    setMessage(text)
  }

  function search(e: FormEvent) {
    e.preventDefault()
    setSkip(0)
    setApplied({ ...filters })
  }

  function toggle(id: number) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const allOnPage = users.length > 0 && users.every((u) => selected.has(u.id))

  return (
    <div className="page">
      <h1 className="page-title">Users (admin)</h1>
      <p className="muted">Admins cannot change their own role or ban another admin — the server enforces this too.</p>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      <form className="filters" onSubmit={search}>
        <input placeholder="Search by name or email" value={filters.q} maxLength={100}
          onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        <select aria-label="Role" value={filters.role} onChange={(e) => setFilters({ ...filters, role: e.target.value })}>
          <option value="">All roles</option>
          <option value="user">Students</option>
          <option value="admin">Staff / admins</option>
        </select>
        <select aria-label="Account status" value={filters.banned} onChange={(e) => setFilters({ ...filters, banned: e.target.value })}>
          <option value="">Any status</option>
          <option value="false">Active</option>
          <option value="true">Banned</option>
        </select>
        <button className="btn btn-primary">Search</button>
        <button type="button" className="btn btn-secondary" disabled={busy}
          onClick={() => adminApi.exportCsv("users", { ...applied }).catch((err) => setError(errorText(err)))}>
          Export CSV
        </button>
      </form>

      {selected.size > 0 && (
        <div className="bulk-bar">
          <span>{selected.size} selected</span>
          <button className="btn btn-sm btn-danger" disabled={busy} onClick={bulkBan}>Ban selected</button>
          <button className="btn btn-sm btn-info" disabled={busy} onClick={bulkUnban}>Unban selected</button>
          <button className="btn btn-sm btn-secondary" onClick={() => setSelected(new Set())}>Clear</button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading users…</div>
      ) : users.length === 0 ? (
        <p className="empty-state">No users found.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th><input type="checkbox" aria-label="Select all on this page" checked={allOnPage}
                  onChange={() => setSelected(allOnPage ? new Set() : new Set(users.map((u) => u.id)))} /></th>
                <th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isMe = u.id === me?.id
                const isAdmin = u.role === "admin"
                return (
                  <tr key={u.id}>
                    <td><input type="checkbox" aria-label={`Select ${u.email}`} checked={selected.has(u.id)} onChange={() => toggle(u.id)} /></td>
                    <td><Link to={`/admin/users/${u.id}`}>{u.full_name}</Link>{isMe && <span className="badge-current">You</span>}</td>
                    <td>{u.email}</td>
                    <td>{ROLE_LABELS[u.role]}</td>
                    <td>{u.is_banned ? <span title={u.ban_reason ?? ""}>Banned</span> : "Active"}</td>
                    <td>
                      <div className="action-btns">
                        <button className="btn btn-sm btn-secondary" disabled={isMe || busy}
                          title={isMe ? "You cannot change your own role" : ""}
                          onClick={() => setConfirm({
                            text: `Make ${u.email} ${isAdmin ? "a Student" : "Print-Shop Staff (Admin)"}?`,
                            run: () => act(() => adminApi.setRole(u.id, isAdmin ? "user" : "admin"),
                              `${u.email} is now ${isAdmin ? "a Student" : "Print-Shop Staff (Admin)"}.`),
                          })}>
                          {isAdmin ? "Make student" : "Make staff/admin"}
                        </button>
                        {u.is_banned ? (
                          <button className="btn btn-sm btn-info" disabled={busy}
                            onClick={() => act(() => adminApi.unban(u.id), `${u.email} unbanned.`)}>Unban</button>
                        ) : (
                          <button className="btn btn-sm btn-danger" disabled={isMe || isAdmin || busy}
                            title={isMe ? "You cannot ban yourself" : isAdmin ? "Admins cannot ban other admins" : ""}
                            onClick={() => ban(u)}>Ban</button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <Pagination skip={skip} limit={LIMIT} total={total} onChange={setSkip} />

      {confirm && (
        <ConfirmDialog message={confirm.text} onCancel={() => setConfirm(null)}
          onConfirm={() => { const c = confirm; setConfirm(null); c.run() }} />
      )}
    </div>
  )
}
