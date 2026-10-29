"use client"
import { useState, useEffect, useMemo } from "react"
import { useAuth } from "./context/AuthContext"
import axios from "axios"
import Image from "next/image"
import LoginPage from "./components/LoginPage"
import DashboardTab from "./components/DashboardTab"
import ImportTab from "./components/ImportTab"
import UsersTab from "./components/UsersTab"
import ShiftsTab from "./components/ShiftsTab"
import ProcessedTab from "./components/ProcessedTab"
import AbsencesTab from "./components/AbsencesTab"
import MovementsTab from "./components/MovementsTab"
import AuthUsersTab from "./components/AuthUsersTab"
import TerminalsTab from "./components/TerminalsTab"
import ControlCenterTab from "./components/ControlCenterTab"
import HolidaysTab from "./components/HolidaysTab"
import ReportsTab from "./components/ReportsTab"
import { Users, Clock, ArrowLeftRight, CheckSquare, Sun, Moon, LogOut, ShieldCheck, FileUp, MonitorSmartphone, UserX, Settings, LayoutDashboard, CalendarDays, FileBarChart } from "lucide-react"

// uiKey: clave de la pestaña en ui.ini (la misma que usa SRTime_Win). La API
// decide cuáles se ocultan; las pestañas sin uiKey no se pueden ocultar.
const CORE_TABS = [
  { id: "users",     label: "Empleados",            Icon: Users,          uiKey: "empleados" },
  { id: "shifts",    label: "Turnos Horarios",      Icon: Clock,          uiKey: "turnos_horarios" },
  { id: "movements", label: "Movimientos",          Icon: ArrowLeftRight, uiKey: "movimientos" },
  { id: "processed", label: "Movimientos Procesados", Icon: CheckSquare,  uiKey: "movimientos_procesados" },
  { id: "absences",  label: "Ausencias",             Icon: UserX,         uiKey: "ausencias" },
  { id: "holidays",  label: "Feriados",              Icon: CalendarDays,  uiKey: "feriados" },
  { id: "reports",   label: "Reportes",              Icon: FileBarChart,  uiKey: "reportes" },
]

interface AddonUiFeatures {
  file_import?: boolean
  terminal_management?: boolean
  network_import?: boolean
}

type Theme = "light" | "dark"
const PASSWORD_PATTERN = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/
const PASSWORD_RULE_MESSAGE = "Usá al menos 8 caracteres, con una letra y un número; sin caracteres especiales"

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}

export default function Home() {
  const { token, username, role, mustChangePassword, changePassword, logout, api } = useAuth()
  const [activeTab, setActiveTab] = useState("dashboard")
  const [addonUi, setAddonUi] = useState<AddonUiFeatures>({})
  const [addonUiLoaded, setAddonUiLoaded] = useState(false)
  const [hiddenTabs, setHiddenTabs] = useState<string[]>([])
  const [uiSettingsLoaded, setUiSettingsLoaded] = useState(false)
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [passwordError, setPasswordError] = useState("")
  const [savingPassword, setSavingPassword] = useState(false)
  // Start with light (safe SSR default); real value set in useEffect
  const [theme, setTheme] = useState<Theme>("light")

  const hasImport = addonUi.file_import || addonUi.network_import
  const tabs = useMemo(() => [
      { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard, uiKey: "dashboard" },
      ...(hasImport ? [{ id: "import", label: "Importar", Icon: FileUp, uiKey: "importar" }] : []),
      ...(addonUi.terminal_management ? [{ id: "terminals", label: "Terminales y Biométricos", Icon: MonitorSmartphone, uiKey: "terminales" }] : []),
      ...CORE_TABS,
      ...(role === "root" ? [{ id: "auth_users", label: "Usuarios Autorizados", Icon: ShieldCheck, uiKey: "usuarios_autorizados" }, { id: "control", label: "Control Center", Icon: Settings, uiKey: "" }] : []),
    ].filter(tab => !hiddenTabs.includes(tab.uiKey)), [addonUi.terminal_management, hasImport, hiddenTabs, role])

  useEffect(() => {
    if (!token) {
      setAddonUi({})
      setAddonUiLoaded(false)
      return
    }
    let cancelled = false
    api.get("/api/import/parsers")
      .then(({ data }) => {
        if (cancelled) return
        const features = (data.parsers || []).reduce((all: AddonUiFeatures, parser: { ui_features?: AddonUiFeatures }) => ({
          file_import: all.file_import || parser.ui_features?.file_import,
          terminal_management: all.terminal_management || parser.ui_features?.terminal_management,
          network_import: all.network_import || parser.ui_features?.network_import,
        }), {})
        setAddonUi(features)
      })
      .catch(() => { if (!cancelled) setAddonUi({}) })
      .finally(() => { if (!cancelled) setAddonUiLoaded(true) })
    return () => { cancelled = true }
  }, [api, token])

  useEffect(() => {
    if (!token) {
      setHiddenTabs([])
      setUiSettingsLoaded(false)
      return
    }
    let cancelled = false
    // Si ui.ini no se puede leer, todo queda visible (mismo criterio que Desktop).
    api.get("/api/ui/settings")
      .then(({ data }) => { if (!cancelled) setHiddenTabs(Array.isArray(data.hidden_tabs) ? data.hidden_tabs : []) })
      .catch(() => { if (!cancelled) setHiddenTabs([]) })
      .finally(() => { if (!cancelled) setUiSettingsLoaded(true) })
    return () => { cancelled = true }
  }, [api, token])

  useEffect(() => {
    if (!addonUiLoaded || !uiSettingsLoaded) return
    if (!tabs.some(tab => tab.id === activeTab)) {
      setActiveTab(tabs[0]?.id || "users")
    }
  }, [activeTab, addonUiLoaded, tabs, uiSettingsLoaded])

  const visibleTabIds = new Set(tabs.map(tab => tab.id))

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ tab?: string }>).detail
      if (detail?.tab && tabs.some(tab => tab.id === detail.tab)) {
        setActiveTab(detail.tab)
      }
    }
    window.addEventListener("srtime:navigate-tab", handler)
    return () => window.removeEventListener("srtime:navigate-tab", handler)
  }, [tabs])

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
    if (!PASSWORD_PATTERN.test(newPassword)) {
      setPasswordError(PASSWORD_RULE_MESSAGE)
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
          {visibleTabIds.has(activeTab) && (
            <>
              {activeTab === "users"      && <UsersTab />}
              {activeTab === "dashboard"  && <DashboardTab />}
              {activeTab === "import"     && hasImport && <ImportTab fileImport={Boolean(addonUi.file_import)} networkImport={Boolean(addonUi.network_import)} />}
              {activeTab === "terminals"  && addonUi.terminal_management && <TerminalsTab />}
              {activeTab === "shifts"     && <ShiftsTab />}
              {activeTab === "movements"  && <MovementsTab />}
              {activeTab === "processed"  && <ProcessedTab />}
              {activeTab === "absences"   && <AbsencesTab />}
              {activeTab === "holidays"   && <HolidaysTab />}
              {activeTab === "reports"    && <ReportsTab />}
              {activeTab === "auth_users" && role === "root" && <AuthUsersTab />}
              {activeTab === "control"    && role === "root" && <ControlCenterTab />}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
