"use client"
import { useState, useEffect } from "react"
import { useAuth } from "./context/AuthContext"
import axios from "axios"
import Image from "next/image"
import LoginPage from "./components/LoginPage"
import ImportTab from "./components/ImportTab"
import UsersTab from "./components/UsersTab"
import ShiftsTab from "./components/ShiftsTab"
import ProcessedTab from "./components/ProcessedTab"
import MovementsTab from "./components/MovementsTab"
import AuthUsersTab from "./components/AuthUsersTab"
import { Users, Clock, ArrowLeftRight, CheckSquare, Sun, Moon, LogOut, ShieldCheck, FileUp } from "lucide-react"

const TABS = [
  { id: "import",    label: "Importar",             Icon: FileUp },
  { id: "users",     label: "Empleados",            Icon: Users },
  { id: "shifts",    label: "Turnos Horarios",      Icon: Clock },
  { id: "movements", label: "Movimientos",          Icon: ArrowLeftRight },
  { id: "processed", label: "Asistencia Procesada", Icon: CheckSquare },
]

type Theme = "light" | "dark"

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}

export default function Home() {
  const { token, username, role, mustChangePassword, changePassword, logout } = useAuth()
  const [activeTab, setActiveTab] = useState("import")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [passwordError, setPasswordError] = useState("")
  const [savingPassword, setSavingPassword] = useState(false)
  // Start with light (safe SSR default); real value set in useEffect
  const [theme, setTheme] = useState<Theme>("light")

  const tabs = role === "root"
    ? [...TABS, { id: "auth_users", label: "Usuarios Autorizados", Icon: ShieldCheck }]
    : TABS

  useEffect(() => {
    // Read OS preference on mount and apply
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = (dark: boolean) => {
      const t: Theme = dark ? "dark" : "light"
      setTheme(t)
      document.documentElement.setAttribute("data-theme", t)
    }
    apply(mq.matches)
    // Live system theme changes
    const handler = (e: MediaQueryListEvent) => apply(e.matches)
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  // Manual override
  function toggleTheme() {
    const next: Theme = theme === "light" ? "dark" : "light"
    setTheme(next)
    document.documentElement.setAttribute("data-theme", next)
  }

  if (!token) return <LoginPage />

  async function handleChangePassword() {
    setPasswordError("")
    if (newPassword.length < 6) {
      setPasswordError("La contraseña debe tener al menos 6 caracteres")
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Las contraseñas no coinciden")
      return
    }
    setSavingPassword(true)
    try {
      await changePassword(newPassword)
      setNewPassword("")
      setConfirmPassword("")
    } catch (e: unknown) {
      setPasswordError(getErrorMessage(e, "Error al cambiar contraseña"))
    } finally {
      setSavingPassword(false)
    }
  }

  return (
    <div className="app-wrapper">
      {mustChangePassword && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <div className="modal-title"><span>Cambio de contraseña obligatorio</span></div>
            <p style={{ marginBottom: 12, color: "var(--text-secondary)", fontSize: 13 }}>
              Debes cambiar la contraseña para continuar.
            </p>
            <div className="form-group">
              <label>Nueva contraseña</label>
              <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Confirmar contraseña</label>
              <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} />
            </div>
            {passwordError && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {passwordError}</p>}
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary" onClick={handleChangePassword} disabled={savingPassword}>
                {savingPassword ? "Guardando..." : "Guardar contraseña"}
              </button>
              <button className="btn btn-danger" onClick={logout}>Salir</button>
            </div>
          </div>
        </div>
      )}

      {/* Top Bar */}
      <div className="topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Image src="/img/sr_logo.png" alt="SRTime" width={30} height={30} style={{ objectFit: "contain" }} />
          <span className="topbar-title">SRTime</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 5 }}>
            <Users size={14} /> {username}
          </span>
          <button className="btn" onClick={toggleTheme} style={{ padding: "5px 12px" }} title="Cambiar tema">
            {theme === "light" ? <><Moon size={14} /> Oscuro</> : <><Sun size={14} /> Claro</>}
          </button>
          <button className="btn btn-danger" onClick={logout} style={{ padding: "5px 12px" }}>
            <LogOut size={14} /> Salir
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="tabs">
        {tabs.map(({ id, label, Icon }) => (
          <button
            key={id}
            className={`tab ${activeTab === id ? "active" : ""}`}
            onClick={() => setActiveTab(id)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="main-area">
        <div className="content-wrapper">
          {activeTab === "users"      && <UsersTab />}
          {activeTab === "import"     && <ImportTab />}
          {activeTab === "shifts"     && <ShiftsTab />}
          {activeTab === "movements"  && <MovementsTab />}
          {activeTab === "processed"  && <ProcessedTab />}
          {activeTab === "auth_users" && role === "root" && <AuthUsersTab />}
        </div>
      </div>
    </div>
  )
}
