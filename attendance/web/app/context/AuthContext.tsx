"use client"
import { createContext, useCallback, useContext, useState, useEffect, ReactNode } from "react"
import axios, { AxiosInstance } from "axios"

const API = process.env.NEXT_PUBLIC_API_URL || ""

const apiClient = axios.create({ baseURL: API, withCredentials: true })

interface AuthCtx {
  token: string | null
  username: string | null
  role: string | null
  mustChangePassword: boolean
  login: (user: string, pass: string) => Promise<void>
  changePassword: (newPassword: string, currentPassword?: string) => Promise<void>
  refreshProfile: () => Promise<void>
  logout: () => void
  api: AxiosInstance
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [role, setRole] = useState<string | null>(null)
  const [mustChangePassword, setMustChangePassword] = useState(false)

  const api = apiClient

  const refreshProfile = useCallback(async () => {
    const me = await api.get("/api/auth/me")
    setRole(me.data.role)
    setMustChangePassword(Boolean(me.data.must_change_password))
    localStorage.setItem("srtime_role", me.data.role || "viewer")
    localStorage.setItem("srtime_must_change_password", me.data.must_change_password ? "1" : "0")
  }, [api])

  useEffect(() => {
    const u = localStorage.getItem("srtime_user")
    const r = localStorage.getItem("srtime_role")
    const m = localStorage.getItem("srtime_must_change_password")
    if (u) {
      setToken("cookie")
      setUsername(u)
      setRole(r)
      setMustChangePassword(m === "1")
      refreshProfile().catch(() => logout())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshProfile])

  async function login(user: string, pass: string) {
    const formData = new FormData()
    formData.append("username", user)
    formData.append("password", pass)
    const res = await axios.post(`${API}/api/auth/token`, formData, { withCredentials: true })
    // Do not render the application until the cookie has been verified and the
    // complete profile is available. This avoids a half-authenticated UI.
    const me = await api.get("/api/auth/me")
    try {
      localStorage.setItem("srtime_user", user)
      localStorage.setItem("srtime_role", me.data.role || "viewer")
      localStorage.setItem("srtime_must_change_password", me.data.must_change_password ? "1" : "0")
    } catch {
      // The session cookie remains valid when browser storage is unavailable.
    }
    setToken("cookie")
    setUsername(user)
    setRole(me.data.role || "viewer")
    setMustChangePassword(Boolean(me.data.must_change_password ?? res.data.must_change_password))
  }

  async function changePassword(newPassword: string, currentPassword?: string) {
    await api.post("/api/auth/change-password", { current_password: currentPassword || null, new_password: newPassword })
    setMustChangePassword(false)
    localStorage.setItem("srtime_must_change_password", "0")
    await refreshProfile()
  }

  function logout() {
    void api.post("/api/auth/logout").catch(() => undefined)
    setToken(null)
    setUsername(null)
    setRole(null)
    setMustChangePassword(false)
    localStorage.removeItem("srtime_user")
    localStorage.removeItem("srtime_role")
    localStorage.removeItem("srtime_must_change_password")
  }

  return <AuthContext.Provider value={{ token, username, role, mustChangePassword, login, changePassword, refreshProfile, logout, api }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be inside AuthProvider")
  return ctx
}
