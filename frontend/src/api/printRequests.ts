import type {
  CreatePrintRequestData,
  DocumentLink,
  PaymentStatus,
  Pricing,
  PrintRequest,
  RequestQuery,
  StatusHistoryEntry,
  UpdatePrintRequestData,
} from "../types"
import { apiFetch, apiPage, queryString } from "./client"

const BASE = "/api/print-requests"

// Same functions as the Mid Project; they now go through apiFetch, which adds the
// login token and handles expired tokens and readable error messages.
export const printRequestsApi = {
  list: (status?: string): Promise<PrintRequest[]> => {
    const url = status ? `${BASE}?status=${encodeURIComponent(status)}` : BASE
    return apiFetch<PrintRequest[]>(url)
  },

  /** Search + filters + paging (staff queue). Students only ever get their own/group requests. */
  query: (params: RequestQuery) => apiPage<PrintRequest>(`${BASE}${queryString({ ...params })}`),

  get: (id: number): Promise<PrintRequest> => apiFetch<PrintRequest>(`${BASE}/${id}`),

  history: (id: number) => apiFetch<StatusHistoryEntry[]>(`${BASE}/${id}/history`),

  create: (data: CreatePrintRequestData): Promise<PrintRequest> =>
    apiFetch<PrintRequest>(BASE, { method: "POST", body: JSON.stringify(data) }),

  update: (id: number, data: UpdatePrintRequestData): Promise<PrintRequest> =>
    apiFetch<PrintRequest>(`${BASE}/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  delete: (id: number): Promise<void> => apiFetch<void>(`${BASE}/${id}`, { method: "DELETE" }),

  /** Upload or replace the PDF/DOCX (multipart; the browser sets the Content-Type). */
  uploadDocument: (id: number, file: File): Promise<PrintRequest> => {
    const form = new FormData()
    form.append("file", file)
    return apiFetch<PrintRequest>(`${BASE}/${id}/document`, { method: "PUT", body: form })
  },

  /** Printing rates used by the server, for the estimate shown before submitting. */
  pricing: () => apiFetch<Pricing>(`${BASE}/pricing`),

  /** Staff only (server returns 403 for students): mark Paid / back to Pending. */
  setPayment: (id: number, payment_status: PaymentStatus): Promise<PrintRequest> =>
    apiFetch<PrintRequest>(`${BASE}/${id}/payment`, { method: "PATCH", body: JSON.stringify({ payment_status }) }),

  /** Short-lived signed link, issued only after the server checks permission. */
  documentLink: (id: number) => apiFetch<DocumentLink>(`${BASE}/${id}/document`),
}
