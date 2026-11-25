import { type FormEvent, useState } from "react"
import { errorText } from "../api/client"
import { printRequestsApi } from "../api/printRequests"
import { MIN_REJECTION_REASON, VALID_TRANSITIONS, type PrintRequest, type RequestStatus } from "../types"

const LABELS: Record<RequestStatus, string> = {
  Pending: "Pending",
  Processing: "Accept (start processing)",
  Ready: "Mark Ready",
  Collected: "Mark Collected",
  Rejected: "Reject…",
}

interface Props {
  request: PrintRequest
  onChanged: (updated: PrintRequest) => void
}

/** Staff-only status buttons. Only the allowed next steps are shown; the server enforces them too. */
export function StaffActions({ request, onChanged }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState("")
  const next = VALID_TRANSITIONS[request.status]

  async function move(status: RequestStatus, why?: string) {
    setBusy(true)
    setError("")
    try {
      onChanged(await printRequestsApi.update(request.id, { status, ...(why ? { reason: why } : {}) }))
      setRejecting(false)
      setReason("")
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  function submitReject(e: FormEvent) {
    e.preventDefault()
    if (reason.trim().length < MIN_REJECTION_REASON) {
      setError(`Please give a reason of at least ${MIN_REJECTION_REASON} characters`)
      return
    }
    move("Rejected", reason.trim())
  }

  if (next.length === 0) return <p className="muted spaced">This request is {request.status}; no further status changes.</p>

  return (
    <div className="spaced">
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      <div className="action-btns">
        {next.map((s) => (
          <button key={s} disabled={busy}
            className={`btn btn-sm ${s === "Rejected" ? "btn-danger" : "btn-primary"}`}
            onClick={() => (s === "Rejected" ? setRejecting(true) : move(s))}>
            {LABELS[s]}
          </button>
        ))}
      </div>
      {!request.has_document && request.status === "Pending" && (
        <p className="hint">⚠ No document uploaded for this request.</p>
      )}

      {rejecting && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="reject-title">
          <form className="modal" onSubmit={submitReject}>
            <h3 id="reject-title">Reject request #{request.id}</h3>
            <label htmlFor="reject-reason">Reason (shown to the student) *</label>
            <textarea id="reject-reason" rows={3} maxLength={500} required autoFocus value={reason}
              onChange={(e) => setReason(e.target.value)} placeholder="e.g. The document is password-protected" />
            {error && <div className="alert alert-error" role="alert">{error}</div>}
            <div className="form-actions">
              <button type="button" className="btn btn-secondary" onClick={() => { setRejecting(false); setError("") }}>
                Cancel
              </button>
              <button type="submit" className="btn btn-danger" disabled={busy}>
                {busy ? "Rejecting…" : "Reject request"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
