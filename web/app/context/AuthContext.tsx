"use client"
import { createContext, useContext, useState, useEffect, ReactNode } from "react"
import axios from "axios"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface AuthCtx {
  token: string | null
  username: string | null
  login: (user: string, pass: string) => Promise<void>
  logout: () => void
  api: typeof axios
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [username, setUsername] = useState<string | null>(null)

  useEffect(() => {
    const t = localStorage.getItem("srtime_token")
    const u = localStorage.getItem("srtime_user")
    if (t) { setToken(t); setUsername(u) }
  }, [])

  // Create a persistent axios instance with the auth header
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

  async function login(user: string, pass: string) {
    const formData = new FormData()
    formData.append("username", user)
    formData.append("password", pass)
    const res = await axios.post(`${API}/api/auth/token`, formData)
    const t = res.data.access_token
    setToken(t)
    setUsername(user)
    localStorage.setItem("srtime_token", t)
    localStorage.setItem("srtime_user", user)
  }

  function logout() {
    setToken(null)
    setUsername(null)
    localStorage.removeItem("srtime_token")
    localStorage.removeItem("srtime_user")
  }

  return <AuthContext.Provider value={{ token, username, login, logout, api }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be inside AuthProvider")
  return ctx
}
