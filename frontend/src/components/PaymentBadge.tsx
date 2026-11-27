import type { PaymentStatus } from "../types"

export function PaymentBadge({ status = "Pending" }: { status?: PaymentStatus }) {
  return <span className={`pay-badge ${status === "Paid" ? "pay-paid" : "pay-pending"}`}>{status === "Paid" ? "Paid" : "Unpaid"}</span>
}
