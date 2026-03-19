"use client"
import { useState, useEffect } from "react"
import { useAuth } from "./context/AuthContext"
import LoginPage from "./components/LoginPage"
import UsersTab from "./components/UsersTab"
import ShiftsTab from "./components/ShiftsTab"
import ProcessedTab from "./components/ProcessedTab"
import MovementsTab from "./components/MovementsTab"

const TABS = [
  { id: "users",     label: "👨‍💼 Usuarios" },
  { id: "shifts",    label: "⏰ Turnos Horarios" },
  { id: "movements", label: "📋 Movimientos" },
  { id: "processed", label: "✅ Asistencia Procesada" },
]

export default function Home() {
  const { token, username, logout } = useAuth()
  const [activeTab, setActiveTab] = useState("processed")
  const [theme, setTheme] = useState<"light" | "dark">("light")

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
  }, [theme])

  if (!token) return <LoginPage />

  return (
    <div className="app-wrapper">
      {/* Top Bar */}
      <div className="topbar">
        <span className="topbar-title">🕐 SRTime</span>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ fontSize: 13, opacity: 0.7 }}>👤 {username}</span>
          <button className="btn" onClick={() => setTheme(t => t === "light" ? "dark" : "light")} style={{ padding: "4px 12px", fontSize: 12 }}>
            {theme === "light" ? "🌙 Oscuro" : "☀️ Claro"}
          </button>
          <button className="btn btn-danger" onClick={logout} style={{ padding: "4px 12px", fontSize: 12 }}>
            Cerrar Sesión
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="main-area">
        {activeTab === "users"     && <UsersTab />}
        {activeTab === "shifts"    && <ShiftsTab />}
        {activeTab === "movements" && <MovementsTab />}
        {activeTab === "processed" && <ProcessedTab />}
      </div>
    </div>
  )
}
