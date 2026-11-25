import { useEffect, useState } from "react"
import { groupsApi } from "../api/groups"
import { errorText } from "../api/client"
import { printRequestsApi } from "../api/printRequests"
import { useAuth } from "../auth/AuthContext"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { PrintRequestForm } from "../components/PrintRequestForm"
import { PrintRequestTable } from "../components/PrintRequestTable"
import { RequestDetails } from "../components/RequestDetails"
import type { CreatePrintRequestData, GroupSummary, PrintRequest, UpdatePrintRequestData } from "../types"

type View = "list" | "create" | "edit" | "detail"

export function PrintRequestsPage() {
  const { user } = useAuth()
  const isStaff = user?.role === "admin"
  const [groups, setGroups] = useState<GroupSummary[]>([])
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
    // Groups where I may create requests (for the optional group selector).
    groupsApi.list().then((gs) => setGroups(gs.filter((g) => g.my_permissions.can_create))).catch(() => setGroups([]))
  }, [])

  function showSuccess(msg: string) {
    setSuccess(msg)
    setTimeout(() => setSuccess(""), 4000)
  }

  /** Saves the request, then uploads the chosen file. If only the upload fails the request
   *  still exists (Pending), so the student can open it and upload again. */
  async function uploadAfterSave(id: number, file: File | null): Promise<boolean> {
    if (!file) return true
    try {
      await printRequestsApi.uploadDocument(id, file)
      return true
    } catch (err) {
      setError(`Request #${id} was saved, but the document upload failed: ${errorText(err)} Open the request and upload it again.`)
      return false
    }
  }

  async function handleCreate(data: CreatePrintRequestData | UpdatePrintRequestData, file: File | null) {
    const created = await printRequestsApi.create(data as CreatePrintRequestData)
    const uploaded = await uploadAfterSave(created.id, file)
    if (uploaded) showSuccess(`Print request #${created.id} submitted successfully!`)
    setView("list")
    loadRequests()
  }

  async function handleUpdate(data: CreatePrintRequestData | UpdatePrintRequestData, file: File | null) {
    if (!selected) return
    if (Object.keys(data).length > 0) await printRequestsApi.update(selected.id, data as UpdatePrintRequestData)
    const uploaded = await uploadAfterSave(selected.id, file)
    if (uploaded) showSuccess("Print request updated successfully!")
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
            <h2>{isStaff ? "All Print Requests (staff view)" : "My Print Requests"}</h2>
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
            submitLabel="Submit Request"
            requireFile
            groups={groups}
            defaultName={user?.full_name ?? ""}
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
            canEditFields={selected.permissions?.edit ?? false}
            canChangeStatus={selected.permissions?.change_status ?? false}
          />
        </>
      )}

      {view === "detail" && selected && (
        <>
          <RequestDetails
            request={selected}
            onChanged={(updated) => {
              setSelected(updated)
              showSuccess(`Request #${updated.id} is now ${updated.status}.`)
              loadRequests()
            }}
          />
          <div className="form-actions" style={{ marginTop: "16px" }}>
            {selected.permissions?.edit && (
              <button className="btn btn-primary" onClick={() => setView("edit")}>Edit</button>
            )}
            {selected.permissions?.delete && (
              <button className="btn btn-danger" onClick={() => {
                setDeleteId(selected.id)
                setView("list")
              }}>
                Delete
              </button>
            )}
          </div>
        </>
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
