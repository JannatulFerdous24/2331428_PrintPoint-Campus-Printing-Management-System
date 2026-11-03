export type PrintType = "Black & White" | "Color"

export type RequestStatus = "Pending" | "Processing" | "Ready" | "Collected" | "Rejected"

export const PRINT_TYPES: PrintType[] = ["Black & White", "Color"]

export const REQUEST_STATUSES: RequestStatus[] = [
  "Pending",
  "Processing",
  "Ready",
  "Collected",
  "Rejected",
]

// Valid transitions (frontend validation mirror)
export const VALID_TRANSITIONS: Record<RequestStatus, RequestStatus[]> = {
  Pending: ["Processing", "Rejected"],
  Processing: ["Ready", "Rejected"],
  Ready: ["Collected", "Rejected"],
  Collected: [],
  Rejected: [],
}

export interface PrintRequest {
  id: number
  student_name: string
  document_name: string
  copies: number
  print_type: PrintType
  status: RequestStatus
  notes: string | null
  created_at: string
  updated_at: string
}

export interface CreatePrintRequestData {
  student_name: string
  document_name: string
  copies: number
  print_type: PrintType
  notes?: string
}

export interface UpdatePrintRequestData {
  student_name?: string
  document_name?: string
  copies?: number
  print_type?: PrintType
  status?: RequestStatus
  notes?: string
}
