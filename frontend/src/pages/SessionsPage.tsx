import { useCallback, useEffect, useState } from "react"
import { authApi } from "../api/auth"
import { errorText } from "../api/client"
import type { SessionInfo } from "../types"

/** Very small user-agent summary, e.g. "Chrome on Windows". */
function describeDevice(ua: string | null): string {
  if (!ua) return "Unknown device"
  const browser = /Edg\//.test(ua) ? "Edge"
    : /Chrome\//.test(ua) ? "Chrome"
    : /Firefox\//.test(ua) ? "Firefox"
    : /Safari\//.test(ua) ? "Safari"
    : "Browser"
  const os = /Windows/.test(ua) ? "Windows"
    : /Android/.test(ua) ? "Android"
    : /iPhone|iPad/.test(ua) ? "iOS"
    : /Mac OS X/.test(ua) ? "macOS"
    : /Linux/.test(ua) ? "Linux"
    : "unknown OS"
  return `${browser} on ${os}`
}

export function SessionsPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [busyId, setBusyId] = useState<number | "others" | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      setSessions(await authApi.sessions())
    } catch (err) {
      setError(errorText(err, "Could not load sessions"))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function revoke(id: number) {
    setBusyId(id)
    setMessage("")
    setError("")
    try {
      await authApi.revokeSession(id)
      setMessage("That device has been logged out.")
      await load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusyId(null)
    }
  }

  async function revokeOthers() {
    setBusyId("others")
    setMessage("")
    setError("")
    try {
      const res = await authApi.revokeOtherSessions()
      setMessage(res.revoked ? `${res.revoked} other device(s) logged out.` : "No other devices were logged in.")
      await load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusyId(null)
    }
  }

  const others = sessions.filter((s) => !s.current).length

  return (
    <div className="page">
      <div className="section-header section-header-split">
        <h1 className="page-title">Active sessions</h1>
        <button className="btn btn-danger btn-sm" onClick={revokeOthers}
          disabled={busyId !== null || loading || others === 0}>
          {busyId === "others" ? "Logging out…" : "Log out all other devices"}
        </button>
      </div>
      <p className="muted">Every browser or device where you are logged in. Revoke any you don't recognise.</p>

      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      {loading ? (
        <div className="loading">Loading sessions…</div>
      ) : sessions.length === 0 ? (
        <p className="empty-state">No active sessions.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Device</th>
                <th>IP address</th>
                <th>Signed in</th>
                <th>Last active</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>
                    {describeDevice(s.user_agent)}
                    {s.current && <span className="badge-current">This device</span>}
                  </td>
                  <td>{s.ip_address ?? "—"}</td>
                  <td>{new Date(s.created_at).toLocaleString()}</td>
                  <td>{new Date(s.last_used_at).toLocaleString()}</td>
                  <td>
                    {!s.current && (
                      <button className="btn btn-danger btn-sm" onClick={() => revoke(s.id)}
                        disabled={busyId !== null}>
                        {busyId === s.id ? "Revoking…" : "Revoke"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
