"use client"
import { useEffect, useState } from "react"
import Image from "next/image"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Database, Lock, User, AlertCircle, LogIn } from "lucide-react"

const API = process.env.NEXT_PUBLIC_API_URL || ""
const APP_VERSION = "v0.9.0-beta.10"
const PASSWORD_PATTERN = "(?=.*[A-Za-z])(?=.*\\d)[A-Za-z\\d]{8,}"

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError]   = useState("")
  const [loading, setLoading] = useState(false)
  const [setupRequired, setSetupRequired] = useState<boolean | null>(null)
  const [databaseEngine, setDatabaseEngine] = useState("postgres")
  // Proposed values come from /api/setup/status (the local profile written by
  // the installer); a database is only created when the operator confirms.
  const [dbHost, setDbHost] = useState("")
  const [dbPort, setDbPort] = useState("")
  const [dbUser, setDbUser] = useState("")
  const [dbPassword, setDbPassword] = useState("")
  const [dbName, setDbName] = useState("")
  const [databaseCreated, setDatabaseCreated] = useState(false)
  const [adminPassword, setAdminPassword] = useState("")
  const [confirmAdminPassword, setConfirmAdminPassword] = useState("")
  const passwordsMismatch = confirmAdminPassword.length > 0 && adminPassword !== confirmAdminPassword
  const passwordsMatch = adminPassword.length > 0 && confirmAdminPassword.length > 0 && adminPassword === confirmAdminPassword

  useEffect(() => {
    axios.get(`${API}/api/setup/status`)
      .then(res => {
        setSetupRequired(Boolean(res.data.setup_required))
        setDatabaseEngine(res.data.database_engine || "postgres")
        setDatabaseCreated(Boolean(res.data.configured && res.data.setup_required))
        const suggested = res.data.suggested_connection
        if (suggested) {
          setDbHost(suggested.db_host)
          setDbPort(String(suggested.db_port))
          setDbUser(suggested.db_user)
          setDbName(suggested.db_name)
        }
      })
      // A failed status check must never expose the login form as if setup had
      // completed; the operator needs the installer/retry path instead.
      .catch(() => setSetupRequired(true))
  }, [])

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

  async function handleCreateDatabase(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true); setError("")
    try {
      await axios.post(`${API}/api/setup/database`, {
        db_host: dbHost, db_port: Number(dbPort), db_user: dbUser,
        db_password: dbPassword, db_name: dbName,
      })
      setDatabaseCreated(true)
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "No se pudo configurar PostgreSQL")
      } else {
        setError("No se pudo configurar PostgreSQL")
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateAdmin(e: React.FormEvent) {
    e.preventDefault()
    if (adminPassword !== confirmAdminPassword) {
      setError("Las contraseñas de administrador no coinciden")
      return
    }
    setLoading(true); setError("")
    try {
      await axios.post(`${API}/api/setup/admin`, {
        admin_password: adminPassword,
        confirm_admin_password: confirmAdminPassword,
      })
      await login("admin", adminPassword)
    } catch (err) {
      if (axios.isAxiosError(err)) setError(err.response?.data?.detail || "No se pudo crear o verificar el administrador")
      else setError("No se pudo crear o verificar el administrador")
    } finally { setLoading(false) }
  }

  return (
    <div className={`login-page${setupRequired ? " setup-page" : ""}`}>
      <div className={`login-box${setupRequired ? " setup-login-box" : ""}`}>
        {/* Logo */}
        <div className={`login-brand${setupRequired ? " login-brand-compact" : ""}`} style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: 28 }}>
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
          <p style={{ color: "var(--text-muted)", fontSize: 11, margin: "5px 0 0" }}>
            {APP_VERSION}
          </p>
        </div>

        {setupRequired && <div className="setup-form">
          <div style={{ display: "flex", gap: 8, alignItems: "center", color: "var(--primary)", marginBottom: 16, fontWeight: 600 }}>
            <Database size={17} /> Configuración inicial
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, marginBottom: 16 }}>
            {databaseEngine === "sqlite"
              ? "SRTime creará la base local en este equipo. Definí el usuario inicial para comenzar."
              : "Primero creá o conectá la base de datos. Luego definí el usuario inicial de SRTime."}
          </p>
          {!databaseCreated && databaseEngine !== "sqlite" ? <form onSubmit={handleCreateDatabase}>
            <div className="form-group"><label>Servidor PostgreSQL</label><input value={dbHost} onChange={e => setDbHost(e.target.value)} required /></div>
            <div className="form-group"><label>Puerto</label><input type="number" value={dbPort} onChange={e => setDbPort(e.target.value)} required /></div>
            <div className="form-group"><label>Usuario PostgreSQL</label><input value={dbUser} onChange={e => setDbUser(e.target.value)} required /></div>
            <div className="form-group"><label>Contraseña PostgreSQL</label><input type="password" value={dbPassword} onChange={e => setDbPassword(e.target.value)} required /></div>
            <div className="form-group"><label>Base de datos</label><input value={dbName} onChange={e => setDbName(e.target.value)} required pattern="[A-Za-z_][A-Za-z0-9_]*" /></div>
            <button type="submit" className="btn btn-primary" style={{ width: "100%", justifyContent: "center", height: 40 }} disabled={loading}>{loading ? "Creando..." : "Crear base de datos"}</button>
          </form> : <div role="status" style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--status-success)", background: "var(--bg-secondary)", border: "1px solid var(--status-success)", borderRadius: 6, padding: "10px 12px", fontSize: 13 }}>
            <Database size={16} /> {databaseEngine === "sqlite" ? "Base local lista para inicializar." : "Conexión y esquema de la base listos. Ahora creá el administrador de SRTime."}
          </div>}
          <form onSubmit={handleCreateAdmin} style={{ borderTop: "1px solid var(--border)", marginTop: 20, paddingTop: 16, opacity: databaseCreated ? 1 : .55 }}>
          <div className="form-group">
            <label>Usuario inicial de SRTime</label>
            <input value="admin" disabled aria-label="Usuario inicial de SRTime" />
            <p style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 5 }}>{databaseEngine === "sqlite" ? "Administrador de la base local de este equipo." : "Disponible luego de crear la base de datos."}</p>
          </div>
          <div className="form-group"><label>Contraseña para el usuario admin</label><input type="password" value={adminPassword} onChange={e => setAdminPassword(e.target.value)} required disabled={!databaseCreated} minLength={8} pattern={PASSWORD_PATTERN} title="Al menos 8 caracteres, con una letra y un número; sin caracteres especiales" /></div>
          <div className="form-group"><label>Confirmar contraseña</label><input type="password" value={confirmAdminPassword} onChange={e => setConfirmAdminPassword(e.target.value)} required disabled={!databaseCreated} minLength={8} pattern={PASSWORD_PATTERN} title="Al menos 8 caracteres, con una letra y un número; sin caracteres especiales" /></div>
          {passwordsMismatch && <p className="password-match-message password-match-error">Las contraseñas no coinciden.</p>}
          {passwordsMatch && <p className="password-match-message password-match-ok">Las contraseñas coinciden.</p>}
          <div className="setup-actions">
            {error && <div style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--status-error)", fontSize: 13, marginBottom: 12 }}><AlertCircle size={14} /> {error}</div>}
            <button type="submit" className="btn btn-primary" style={{ width: "100%", justifyContent: "center", gap: 8, height: 40 }} disabled={loading || !databaseCreated || !passwordsMatch}>
              {loading ? "Creando..." : <><Database size={16} /> Crear administrador e iniciar</>}
            </button>
          </div>
          </form>
        </div>}

        {setupRequired === false && <form onSubmit={handleSubmit}>
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
        </form>}
      </div>
    </div>
  )
}
