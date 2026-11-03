import type { RequestStatus } from "../types"

const STATUS_COLORS: Record<RequestStatus, string> = {
  Pending: "#f59e0b",
  Processing: "#3b82f6",
  Ready: "#10b981",
  Collected: "#6b7280",
  Rejected: "#ef4444",
}

interface Props {
  status: RequestStatus
}

export function StatusBadge({ status }: Props) {
  return (
    <span
      style={{
        backgroundColor: STATUS_COLORS[status],
        color: "#fff",
        padding: "2px 10px",
        borderRadius: "12px",
        fontSize: "12px",
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {status}
    </span>
  )
}
