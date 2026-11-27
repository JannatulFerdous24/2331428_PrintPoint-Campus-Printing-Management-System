import { type FormEvent, useEffect, useState } from "react"
import { printRequestsApi } from "../api/printRequests"
import type { CreatePrintRequestData, GroupSummary, Pricing, PrintRequest, RequestStatus, UpdatePrintRequestData } from "../types"
import {
  ALLOWED_EXTENSIONS, MAX_PAGES, MAX_UPLOAD_BYTES, MIN_REJECTION_REASON, PRINT_TYPES, VALID_TRANSITIONS, formatTaka,
} from "../types"

interface Props {
  initial?: Partial<PrintRequest>
  /** file = the chosen PDF/DOCX (null if none); the page uploads it after saving. */
  onSubmit: (data: CreatePrintRequestData | UpdatePrintRequestData, file: File | null) => Promise<void>
  /** New requests must include a document (approved decision B). */
  requireFile?: boolean
  onCancel: () => void
  isEdit?: boolean
  submitLabel?: string
  /** From the server's `permissions` (rbac.py). The server re-checks everything. */
  canEditFields?: boolean
  canChangeStatus?: boolean
  /** Groups the user may create requests in (can_create). */
  groups?: GroupSummary[]
  defaultName?: string
}

export function PrintRequestForm({
  initial,
  onSubmit,
  onCancel,
  isEdit = false,
  submitLabel = "Submit",
  canEditFields = true,
  canChangeStatus = false,
  groups = [],
  defaultName = "",
  requireFile = false,
}: Props) {
  const [studentName, setStudentName] = useState(initial?.student_name ?? defaultName)
  const [documentName, setDocumentName] = useState(initial?.document_name ?? "")
  const [copies, setCopies] = useState(String(initial?.copies ?? "1"))
  const [pages, setPages] = useState(String(initial?.pages ?? "1"))
  const [pricing, setPricing] = useState<Pricing | null>(null)
  const [printType, setPrintType] = useState(initial?.print_type ?? "Black & White")
  const [status, setStatus] = useState<RequestStatus>(initial?.status ?? "Pending")
  const [notes, setNotes] = useState(initial?.notes ?? "")
  const [reason, setReason] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [groupId, setGroupId] = useState<string>("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const currentStatus: RequestStatus = initial?.status ?? "Pending"
  const statusOptions: RequestStatus[] = [currentStatus, ...VALID_TRANSITIONS[currentStatus]]
  const fieldsLocked = isEdit && !canEditFields
  const statusChanging = isEdit && canChangeStatus && status !== currentStatus
  const rejecting = statusChanging && status === "Rejected"

  useEffect(() => {
    printRequestsApi.pricing().then(setPricing).catch(() => setPricing(null))
  }, [])

  // Estimate only - the server calculates and stores the real amount.
  const pagesNum = parseInt(pages, 10)
  const copiesNumber = parseInt(copies, 10)
  const rate = pricing?.rates_per_page[printType]
  const estimate =
    rate !== undefined && pagesNum >= 1 && pagesNum <= MAX_PAGES && copiesNumber >= 1 && copiesNumber <= 999
      ? pagesNum * copiesNumber * rate
      : null

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError("")
    const copiesNum = parseInt(copies, 10)
    if (!fieldsLocked && (isNaN(copiesNum) || copiesNum < 1 || copiesNum > 999)) {
      setError("Copies must be between 1 and 999")
      return
    }
    if (!fieldsLocked && (isNaN(pagesNum) || pagesNum < 1 || pagesNum > MAX_PAGES)) {
      setError(`Pages must be between 1 and ${MAX_PAGES}`)
      return
    }
    if (requireFile && !file) {
      setError("Please choose the PDF or DOCX document to print")
      return
    }
    if (rejecting && reason.trim().length < MIN_REJECTION_REASON) {
      setError(`Please give a reason of at least ${MIN_REJECTION_REASON} characters for rejecting this request`)
      return
    }
    setLoading(true)
    try {
      const fields = fieldsLocked
        ? {}
        : {
            student_name: studentName.trim(),
            document_name: documentName.trim(),
            copies: copiesNum,
            pages: pagesNum,
            print_type: printType,
            ...(notes.trim() ? { notes: notes.trim() } : {}),
          }
      const data: CreatePrintRequestData | UpdatePrintRequestData = {
        ...fields,
        ...(statusChanging ? { status } : {}),
        ...(statusChanging && reason.trim() ? { reason: reason.trim() } : {}),
        ...(!isEdit && groupId ? { group_id: Number(groupId) } : {}),
      } as CreatePrintRequestData | UpdatePrintRequestData
      await onSubmit(data, fieldsLocked ? null : file)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong")
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="form-card">
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {fieldsLocked && (
        <p className="muted">
          {currentStatus === "Pending" && initial?.payment_status !== "Paid"
            ? "You can view this request but not edit its details."
            : initial?.payment_status === "Paid"
              ? "This request has been paid, so its details are locked."
              : "This request is no longer Pending, so its details are locked."}
        </p>
      )}

      <fieldset disabled={fieldsLocked} className="plain-fieldset">
        <div className="form-group">
          <label>Student Name *</label>
          <input
            value={studentName}
            onChange={(e) => setStudentName(e.target.value)}
            placeholder="e.g. Jannatul Ferdous"
            required
            minLength={1}
            maxLength={200}
          />
        </div>

        <div className="form-group">
          <label htmlFor="document-file">
            {requireFile ? "Document file (PDF or DOCX, max 4 MB) *" : "Replace document file (optional, PDF or DOCX, max 4 MB)"}
          </label>
          {isEdit && initial?.original_filename && (
            <p className="hint">Current file: {initial.original_filename}</p>
          )}
          <input id="document-file" type="file" accept={ALLOWED_EXTENSIONS.join(",")} required={requireFile}
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null
              setError("")
              if (f) {
                const ext = f.name.includes(".") ? f.name.slice(f.name.lastIndexOf(".")).toLowerCase() : ""
                if (!ALLOWED_EXTENSIONS.includes(ext)) {
                  setError("Only PDF (.pdf) and Word (.docx) files are accepted")
                  e.target.value = ""
                  setFile(null)
                  return
                }
                if (f.size > MAX_UPLOAD_BYTES) {
                  setError("The file is larger than 4 MB")
                  e.target.value = ""
                  setFile(null)
                  return
                }
                if (!documentName.trim()) setDocumentName(f.name.replace(/\.[^.]+$/, ""))
              }
              setFile(f)
            }} />
        </div>

        <div className="form-group">
          <label>Document Name *</label>
          <input
            value={documentName}
            onChange={(e) => setDocumentName(e.target.value)}
            placeholder="e.g. Assignment_1.pdf"
            required
            minLength={1}
            maxLength={500}
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="pages">Pages in document *</label>
            <input
              id="pages"
              type="number"
              value={pages}
              onChange={(e) => setPages(e.target.value)}
              min="1"
              max={MAX_PAGES}
              required
            />
          </div>

          <div className="form-group">
            <label>Copies *</label>
            <input
              type="number"
              value={copies}
              onChange={(e) => setCopies(e.target.value)}
              min="1"
              max="999"
              required
            />
          </div>

          <div className="form-group">
            <label>Print Type *</label>
            <select value={printType} onChange={(e) => setPrintType(e.target.value as typeof printType)}>
              {PRINT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="cost-estimate" aria-live="polite">
          {estimate !== null && rate !== undefined ? (
            <>
              <span>Estimated cost</span>
              <strong>{formatTaka(estimate)}</strong>
              <small>
                {pagesNum} page{pagesNum === 1 ? "" : "s"} × {copiesNumber} cop{copiesNumber === 1 ? "y" : "ies"} ×{" "}
                {formatTaka(rate)} ({printType}) · pay at the counter
              </small>
            </>
          ) : (
            <span className="muted">{pricing ? "Enter pages and copies to see the cost" : "Loading prices…"}</span>
          )}
        </div>

        {!isEdit && groups.length > 0 && (
          <div className="form-group">
            <label>Group (optional)</label>
            <select value={groupId} onChange={(e) => setGroupId(e.target.value)}>
              <option value="">Personal request</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="form-group">
          <label>Notes (optional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Any special instructions..."
            rows={3}
            maxLength={1000}
          />
        </div>
      </fieldset>

      {isEdit && canChangeStatus && (
        <div className="form-group">
          <label>Status (staff only)</label>
          <select value={status} onChange={(e) => setStatus(e.target.value as RequestStatus)}>
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s === currentStatus ? `${s} (current)` : s}
              </option>
            ))}
          </select>
          {VALID_TRANSITIONS[currentStatus].length === 0 && (
            <p className="muted">This request is {currentStatus}; its status can no longer change.</p>
          )}
        </div>
      )}

      {statusChanging && (
        <div className="form-group">
          <label htmlFor="status-reason">
            {rejecting ? "Reason for rejection * (shown to the student)" : "Note for the student (optional)"}
          </label>
          <textarea
            id="status-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={rejecting ? "e.g. The document is password-protected" : "e.g. Printing on the colour printer"}
            rows={2}
            maxLength={500}
            required={rejecting}
            minLength={rejecting ? MIN_REJECTION_REASON : undefined}
          />
        </div>
      )}

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={loading || (fieldsLocked && !canChangeStatus)}>
          {loading ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  )
}
