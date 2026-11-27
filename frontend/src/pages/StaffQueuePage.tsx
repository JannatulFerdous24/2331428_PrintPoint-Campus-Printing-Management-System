import { type FormEvent, useCallback, useEffect, useState } from "react"
import { adminApi } from "../api/admin"
import { errorText } from "../api/client"
import { printRequestsApi } from "../api/printRequests"
import { Pagination } from "../components/Pagination"
import { RequestDetails } from "../components/RequestDetails"
import { PaymentBadge } from "../components/PaymentBadge"
import { StatusBadge } from "../components/StatusBadge"
import { PRINT_TYPES, REQUEST_STATUSES, formatTaka, type PrintRequest, type RequestQuery, type RequestStatus } from "../types"

const LIMIT = 20
const EMPTY: RequestQuery = { q: "", status: "Pending", print_type: "", payment_status: "", has_document: "", created_from: "", created_to: "", sort: "oldest" }

/** Staff (admin) work queue: incoming requests, oldest first, with search and filters. */
export function StaffQueuePage() {
  const [filters, setFilters] = useState<RequestQuery>(EMPTY)
  const [applied, setApplied] = useState<RequestQuery>(EMPTY)
  const [skip, setSkip] = useState(0)
  const [rows, setRows] = useState<PrintRequest[]>([])
  const [total, setTotal] = useState(0)
  const [counts, setCounts] = useState<Record<RequestStatus, number> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [selected, setSelected] = useState<PrintRequest | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const { created_from, created_to, ...rest } = applied
      const page = await printRequestsApi.query({
        ...rest,
        // date inputs give "YYYY-MM-DD": include the whole "to" day
        created_from: created_from ? `${created_from}T00:00:00` : "",
        created_to: created_to ? `${created_to}T23:59:59` : "",
        skip,
        limit: LIMIT,
      })
      setRows(page.items)
      setTotal(page.total)
      adminApi.stats().then((s) => setCounts(s.requests_by_status)).catch(() => setCounts(null))
    } catch (err) {
      setError(errorText(err, "Could not load the queue"))
    } finally {
      setLoading(false)
    }
  }, [applied, skip])

  useEffect(() => {
    load()
  }, [load])

  function apply(e?: FormEvent) {
    e?.preventDefault()
    setSkip(0)
    setApplied({ ...filters })
  }

  function setTab(status: RequestStatus | "") {
    const next = { ...filters, status }
    setFilters(next)
    setSkip(0)
    setApplied(next)
  }

  async function open(id: number) {
    try {
      setSelected(await printRequestsApi.get(id))
    } catch (err) {
      setError(errorText(err))
    }
  }

  const set = (k: keyof RequestQuery) => (e: { target: { value: string } }) => setFilters({ ...filters, [k]: e.target.value })

  if (selected) {
    return (
      <div className="page">
        <button className="btn btn-secondary" onClick={() => { setSelected(null); load() }}>← Back to queue</button>
        {message && <div className="alert alert-success spaced">{message}</div>}
        <RequestDetails request={selected} onChanged={(u) => { setSelected(u); setMessage(`Request #${u.id}: ${u.status}, payment ${u.payment_status === "Paid" ? "Paid" : "Unpaid"}.`) }} />
      </div>
    )
  }

  return (
    <div className="page">
      <h1 className="page-title">Staff queue</h1>
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      <div className="tabs" role="tablist">
        {(["", ...REQUEST_STATUSES] as (RequestStatus | "")[]).map((s) => (
          <button key={s || "all"} role="tab" aria-selected={applied.status === s}
            className={`tab ${applied.status === s ? "tab-active" : ""}`} onClick={() => setTab(s)}>
            {s || "All"}{s && counts ? ` (${counts[s]})` : ""}
          </button>
        ))}
      </div>

      <form className="filters" onSubmit={apply}>
        <input placeholder="Search: #ID, student, document, file or email" value={filters.q} onChange={set("q")} maxLength={100} />
        <select value={filters.print_type} onChange={set("print_type")} aria-label="Print type">
          <option value="">Any print type</option>
          {PRINT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={filters.payment_status} onChange={set("payment_status")} aria-label="Payment">
          <option value="">Paid or unpaid</option>
          <option value="Pending">Unpaid</option>
          <option value="Paid">Paid</option>
        </select>
        <select value={filters.has_document} onChange={set("has_document")} aria-label="Document">
          <option value="">With or without file</option>
          <option value="true">Has document</option>
          <option value="false">No document</option>
        </select>
        <label className="inline-label">From <input type="date" value={filters.created_from} onChange={set("created_from")} /></label>
        <label className="inline-label">To <input type="date" value={filters.created_to} onChange={set("created_to")} /></label>
        <select value={filters.sort} onChange={set("sort")} aria-label="Sort">
          <option value="oldest">Oldest first</option>
          <option value="newest">Newest first</option>
        </select>
        <button className="btn btn-primary">Apply</button>
        <button type="button" className="btn btn-secondary" onClick={() => { setFilters(EMPTY); setSkip(0); setApplied(EMPTY) }}>Reset</button>
      </form>

      {loading ? (
        <div className="loading">Loading queue…</div>
      ) : rows.length === 0 ? (
        <p className="empty-state">No requests match these filters.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr><th>#ID</th><th>Student</th><th>Document</th><th>File</th><th>Copies</th><th>Type</th><th>Cost</th><th>Status</th><th>Submitted</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>#{r.id}</td>
                  <td>{r.student_name}</td>
                  <td className="doc-name">{r.document_name}</td>
                  <td>{r.has_document ? "📄" : <span className="muted">none</span>}</td>
                  <td>{r.copies}</td>
                  <td>{r.print_type}</td>
                  <td className="nowrap">{formatTaka(r.total_cost ?? 0)} <PaymentBadge status={r.payment_status} /></td>
                  <td><StatusBadge status={r.status} /></td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td><button className="btn btn-sm btn-info" onClick={() => open(r.id)}>Open</button></td>
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
