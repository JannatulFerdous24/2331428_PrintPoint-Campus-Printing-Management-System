import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { adminApi } from "../api/admin"
import { errorText } from "../api/client"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { StatusBadge } from "../components/StatusBadge"
import type { AdminGroupDetail, RequestStatus } from "../types"

const when = (s?: string | null) => (s ? new Date(s).toLocaleString() : "—")
const yes = (v: boolean) => (v ? "✅" : "❌")

/** Admin moderation view of one group (read-only + delete). Viewing does not make the admin a member. */
export function AdminGroupDetailPage() {
  const { groupId } = useParams()
  const id = Number(groupId)
  const navigate = useNavigate()
  const [g, setG] = useState<AdminGroupDetail | null>(null)
  const [error, setError] = useState("")
  const [confirm, setConfirm] = useState(false)

  useEffect(() => {
    adminApi.group(id).then(setG).catch((err) => setError(errorText(err, "Could not load this group")))
  }, [id])

  async function remove() {
    setConfirm(false)
    try {
      await adminApi.deleteGroup(id)
      navigate("/admin/groups")
    } catch (err) {
      setError(errorText(err))
    }
  }

  if (!g) {
    return (
      <div className="page">
        <Link to="/admin/groups">← All groups</Link>
        {error ? <div className="alert alert-error spaced" role="alert">{error}</div> : <div className="loading">Loading group…</div>}
      </div>
    )
  }

  return (
    <div className="page">
      <Link to="/admin/groups">← All groups</Link>
      <h1 className="page-title">{g.name} <span className="muted">#{g.id}</span></h1>
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {g.description && <p>{g.description}</p>}
      <p className="muted">
        Owner: {g.owner ? <Link to={`/admin/users/${g.owner.id}`}>{g.owner.full_name} ({g.owner.email})</Link> : "—"}
        {" · "}Created {when(g.created_at)} · Updated {when(g.updated_at)}
      </p>
      <button className="btn btn-danger" onClick={() => setConfirm(true)}>Delete group</button>

      <h2 className="spaced">Members ({g.members.length})</h2>
      {g.members.length === 0 ? <p className="empty-state">No members.</p> : (
        <div className="table-wrapper"><table>
          <thead><tr><th>Member</th><th>Role</th><th>Create</th><th>Edit</th><th>Assign</th><th>Joined</th></tr></thead>
          <tbody>{g.members.map((m) => (
            <tr key={m.user_id}>
              <td><Link to={`/admin/users/${m.user_id}`}>{m.full_name}</Link><br /><span className="muted">{m.email}</span></td>
              <td>{m.is_owner ? "Owner" : "Member"}</td>
              <td>{yes(m.is_owner || m.can_create)}</td><td>{yes(m.is_owner || m.can_edit)}</td><td>{yes(m.is_owner || m.can_assign)}</td>
              <td>{when(m.joined_at)}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}

      <h2 className="spaced">Print requests ({g.request_count})</h2>
      {g.requests.length === 0 ? <p className="empty-state">No print requests in this group.</p> : (
        <div className="table-wrapper"><table>
          <thead><tr><th>#ID</th><th>Document</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>{g.requests.map((r) => (
            <tr key={r.id}><td>#{r.id}</td><td className="doc-name">{r.document_name}</td>
              <td><StatusBadge status={r.status as RequestStatus} /></td><td>{when(r.created_at)}</td></tr>
          ))}</tbody>
        </table></div>
      )}

      {confirm && (
        <ConfirmDialog
          message={`Delete group "${g.name}"? Its ${g.request_count} print request(s) are kept (detached from the group). This is recorded in the audit log.`}
          onCancel={() => setConfirm(false)}
          onConfirm={remove} />
      )}
    </div>
  )
}
