import { useEffect, useState } from "react"
import { printRequestsApi } from "../api/printRequests"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { PrintRequestForm } from "../components/PrintRequestForm"
import { PrintRequestTable } from "../components/PrintRequestTable"
import type { CreatePrintRequestData, PrintRequest, UpdatePrintRequestData } from "../types"

type View = "list" | "create" | "edit" | "detail"

export function PrintRequestsPage() {
  const [requests, setRequests] = useState<PrintRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")
  const [view, setView] = useState<View>("list")
  const [selected, setSelected] = useState<PrintRequest | null>(null)
  const [deleteId, setDeleteId] = useState<number | null>(null)

  async function loadRequests() {
    setLoading(true)
    setError("")
    try {
      const data = await printRequestsApi.list()
      setRequests(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load requests")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRequests()
  }, [])

  function showSuccess(msg: string) {
    setSuccess(msg)
    setTimeout(() => setSuccess(""), 4000)
  }

  async function handleCreate(data: CreatePrintRequestData | UpdatePrintRequestData) {
    await printRequestsApi.create(data as CreatePrintRequestData)
    showSuccess("Print request created successfully!")
    setView("list")
    loadRequests()
  }

  async function handleUpdate(data: CreatePrintRequestData | UpdatePrintRequestData) {
    if (!selected) return
    await printRequestsApi.update(selected.id, data as UpdatePrintRequestData)
    showSuccess("Print request updated successfully!")
    setView("list")
    setSelected(null)
    loadRequests()
  }

  async function handleViewDetail(id: number) {
    try {
      const req = await printRequestsApi.get(id)
      setSelected(req)
      setView("detail")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load request")
    }
  }

  async function handleEditClick(id: number) {
    try {
      const req = await printRequestsApi.get(id)
      setSelected(req)
      setView("edit")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load request")
    }
  }

  async function handleDeleteConfirm() {
    if (deleteId === null) return
    try {
      await printRequestsApi.delete(deleteId)
      showSuccess("Print request deleted.")
      setDeleteId(null)
      loadRequests()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete")
      setDeleteId(null)
    }
  }

  function goToList() {
    setView("list")
    setSelected(null)
  }

  return (
    <div className="page">
      <header className="page-header">
        <div className="header-brand">
          <h1>🖨️ PrintPoint</h1>
          <span className="subtitle">Campus Printing Management System</span>
        </div>
        {view === "list" && (
          <button className="btn btn-primary" onClick={() => setView("create")}>
            + New Request
          </button>
        )}
        {view !== "list" && (
          <button className="btn btn-secondary" onClick={goToList}>
            ← Back to List
          </button>
        )}
      </header>

      {success && <div className="alert alert-success">{success}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      {view === "list" && (
        <>
          <div className="section-header">
            <h2>Print Requests</h2>
            {!loading && (
              <span className="count-badge">{requests.length} total</span>
            )}
          </div>
          {loading ? (
            <div className="loading">Loading requests…</div>
          ) : (
            <PrintRequestTable
              requests={requests}
              onView={handleViewDetail}
              onEdit={handleEditClick}
              onDelete={(id) => setDeleteId(id)}
            />
          )}
        </>
      )}

      {view === "create" && (
        <>
          <h2>New Print Request</h2>
          <PrintRequestForm
            onSubmit={handleCreate}
            onCancel={goToList}
            submitLabel="Create Request"
          />
        </>
      )}

      {view === "edit" && selected && (
        <>
          <h2>Edit Request #{selected.id}</h2>
          <PrintRequestForm
            initial={selected}
            onSubmit={handleUpdate}
            onCancel={goToList}
            isEdit
            submitLabel="Save Changes"
          />
        </>
      )}

      {view === "detail" && selected && (
        <div className="detail-card">
          <h2>Request #{selected.id}</h2>
          <table className="detail-table">
            <tbody>
              <tr><td>Student Name</td><td>{selected.student_name}</td></tr>
              <tr><td>Document Name</td><td>{selected.document_name}</td></tr>
              <tr><td>Copies</td><td>{selected.copies}</td></tr>
              <tr><td>Print Type</td><td>{selected.print_type}</td></tr>
              <tr>
                <td>Status</td>
                <td>
                  <span style={{
                    backgroundColor: {
                      Pending: "#f59e0b", Processing: "#3b82f6", Ready: "#10b981",
                      Collected: "#6b7280", Rejected: "#ef4444"
                    }[selected.status],
                    color: "#fff", padding: "2px 10px", borderRadius: "12px",
                    fontSize: "12px", fontWeight: 600
                  }}>
                    {selected.status}
                  </span>
                </td>
              </tr>
              <tr><td>Notes</td><td>{selected.notes || "—"}</td></tr>
              <tr><td>Created</td><td>{new Date(selected.created_at).toLocaleString()}</td></tr>
              <tr><td>Updated</td><td>{new Date(selected.updated_at).toLocaleString()}</td></tr>
            </tbody>
          </table>
          <div className="form-actions" style={{ marginTop: "16px" }}>
            <button className="btn btn-primary" onClick={() => {
              setView("edit")
            }}>
              Edit
            </button>
            <button className="btn btn-danger" onClick={() => {
              setDeleteId(selected.id)
              setView("list")
            }}>
              Delete
            </button>
          </div>
        </div>
      )}

      {deleteId !== null && (
        <ConfirmDialog
          message={`Are you sure you want to delete request #${deleteId}? This cannot be undone.`}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteId(null)}
        />
      )}
    </div>
  )
}
