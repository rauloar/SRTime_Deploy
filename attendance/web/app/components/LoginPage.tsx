"use client"
import { useState } from "react"
import Image from "next/image"
import { useAuth } from "../context/AuthContext"
import { Lock, User, AlertCircle, LogIn } from "lucide-react"

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError]   = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true); setError("")
    try {
      await login(username, password)
    } catch {
      setError("Usuario o contraseña incorrectos")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-box">
        {/* Logo */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: 28 }}>
          <Image
            src="/img/sr_logo.png"
            alt="SRTime Logo"
            width={72}
            height={72}
            style={{ objectFit: "contain", marginBottom: 14 }}
          />
          <div className="login-header" style={{ marginBottom: 4 }}>SRTime</div>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, margin: 0 }}>
            Sistema de Control de Asistencias
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Usuario</label>
            <div style={{ position: "relative" }}>
              <User size={15} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
              <input
                type="text" value={username}
                onChange={e => setUsername(e.target.value)}
                autoFocus required placeholder="admin"
                style={{ paddingLeft: 34 }}
              />
            </div>
          </div>
          <div className="form-group">
            <label>Contraseña</label>
            <div style={{ position: "relative" }}>
              <Lock size={15} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
              <input
                type="password" value={password}
                onChange={e => setPassword(e.target.value)}
                required placeholder="••••••"
                style={{ paddingLeft: 34 }}
              />
            </div>
          </div>

          {error && (
            <div style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--status-error)", fontSize: 13, marginBottom: 12 }}>
              <AlertCircle size={14} /> {error}
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: "100%", justifyContent: "center", gap: 8, height: 40, marginTop: 4 }} disabled={loading}>
            {loading ? "Iniciando sesión..." : <><LogIn size={16} /> Iniciar Sesión</>}
          </button>
        </form>
      </div>
    </div>
  )
}
