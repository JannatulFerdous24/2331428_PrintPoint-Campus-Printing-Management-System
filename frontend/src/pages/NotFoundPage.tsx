import { Link } from "react-router-dom"
import { ThemeToggle } from "../components/ThemeToggle"

export function NotFoundPage() {
  return (
    <div className="auth-page">
      <ThemeToggle floating />
      <div className="auth-card">
        <div className="auth-brand">🖨️ PrintPoint</div>
        <h2>Page not found</h2>
        <p className="muted">The page you are looking for does not exist.</p>
        <Link to="/requests" className="btn btn-primary">Go to my print requests</Link>
      </div>
    </div>
  )
}
