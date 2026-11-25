import { type FormEvent, useCallback, useEffect, useState } from "react"
import { adminApi } from "../api/admin"
import { errorText } from "../api/client"
import { printRequestsApi } from "../api/printRequests"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { Pagination } from "../components/Pagination"
import { StatusBadge } from "../components/StatusBadge"
import { REQUEST_STATUSES, type AdminGroup, type BulkResult, type PrintRequest } from "../types"

const LIMIT = 20
type Tab = "requests" | "groups"

/** Content moderation: list/search all print requests and groups, delete one or many (audited). */
export function AdminModerationPage() {
  const [tab, setTab] = useState<Tab>("requests")
  const [q, setQ] = useState("")
  const [status, setStatus] = useState("")
  const [applied, setApplied] = useState({ q: "", status: "" })
  const [skip, setSkip] = useState(0)
  const [requests, setRequests] = useState<PrintRequest[]>([])
  const [groups, setGroups] = useState<AdminGroup[]>([])
  const [total, setTotal] = useState(0)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [confirm, setConfirm] = useState<number[] | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      if (tab === "requests") {
        const page = await printRequestsApi.query({ q: applied.q, status: applied.status as PrintRequest["status"] | "", skip, limit: LIMIT })
        setRequests(page.items)
        setTotal(page.total)
      } else {
        const page = await adminApi.groups({ q: applied.q, skip, limit: LIMIT })
        setGroups(page.items)
        setTotal(page.total)
      }
    } catch (err) {
      setError(errorText(err, "Could not load content"))
    } finally {
      setLoading(false)
    }
  }, [tab, applied, skip])

  useEffect(() => {
    load()
  }, [load])

  function switchTab(t: Tab) {
    setTab(t)
    setSkip(0)
    setSelected(new Set())
    setQ("")
    setStatus("")
    setApplied({ q: "", status: "" })
  }

  function search(e: FormEvent) {
    e.preventDefault()
    setSkip(0)
    setSelected(new Set())
    setApplied({ q, status })
  }

  async function remove(ids: number[]) {
    setError("")
    setMessage("")
    try {
      const r: BulkResult = tab === "requests" ? await adminApi.bulkDeleteRequests(ids) : await adminApi.bulkDeleteGroups(ids)
      setMessage(`Deleted ${r.done.length} ${tab === "requests" ? "request(s)" : "group(s)"}.` +
        (r.skipped.length ? ` Skipped ${r.skipped.length} (not found).` : ""))
      setSelected(new Set())
      await load()
    } catch (err) {
      setError(errorText(err))
    }
  }

  function toggle(id: number) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const ids = tab === "requests" ? requests.map((r) => r.id) : groups.map((g) => g.id)
  const allOnPage = ids.length > 0 && ids.every((i) => selected.has(i))
  const headCheck = (
    <th><input type="checkbox" aria-label="Select all on this page" checked={allOnPage}
      onChange={() => setSelected(allOnPage ? new Set() : new Set(ids))} /></th>
  )
  const rowCheck = (id: number) => (
    <td><input type="checkbox" aria-label={`Select #${id}`} checked={selected.has(id)} onChange={() => toggle(id)} /></td>
  )

  return (
    <div className="page">
      <h1 className="page-title">Content moderation</h1>
      <p className="muted">Deleting here is a privileged admin action and is recorded in the audit log.</p>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "requests"} className={`tab ${tab === "requests" ? "tab-active" : ""}`} onClick={() => switchTab("requests")}>Print requests</button>
        <button role="tab" aria-selected={tab === "groups"} className={`tab ${tab === "groups" ? "tab-active" : ""}`} onClick={() => switchTab("groups")}>Groups</button>
      </div>

      <form className="filters" onSubmit={search}>
        <input placeholder={tab === "requests" ? "Search: #ID, student, document, email" : "Search: name, description, owner email"}
          value={q} onChange={(e) => setQ(e.target.value)} maxLength={100} />
        {tab === "requests" && (
          <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option>
            {REQUEST_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
        <button className="btn btn-primary">Search</button>
        {tab === "requests" && (
          <button type="button" className="btn btn-secondary"
            onClick={() => adminApi.exportCsv("print-requests", { ...applied }).catch((err) => setError(errorText(err)))}>
            Export CSV
          </button>
        )}
      </form>

      {selected.size > 0 && (
        <div className="bulk-bar">
          <span>{selected.size} selected</span>
          <button className="btn btn-sm btn-danger" onClick={() => setConfirm([...selected])}>Delete selected</button>
          <button className="btn btn-sm btn-secondary" onClick={() => setSelected(new Set())}>Clear</button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading…</div>
      ) : ids.length === 0 ? (
        <p className="empty-state">Nothing found.</p>
      ) : tab === "requests" ? (
        <div className="table-wrapper"><table>
          <thead><tr>{headCheck}<th>#ID</th><th>Student</th><th>Document</th><th>Status</th><th>Created</th><th></th></tr></thead>
          <tbody>{requests.map((r) => (
            <tr key={r.id}>{rowCheck(r.id)}<td>#{r.id}</td><td>{r.student_name}</td><td className="doc-name">{r.document_name}</td>
              <td><StatusBadge status={r.status} /></td><td>{new Date(r.created_at).toLocaleDateString()}</td>
              <td><button className="btn btn-sm btn-danger" onClick={() => setConfirm([r.id])}>Delete</button></td></tr>
          ))}</tbody>
        </table></div>
      ) : (
        <div className="table-wrapper"><table>
          <thead><tr>{headCheck}<th>#ID</th><th>Name</th><th>Owner</th><th>Members</th><th>Requests</th><th>Created</th><th></th></tr></thead>
          <tbody>{groups.map((g) => (
            <tr key={g.id}>{rowCheck(g.id)}<td>#{g.id}</td><td>{g.name}</td><td>{g.owner_email}</td><td>{g.member_count}</td>
              <td>{g.request_count}</td><td>{new Date(g.created_at).toLocaleDateString()}</td>
              <td><button className="btn btn-sm btn-danger" onClick={() => setConfirm([g.id])}>Delete</button></td></tr>
          ))}</tbody>
        </table></div>
      )}
      <Pagination skip={skip} limit={LIMIT} total={total} onChange={(s) => { setSkip(s); setSelected(new Set()) }} />

      {confirm && (
        <ConfirmDialog
          message={tab === "requests"
            ? `Permanently delete ${confirm.length} print request(s) and their documents? This cannot be undone.`
            : `Delete ${confirm.length} group(s)? Their print requests are kept (detached from the group).`}
          onCancel={() => setConfirm(null)}
          onConfirm={() => { const c = confirm; setConfirm(null); remove(c) }} />
      )}
    </div>
  )
}
