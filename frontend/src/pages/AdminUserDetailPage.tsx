import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { adminApi } from "../api/admin"
import { errorText } from "../api/client"
import { useAuth } from "../auth/AuthContext"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { StatusBadge } from "../components/StatusBadge"
import { ROLE_LABELS, type AdminUserDetail } from "../types"

const when = (s?: string | null) => (s ? new Date(s).toLocaleString() : "—")

export function AdminUserDetailPage() {
  const { userId } = useParams()
  const id = Number(userId)
  const { user: me } = useAuth()
  const [d, setD] = useState<AdminUserDetail | null>(null)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState<{ text: string; run: () => void } | null>(null)

  const load = useCallback(async () => {
    try {
      setD(await adminApi.user(id))
    } catch (err) {
      setError(errorText(err, "Could not load this user"))
    }
  }, [id])

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
      await load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (!d) {
    return (
      <div className="page">
        <Link to="/admin/users">← All users</Link>
        {error ? <div className="alert alert-error spaced" role="alert">{error}</div> : <div className="loading">Loading user…</div>}
      </div>
    )
  }

  const u = d.user
  const isMe = u.id === me?.id
  const isAdmin = u.role === "admin"

  function ban() {
    const reason = window.prompt(`Reason for banning ${u.email} (at least 3 characters):`)
    if (reason === null) return
    if (reason.trim().length < 3) return setError("A ban reason of at least 3 characters is required")
    act(() => adminApi.ban(u.id, reason.trim()), "User banned and logged out.")
  }

  return (
    <div className="page">
      <Link to="/admin/users">← All users</Link>
      <h1 className="page-title">{u.full_name}{isMe && <span className="badge-current">You</span>}</h1>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      <table className="detail-table">
        <tbody>
          <tr><td>Email</td><td>{u.email}</td></tr>
          <tr><td>Role</td><td>{ROLE_LABELS[u.role]}</td></tr>
          <tr><td>Status</td><td>{u.is_banned ? `Banned (${u.ban_reason ?? "no reason"}) since ${when(u.banned_at)}` : "Active"}</td></tr>
          <tr><td>Failed logins in a row</td><td>{d.failed_login_count}{d.locked_until && new Date(d.locked_until) > new Date() ? ` · locked until ${when(d.locked_until)}` : ""}</td></tr>
          <tr><td>Joined</td><td>{when(u.created_at)}</td></tr>
        </tbody>
      </table>

      <div className="action-btns spaced">
        {u.is_banned ? (
          <button className="btn btn-info" disabled={busy} onClick={() => act(() => adminApi.unban(u.id), "User unbanned.")}>Unban</button>
        ) : (
          <button className="btn btn-danger" disabled={busy || isMe || isAdmin}
            title={isMe ? "You cannot ban yourself" : isAdmin ? "Admins cannot ban other admins" : ""} onClick={ban}>Ban</button>
        )}
        <button className="btn btn-secondary" disabled={busy || isMe} title={isMe ? "You cannot change your own role" : ""}
          onClick={() => setConfirm({ text: `Make ${u.email} ${isAdmin ? "a Student" : "Print-Shop Staff (Admin)"}?`,
            run: () => act(() => adminApi.setRole(u.id, isAdmin ? "user" : "admin"), "Role changed.") })}>
          {isAdmin ? "Make student" : "Make staff/admin"}
        </button>
        <button className="btn btn-secondary" disabled={busy || isMe || d.sessions.length === 0}
          onClick={() => setConfirm({ text: `Log ${u.email} out of all ${d.sessions.length} session(s)?`,
            run: () => act(async () => { const r = await adminApi.revokeSessions(u.id); setMessage(`${r.revoked} session(s) revoked.`) }, "Sessions revoked.") })}>
          Revoke all sessions
        </button>
      </div>

      <h2 className="spaced">Print requests ({d.requests_total})</h2>
      {d.requests.length === 0 ? <p className="empty-state">No print requests.</p> : (
        <div className="table-wrapper"><table>
          <thead><tr><th>#ID</th><th>Document</th><th>Copies</th><th>Type</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>{d.requests.map((r) => (
            <tr key={r.id}><td>#{r.id}</td><td className="doc-name">{r.document_name}</td><td>{r.copies}</td>
              <td>{r.print_type}</td><td><StatusBadge status={r.status} /></td><td>{when(r.created_at)}</td></tr>
          ))}</tbody>
        </table></div>
      )}

      <h2 className="spaced">Groups</h2>
      {d.groups.length === 0 ? <p className="empty-state">Not in any group.</p> : (
        <ul>{d.groups.map((g) => (
          <li key={g.id}><Link to={`/admin/groups/${g.id}`}>{g.name}</Link> — {g.role === "owner" ? "owner" : `member (${[g.can_create && "create", g.can_edit && "edit", g.can_assign && "assign"].filter(Boolean).join(", ") || "view only"})`}</li>
        ))}</ul>
      )}

      <h2 className="spaced">Active sessions ({d.sessions.length})</h2>
      {d.sessions.length === 0 ? <p className="empty-state">No active sessions.</p> : (
        <div className="table-wrapper"><table>
          <thead><tr><th>Browser</th><th>IP address</th><th>Signed in</th><th>Last used</th><th>Expires</th></tr></thead>
          <tbody>{d.sessions.map((s) => (
            <tr key={s.id}><td className="doc-name">{s.user_agent ?? "—"}</td><td>{s.ip_address ?? "—"}</td>
              <td>{when(s.created_at)}</td><td>{when(s.last_used_at)}</td><td>{when(s.expires_at)}</td></tr>
          ))}</tbody>
        </table></div>
      )}

      <h2 className="spaced">Recent activity</h2>
      {d.activity.length === 0 ? <p className="empty-state">No recorded activity.</p> : (
        <div className="table-wrapper"><table>
          <thead><tr><th>Time</th><th>Action</th><th>By</th><th>Target</th><th>IP address</th></tr></thead>
          <tbody>{d.activity.map((a) => (
            <tr key={a.id}><td>{when(a.created_at)}</td><td>{a.action}</td><td>{a.actor_email ?? "—"}</td>
              <td>{a.target_type ? `${a.target_type} #${a.target_id}` : "—"}</td><td>{a.ip_address ?? "—"}</td></tr>
          ))}</tbody>
        </table></div>
      )}

      {confirm && <ConfirmDialog message={confirm.text} onCancel={() => setConfirm(null)}
        onConfirm={() => { const c = confirm; setConfirm(null); c.run() }} />}
    </div>
  )
}
