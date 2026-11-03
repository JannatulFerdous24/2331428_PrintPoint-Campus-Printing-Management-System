import type { PrintRequest } from "../types"
import { StatusBadge } from "./StatusBadge"

interface Props {
  requests: PrintRequest[]
  onView: (id: number) => void
  onEdit: (id: number) => void
  onDelete: (id: number) => void
}

export function PrintRequestTable({ requests, onView, onEdit, onDelete }: Props) {
  if (requests.length === 0) {
    return <p className="empty-state">No print requests found.</p>
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>#ID</th>
            <th>Student</th>
            <th>Document</th>
            <th>Copies</th>
            <th>Type</th>
            <th>Status</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((r) => (
            <tr key={r.id}>
              <td>#{r.id}</td>
              <td>{r.student_name}</td>
              <td className="doc-name">{r.document_name}</td>
              <td>{r.copies}</td>
              <td>{r.print_type}</td>
              <td>
                <StatusBadge status={r.status} />
              </td>
              <td>{new Date(r.created_at).toLocaleDateString()}</td>
              <td>
                <div className="action-btns">
                  <button className="btn btn-sm btn-info" onClick={() => onView(r.id)}>
                    View
                  </button>
                  <button className="btn btn-sm btn-primary" onClick={() => onEdit(r.id)}>
                    Edit
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => onDelete(r.id)}>
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
