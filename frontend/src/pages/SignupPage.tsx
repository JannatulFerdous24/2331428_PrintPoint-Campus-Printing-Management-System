import { type FormEvent, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { errorText } from "../api/client"
import { useAuth } from "../auth/AuthContext"
import { passwordProblems } from "../auth/passwordRules"

export function SignupPage() {
  const { signup } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError("")
    const problems = passwordProblems(password, email)
    if (problems.length) return setError(`Password must have ${problems.join(", ")}.`)
    if (password !== confirm) return setError("The two passwords do not match.")

    setSubmitting(true)
    try {
      await signup(fullName.trim(), email.trim(), password)
      navigate("/requests", { replace: true })
    } catch (err) {
      setError(errorText(err, "Sign-up failed"))
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-brand">🖨️ PrintPoint</div>
        <h2>Create a student account</h2>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <div className="form-group">
          <label htmlFor="name">Full name</label>
          <input id="name" autoComplete="name" required maxLength={200}
            value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" required maxLength={255}
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="new-password" required maxLength={128}
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <small className="hint">At least 10 characters, with a letter and a digit.</small>
        </div>
        <div className="form-group">
          <label htmlFor="confirm">Confirm password</label>
          <input id="confirm" type="password" autoComplete="new-password" required maxLength={128}
            value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? "Creating account…" : "Sign up"}
        </button>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  )
}
