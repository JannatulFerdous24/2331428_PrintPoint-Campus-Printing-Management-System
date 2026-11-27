import { type FormEvent, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { errorText } from "../api/client"
import { useAuth } from "../auth/AuthContext"
import { ThemeToggle } from "../components/ThemeToggle"

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? "/requests"

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError("")
    setSubmitting(true)
    try {
      await login(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorText(err, "Login failed"))
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <ThemeToggle floating />
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-brand">🖨️ PrintPoint</div>
        <h2>Log in</h2>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" required maxLength={255}
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="current-password" required maxLength={128}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? "Logging in…" : "Log in"}
        </button>
        <p className="auth-switch">
          New to PrintPoint? <Link to="/signup">Create an account</Link>
        </p>
      </form>
    </div>
  )
}
