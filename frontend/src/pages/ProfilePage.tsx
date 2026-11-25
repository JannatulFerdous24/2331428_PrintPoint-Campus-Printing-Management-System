import { type FormEvent, useState } from "react"
import { authApi } from "../api/auth"
import { errorText } from "../api/client"
import { useAuth } from "../auth/AuthContext"
import { passwordProblems } from "../auth/passwordRules"
import { ROLE_LABELS } from "../types"

export function ProfilePage() {
  const { user, updateUser } = useAuth()

  // --- profile form ---
  const [fullName, setFullName] = useState(user?.full_name ?? "")
  const [email, setEmail] = useState(user?.email ?? "")
  const [profilePassword, setProfilePassword] = useState("")
  const [profileMsg, setProfileMsg] = useState("")
  const [profileErr, setProfileErr] = useState("")
  const [savingProfile, setSavingProfile] = useState(false)

  // --- password form ---
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [confirm, setConfirm] = useState("")
  const [pwMsg, setPwMsg] = useState("")
  const [pwErr, setPwErr] = useState("")
  const [savingPw, setSavingPw] = useState(false)

  if (!user) return null
  const emailChanged = email.trim().toLowerCase() !== user.email

  async function saveProfile(e: FormEvent) {
    e.preventDefault()
    setProfileMsg("")
    setProfileErr("")
    setSavingProfile(true)
    try {
      const updated = await authApi.updateProfile({
        full_name: fullName.trim(),
        ...(emailChanged ? { email: email.trim(), current_password: profilePassword } : {}),
      })
      updateUser(updated)
      setProfilePassword("")
      setProfileMsg("Profile saved.")
    } catch (err) {
      setProfileErr(errorText(err))
    } finally {
      setSavingProfile(false)
    }
  }

  async function changePassword(e: FormEvent) {
    e.preventDefault()
    setPwMsg("")
    setPwErr("")
    const problems = passwordProblems(next, user?.email)
    if (problems.length) return setPwErr(`New password must have ${problems.join(", ")}.`)
    if (next !== confirm) return setPwErr("The two new passwords do not match.")
    setSavingPw(true)
    try {
      const res = await authApi.changePassword(current, next)
      setCurrent("")
      setNext("")
      setConfirm("")
      setPwMsg(
        res.other_sessions_revoked > 0
          ? `Password changed. ${res.other_sessions_revoked} other device(s) were logged out.`
          : "Password changed.",
      )
    } catch (err) {
      setPwErr(errorText(err))
    } finally {
      setSavingPw(false)
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">My profile</h1>
      <div className="card-grid">
        <form className="form-card" onSubmit={saveProfile}>
          <h2>Account details</h2>
          <p className="muted">
            Role: <strong>{ROLE_LABELS[user.role]}</strong> · Member since{" "}
            {new Date(user.created_at).toLocaleDateString()}
          </p>
          {profileMsg && <div className="alert alert-success">{profileMsg}</div>}
          {profileErr && <div className="alert alert-error" role="alert">{profileErr}</div>}
          <div className="form-group">
            <label htmlFor="full_name">Full name</label>
            <input id="full_name" required maxLength={200} value={fullName}
              onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" required maxLength={255} value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </div>
          {emailChanged && (
            <div className="form-group">
              <label htmlFor="profile_password">Current password (required to change email)</label>
              <input id="profile_password" type="password" autoComplete="current-password" required
                maxLength={128} value={profilePassword} onChange={(e) => setProfilePassword(e.target.value)} />
            </div>
          )}
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={savingProfile}>
              {savingProfile ? "Saving…" : "Save profile"}
            </button>
          </div>
        </form>

        <form className="form-card" onSubmit={changePassword}>
          <h2>Change password</h2>
          <p className="muted">Changing your password logs out your other devices.</p>
          {pwMsg && <div className="alert alert-success">{pwMsg}</div>}
          {pwErr && <div className="alert alert-error" role="alert">{pwErr}</div>}
          <div className="form-group">
            <label htmlFor="current">Current password</label>
            <input id="current" type="password" autoComplete="current-password" required maxLength={128}
              value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div className="form-group">
            <label htmlFor="new">New password</label>
            <input id="new" type="password" autoComplete="new-password" required maxLength={128}
              value={next} onChange={(e) => setNext(e.target.value)} />
            <small className="hint">At least 10 characters, with a letter and a digit.</small>
          </div>
          <div className="form-group">
            <label htmlFor="confirm">Confirm new password</label>
            <input id="confirm" type="password" autoComplete="new-password" required maxLength={128}
              value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={savingPw}>
              {savingPw ? "Changing…" : "Change password"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
