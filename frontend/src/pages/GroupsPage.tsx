import { type FormEvent, useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { errorText } from "../api/client"
import { groupsApi } from "../api/groups"
import type { GroupSummary } from "../types"

function roleInGroup(g: GroupSummary): string {
  const p = g.my_permissions
  if (p.is_owner) return "Owner"
  const flags = [p.can_create && "create", p.can_edit && "edit", p.can_assign && "assign"].filter(Boolean)
  return flags.length ? `Member (${flags.join(", ")})` : "Member (view only)"
}

export function GroupsPage() {
  const [groups, setGroups] = useState<GroupSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      setGroups(await groupsApi.list())
    } catch (err) {
      setError(errorText(err, "Could not load groups"))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function create(e: FormEvent) {
    e.preventDefault()
    setCreating(true)
    setError("")
    try {
      await groupsApi.create(name.trim(), description.trim())
      setName("")
      setDescription("")
      await load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">Groups</h1>
      <p className="muted">
        Share print requests with a class, club or student team. The owner decides who may create, edit or
        assign requests in the group.
      </p>
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      <form className="form-card inline-form" onSubmit={create}>
        <h2>Create a group</h2>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="gname">Name *</label>
            <input id="gname" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)}
              placeholder="e.g. CSE309 Section 5 Team" />
          </div>
          <div className="form-group">
            <label htmlFor="gdesc">Description</label>
            <input id="gdesc" maxLength={500} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
        </div>
        <div className="form-actions">
          <button className="btn btn-primary" disabled={creating || !name.trim()}>
            {creating ? "Creating…" : "Create group"}
          </button>
        </div>
      </form>

      <h2 className="spaced">My groups</h2>
      {loading ? (
        <div className="loading">Loading groups…</div>
      ) : groups.length === 0 ? (
        <p className="empty-state">You are not in any group yet.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr><th>Name</th><th>Owner</th><th>Members</th><th>My role</th><th></th></tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr key={g.id}>
                  <td>{g.name}</td>
                  <td>{g.owner_name}</td>
                  <td>{g.member_count}</td>
                  <td>{roleInGroup(g)}</td>
                  <td><Link className="btn btn-sm btn-info" to={`/groups/${g.id}`}>Open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
