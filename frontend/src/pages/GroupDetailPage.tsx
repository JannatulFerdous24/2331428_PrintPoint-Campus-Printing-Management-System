import { type FormEvent, useCallback, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ApiError, errorText } from "../api/client"
import { groupsApi } from "../api/groups"
import { StatusBadge } from "../components/StatusBadge"
import type { GroupDetail, GroupMemberInfo, MemberFlags, PrintRequest } from "../types"

const FLAG_LABELS: [keyof MemberFlags, string][] = [
  ["can_create", "Create"],
  ["can_edit", "Edit"],
  ["can_assign", "Assign"],
]

export function GroupDetailPage() {
  const { groupId } = useParams()
  const id = Number(groupId)
  const navigate = useNavigate()

  const [group, setGroup] = useState<GroupDetail | null>(null)
  const [requests, setRequests] = useState<PrintRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [denied, setDenied] = useState("")
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const [newName, setNewName] = useState("")
  const [email, setEmail] = useState("")
  const [flags, setFlags] = useState<MemberFlags>({ can_create: true, can_edit: false, can_assign: false })

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const g = await groupsApi.get(id)
      setGroup(g)
      setNewName(g.name)
      setRequests(await groupsApi.requests(id))
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
        setDenied(err.status === 404 ? "This group does not exist or you are not a member." : err.message)
      } else {
        setError(errorText(err, "Could not load the group"))
      }
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  async function run(action: () => Promise<unknown>, success: string) {
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

  if (loading) return <div className="page"><div className="loading">Loading group…</div></div>
  if (denied) {
    return (
      <div className="page">
        <div className="alert alert-error" role="alert">{denied}</div>
        <Link to="/groups" className="btn btn-secondary">Back to groups</Link>
      </div>
    )
  }
  if (!group) return <div className="page"><div className="alert alert-error">{error}</div></div>

  const me = group.my_permissions
  const members = group.members

  function toggle(m: GroupMemberInfo, key: keyof MemberFlags) {
    const next: MemberFlags = { can_create: m.can_create, can_edit: m.can_edit, can_assign: m.can_assign, [key]: !m[key] }
    run(() => groupsApi.updateMember(id, m.user_id, next), `Updated ${m.full_name}'s permissions.`)
  }

  async function addMember(e: FormEvent) {
    e.preventDefault()
    await run(() => groupsApi.addMember(id, email.trim(), flags), `${email.trim()} added to the group.`)
    setEmail("")
  }

  async function deleteGroup() {
    if (!window.confirm(`Delete group "${group?.name}"? Its print requests are kept as personal requests.`)) return
    setBusy(true)
    try {
      await groupsApi.remove(id)
      navigate("/groups", { replace: true })
    } catch (err) {
      setError(errorText(err))
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <div className="section-header section-header-split">
        <h1 className="page-title">{group.name}</h1>
        <Link to="/groups" className="btn btn-secondary btn-sm">← All groups</Link>
      </div>
      <p className="muted">
        Owner: <strong>{group.owner_name}</strong> · {group.member_count} member(s)
        {group.description ? ` · ${group.description}` : ""}
      </p>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      {me.can_manage && (
        <div className="card-grid">
          <form className="form-card" onSubmit={(e) => { e.preventDefault(); run(() => groupsApi.rename(id, newName.trim(), group.description), "Group renamed.") }}>
            <h2>Rename group (owner only)</h2>
            <div className="form-group">
              <input required maxLength={100} value={newName} onChange={(e) => setNewName(e.target.value)} />
            </div>
            <div className="form-actions">
              <button className="btn btn-danger" type="button" onClick={deleteGroup} disabled={busy}>Delete group</button>
              <button className="btn btn-primary" disabled={busy || !newName.trim() || newName.trim() === group.name}>Rename</button>
            </div>
          </form>
          <form className="form-card" onSubmit={addMember}>
            <h2>Add member (owner only)</h2>
            <div className="form-group">
              <label htmlFor="memail">Student email</label>
              <input id="memail" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="flag-row">
              {FLAG_LABELS.map(([key, label]) => (
                <label key={key} className="check">
                  <input type="checkbox" checked={flags[key]} onChange={() => setFlags({ ...flags, [key]: !flags[key] })} />
                  {label}
                </label>
              ))}
            </div>
            <div className="form-actions">
              <button className="btn btn-primary" disabled={busy || !email.trim()}>Add member</button>
            </div>
          </form>
        </div>
      )}

      <h2 className="spaced">Members</h2>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr><th>Name</th><th>Email</th>{FLAG_LABELS.map(([, l]) => <th key={l}>{l}</th>)}<th></th></tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.user_id}>
                <td>{m.full_name}{m.is_owner && <span className="role-chip">Owner</span>}</td>
                <td>{m.email}</td>
                {FLAG_LABELS.map(([key]) => (
                  <td key={key}>
                    {me.can_manage && !m.is_owner ? (
                      <input type="checkbox" checked={m[key]} disabled={busy} onChange={() => toggle(m, key)}
                        aria-label={`${key} for ${m.full_name}`} />
                    ) : m[key] ? "✓" : "—"}
                  </td>
                ))}
                <td>
                  {me.can_manage && !m.is_owner && (
                    <button className="btn btn-danger btn-sm" disabled={busy}
                      onClick={() => run(() => groupsApi.removeMember(id, m.user_id), `${m.full_name} removed.`)}>
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="spaced">Group print requests</h2>
      {requests.length === 0 ? (
        <p className="empty-state">No requests in this group yet.{me.can_create ? " Create one from Print Requests and choose this group." : ""}</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr><th>#</th><th>Document</th><th>Copies</th><th>Status</th><th>Assignee</th></tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id}>
                  <td>#{r.id}</td>
                  <td className="doc-name">{r.document_name}</td>
                  <td>{r.copies}</td>
                  <td><StatusBadge status={r.status} /></td>
                  <td>
                    {r.permissions?.assign ? (
                      <select value={r.assignee_id ?? ""} disabled={busy}
                        onChange={(e) => run(() => groupsApi.setAssignee(r.id, e.target.value ? Number(e.target.value) : null), `Request #${r.id} assignee updated.`)}>
                        <option value="">Unassigned</option>
                        {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name}</option>)}
                      </select>
                    ) : (
                      members.find((m) => m.user_id === r.assignee_id)?.full_name ?? "Unassigned"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
