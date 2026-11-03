import { type FormEvent, useState } from "react"
import type { CreatePrintRequestData, PrintRequest, UpdatePrintRequestData } from "../types"
import { PRINT_TYPES, REQUEST_STATUSES } from "../types"

interface Props {
  initial?: Partial<PrintRequest>
  onSubmit: (data: CreatePrintRequestData | UpdatePrintRequestData) => Promise<void>
  onCancel: () => void
  isEdit?: boolean
  submitLabel?: string
}

export function PrintRequestForm({
  initial,
  onSubmit,
  onCancel,
  isEdit = false,
  submitLabel = "Submit",
}: Props) {
  const [studentName, setStudentName] = useState(initial?.student_name ?? "")
  const [documentName, setDocumentName] = useState(initial?.document_name ?? "")
  const [copies, setCopies] = useState(String(initial?.copies ?? "1"))
  const [printType, setPrintType] = useState(initial?.print_type ?? "Black & White")
  const [status, setStatus] = useState(initial?.status ?? "Pending")
  const [notes, setNotes] = useState(initial?.notes ?? "")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError("")
    const copiesNum = parseInt(copies, 10)
    if (isNaN(copiesNum) || copiesNum < 1 || copiesNum > 999) {
      setError("Copies must be between 1 and 999")
      return
    }
    setLoading(true)
    try {
      const data: CreatePrintRequestData | UpdatePrintRequestData = {
        student_name: studentName.trim(),
        document_name: documentName.trim(),
        copies: copiesNum,
        print_type: printType,
        ...(notes.trim() ? { notes: notes.trim() } : {}),
        ...(isEdit ? { status } : {}),
      }
      await onSubmit(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong")
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="form-card">
      {error && <div className="alert alert-error">{error}</div>}

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
          <select
            value={printType}
            onChange={(e) => setPrintType(e.target.value as typeof printType)}
          >
            {PRINT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isEdit && (
        <div className="form-group">
          <label>Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as typeof status)}
          >
            {REQUEST_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
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

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  )
}
