"use client"
import { createContext, useContext, useState, useEffect, ReactNode } from "react"
import axios from "axios"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface AuthCtx {
  token: string | null
  username: string | null
  role: string | null
  mustChangePassword: boolean
  login: (user: string, pass: string) => Promise<void>
  changePassword: (newPassword: string, currentPassword?: string) => Promise<void>
  refreshProfile: () => Promise<void>
  logout: () => void
  api: typeof axios
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [role, setRole] = useState<string | null>(null)
  const [mustChangePassword, setMustChangePassword] = useState(false)

  const api = axios.create({ baseURL: API })
  api.interceptors.request.use((config) => {
    const t = localStorage.getItem("srtime_token")
    if (t) config.headers.Authorization = `Bearer ${t}`
    return config
  })
  api.interceptors.response.use(
    r => r,
    err => {
      if (err.response?.status === 401) logout()
      return Promise.reject(err)
    }
  )

  async function refreshProfile() {
    const me = await api.get("/api/auth/me")
    setRole(me.data.role)
    setMustChangePassword(Boolean(me.data.must_change_password))
    localStorage.setItem("srtime_role", me.data.role || "viewer")
    localStorage.setItem("srtime_must_change_password", me.data.must_change_password ? "1" : "0")
  }

  useEffect(() => {
    const t = localStorage.getItem("srtime_token")
    const u = localStorage.getItem("srtime_user")
    const r = localStorage.getItem("srtime_role")
    const m = localStorage.getItem("srtime_must_change_password")
    if (t) {
      setToken(t)
      setUsername(u)
      setRole(r)
      setMustChangePassword(m === "1")
      refreshProfile().catch(() => logout())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function login(user: string, pass: string) {
    const formData = new FormData()
    formData.append("username", user)
    formData.append("password", pass)
    const res = await axios.post(`${API}/api/auth/token`, formData)
    const t = res.data.access_token
    setToken(t)
    setUsername(user)
    setMustChangePassword(Boolean(res.data.must_change_password))
    localStorage.setItem("srtime_token", t)
    localStorage.setItem("srtime_user", user)
    localStorage.setItem("srtime_must_change_password", res.data.must_change_password ? "1" : "0")
    await refreshProfile()
  }

  async function changePassword(newPassword: string, currentPassword?: string) {
    await api.post("/api/auth/change-password", { current_password: currentPassword || null, new_password: newPassword })
    setMustChangePassword(false)
    localStorage.setItem("srtime_must_change_password", "0")
    await refreshProfile()
  }

  function logout() {
    setToken(null)
    setUsername(null)
    setRole(null)
    setMustChangePassword(false)
    localStorage.removeItem("srtime_token")
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
