/**
 * Who is logged in, for the whole app.
 *
 * On page load the status is "loading": we ask the server for a fresh access token
 * using the httpOnly refresh cookie. Only after that answer do we show either the
 * app or the login page - so a logged-in user never sees a flash of guest content.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { authApi } from "../api/auth"
import { refreshSession, setAccessToken, setSessionExpiredHandler } from "../api/client"
import type { User } from "../types"

type AuthStatus = "loading" | "authenticated" | "guest"

interface AuthContextValue {
  status: AuthStatus
  user: User | null
  login: (email: string, password: string) => Promise<void>
  signup: (fullName: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  updateUser: (user: User) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading")
  const [user, setUser] = useState<User | null>(null)

  const becomeGuest = useCallback(() => {
    setAccessToken(null)
    setUser(null)
    setStatus("guest")
  }, [])

  // Restore the session once when the app starts.
  useEffect(() => {
    let cancelled = false
    setSessionExpiredHandler(becomeGuest)
    refreshSession().then((res) => {
      if (cancelled) return
      if (res) {
        setUser(res.user)
        setStatus("authenticated")
      } else {
        setStatus("guest")
      }
    })
    return () => {
      cancelled = true
      setSessionExpiredHandler(null)
    }
  }, [becomeGuest])

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login(email, password)
    setAccessToken(res.access_token)
    setUser(res.user)
    setStatus("authenticated")
  }, [])

  const signup = useCallback(async (fullName: string, email: string, password: string) => {
    const res = await authApi.signup(fullName, email, password)
    setAccessToken(res.access_token)
    setUser(res.user)
    setStatus("authenticated")
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout() // revokes the session on the server and clears the cookie
    } catch {
      // Even if the network fails, forget the token locally.
    }
    becomeGuest()
  }, [becomeGuest])

  const value = useMemo(
    () => ({ status, user, login, signup, logout, updateUser: setUser }),
    [status, user, login, signup, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>")
  return ctx
}
