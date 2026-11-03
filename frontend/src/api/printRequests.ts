import type { CreatePrintRequestData, PrintRequest, UpdatePrintRequestData } from "../types"

const BASE = "/api/print-requests"

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      message = body.detail ?? JSON.stringify(body)
    } catch {
      message = res.statusText || message
    }
    throw new Error(message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const printRequestsApi = {
  list: (status?: string): Promise<PrintRequest[]> => {
    const url = status ? `${BASE}?status=${encodeURIComponent(status)}` : BASE
    return fetch(url).then((r) => handleResponse<PrintRequest[]>(r))
  },

  get: (id: number): Promise<PrintRequest> =>
    fetch(`${BASE}/${id}`).then((r) => handleResponse<PrintRequest>(r)),

  create: (data: CreatePrintRequestData): Promise<PrintRequest> =>
    fetch(BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => handleResponse<PrintRequest>(r)),

  update: (id: number, data: UpdatePrintRequestData): Promise<PrintRequest> =>
    fetch(`${BASE}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => handleResponse<PrintRequest>(r)),

  delete: (id: number): Promise<void> =>
    fetch(`${BASE}/${id}`, { method: "DELETE" }).then((r) =>
      handleResponse<void>(r)
    ),
}
