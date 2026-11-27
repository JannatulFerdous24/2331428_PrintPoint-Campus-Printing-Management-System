import { useEffect, useState } from "react"
import { errorText } from "../api/client"
import { printRequestsApi } from "../api/printRequests"
import type { PaymentStatus, PrintRequest, StatusHistoryEntry } from "../types"
import { formatTaka } from "../types"
import { PaymentBadge } from "./PaymentBadge"
import { StaffActions } from "./StaffActions"
import { StatusBadge } from "./StatusBadge"

interface Props {
  request: PrintRequest
  /** Called with the updated request after a staff status change. */
  onChanged?: (updated: PrintRequest) => void
}

export function formatBytes(n?: number | null): string {
  if (!n) return "—"
  return n < 1024 * 1024 ? `${(n / 1024).toFixed(1)} KB` : `${(n / (1024 * 1024)).toFixed(2)} MB`
}

/** Details + document + status timeline. Used by students (their requests) and staff (queue). */
export function RequestDetails({ request: r, onChanged }: Props) {
  const [history, setHistory] = useState<StatusHistoryEntry[] | null>(null)
  const [error, setError] = useState("")
  const [opening, setOpening] = useState(false)
  const [paying, setPaying] = useState(false)

  useEffect(() => {
    let cancelled = false
    printRequestsApi
      .history(r.id)
      .then((h) => !cancelled && setHistory(h))
      .catch((err) => !cancelled && setError(errorText(err, "Could not load the status history")))
    return () => {
      cancelled = true
    }
  }, [r.id, r.status])

  async function openDocument() {
    setOpening(true)
    setError("")
    try {
      // The server checks permission, then returns a link that expires in 60 seconds.
      const link = await printRequestsApi.documentLink(r.id)
      window.open(link.url, "_blank", "noopener,noreferrer")
    } catch (err) {
      setError(errorText(err, "Could not open the document"))
    } finally {
      setOpening(false)
    }
  }

  async function setPayment(next: PaymentStatus) {
    if (!onChanged) return
    setPaying(true)
    setError("")
    try {
      // Staff only - the server answers 403 for anyone without PAYMENT_UPDATE.
      onChanged(await printRequestsApi.setPayment(r.id, next))
    } catch (err) {
      setError(errorText(err, "Could not update the payment"))
    } finally {
      setPaying(false)
    }
  }

  const paid = r.payment_status === "Paid"

  return (
    <div className="detail-card">
      <h2>Request #{r.id}</h2>
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      <table className="detail-table">
        <tbody>
          <tr><td>Student Name</td><td>{r.student_name}</td></tr>
          <tr><td>Document Name</td><td>{r.document_name}</td></tr>
          <tr>
            <td>Document file</td>
            <td>
              {r.has_document ? (
                <>
                  {r.original_filename} ({formatBytes(r.file_size_bytes)}){" "}
                  <button className="btn btn-sm btn-info" onClick={openDocument} disabled={opening}>
                    {opening ? "Opening…" : "Download"}
                  </button>
                </>
              ) : (
                <span className="muted">No document uploaded</span>
              )}
            </td>
          </tr>
          <tr><td>Pages</td><td>{r.pages ?? 1}</td></tr>
          <tr><td>Copies</td><td>{r.copies}</td></tr>
          <tr><td>Print Type</td><td>{r.print_type}</td></tr>
          <tr><td>Total cost</td><td><strong>{formatTaka(r.total_cost ?? 0)}</strong></td></tr>
          <tr>
            <td>Payment</td>
            <td>
              <PaymentBadge status={r.payment_status} />
              {paid && r.paid_at && <span className="muted"> · {new Date(r.paid_at).toLocaleString()}</span>}
              {r.permissions?.update_payment && onChanged && (
                paid ? (
                  <button className="btn btn-sm btn-secondary inline-btn" disabled={paying} onClick={() => setPayment("Pending")}>
                    {paying ? "Saving…" : "Undo paid"}
                  </button>
                ) : (
                  r.status !== "Rejected" && (
                    <button className="btn btn-sm btn-success inline-btn" disabled={paying} onClick={() => setPayment("Paid")}>
                      {paying ? "Saving…" : `Mark as paid (${formatTaka(r.total_cost ?? 0)})`}
                    </button>
                  )
                )
              )}
            </td>
          </tr>
          <tr><td>Status</td><td><StatusBadge status={r.status} /></td></tr>
          {r.status === "Rejected" && (
            <tr><td>Rejection reason</td><td>{r.rejection_reason || "—"}</td></tr>
          )}
          <tr><td>Notes</td><td>{r.notes || "—"}</td></tr>
          <tr><td>Created</td><td>{new Date(r.created_at).toLocaleString()}</td></tr>
          <tr><td>Updated</td><td>{new Date(r.updated_at).toLocaleString()}</td></tr>
        </tbody>
      </table>

      {r.permissions?.change_status && onChanged && <StaffActions request={r} onChanged={onChanged} />}

      <h3 className="spaced">Status history</h3>
      {history === null ? (
        <div className="loading">Loading history…</div>
      ) : (
        <ol className="timeline">
          {history.map((h, i) => (
            <li key={i}>
              <strong>{h.from_status ? `${h.from_status} → ${h.to_status}` : `Created (${h.to_status})`}</strong>
              <span className="muted"> · {new Date(h.changed_at).toLocaleString()} · {h.changed_by_name ?? "system"}</span>
              {h.note && <div className="timeline-note">“{h.note}”</div>}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
