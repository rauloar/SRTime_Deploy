"use client"

import { useCallback, useEffect, useState } from "react"
import { Activity, Database, HardDriveDownload, RefreshCw, ServerCog } from "lucide-react"
import { useAuth } from "../context/AuthContext"

type Status = {
  application: { status: string }
  database: { status: string; engine: string; error?: string | null }
  scheduler: { status: string }
  backup: { enabled: boolean; latest: { name: string; created_at: string; size_bytes: number } | null }
  service: { status: string; name: string }
}

const label = (status: string) => status === "ok" || status === "running" ? "Operativo" : status === "unavailable" ? "Sin conexión" : "Administrado externamente"

export default function ControlCenterTab() {
  const { api } = useAuth()
  const [data, setData] = useState<Status | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true); setError("")
    try { setData((await api.get("/api/control/status")).data) }
    catch { setError("No se pudo consultar el estado operativo.") }
    finally { setLoading(false) }
  }, [api])

  useEffect(() => { void refresh() }, [refresh])

  async function backupNow() {
    setCreating(true); setError("")
    try { await api.post("/api/control/backups"); await refresh() }
    catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "No se pudo crear el backup.") }
    finally { setCreating(false) }
  }

  return <div className="fade-in">
    <div className="tab-header"><div><h2>Control Center</h2><p>Estado operativo local de SRTime.</p></div><button className="btn" onClick={() => void refresh()} disabled={loading}><RefreshCw size={15} /> Actualizar</button></div>
    {error && <p className="absence-message absence-message-error">{error}</p>}
    <div className="control-grid">
      <article className="control-card"><Activity size={20} /><h3>Aplicación</h3><strong className="badge badge-ok">{data ? label(data.application.status) : "Consultando"}</strong><p>FastAPI y la interfaz Web usan un único proceso.</p></article>
      <article className="control-card"><Database size={20} /><h3>Base de datos</h3><strong className={`badge ${data?.database.status === "ok" ? "badge-ok" : "badge-error"}`}>{data ? label(data.database.status) : "Consultando"}</strong><p>{data ? `${data.database.engine.toUpperCase()}${data.database.error ? `: ${data.database.error}` : ""}` : ""}</p></article>
      <article className="control-card"><ServerCog size={20} /><h3>Tareas programadas</h3><strong className={`badge ${data?.scheduler.status === "running" ? "badge-ok" : "badge-incompleto"}`}>{data ? label(data.scheduler.status) : "Consultando"}</strong><p>Agenda de descargas de terminales.</p></article>
      <article className="control-card"><HardDriveDownload size={20} /><h3>Backups PostgreSQL</h3><strong className={`badge ${data?.backup.enabled ? "badge-ok" : "badge-incompleto"}`}>{data?.backup.enabled ? "Disponible" : "Requiere pg_dump"}</strong><p>{data?.backup.latest ? `Último: ${data.backup.latest.name}` : "Todavía no hay backups."}</p><button className="btn btn-primary" disabled={!data?.backup.enabled || creating} onClick={() => void backupNow()}>{creating ? "Creando..." : "Crear backup ahora"}</button></article>
    </div>
    <p className="control-note">Servicio configurado: {data?.service.name || "SRTimeWeb"}. Su instalación, inicio y detención se gestionarán por el instalador Windows; esta pestaña no detiene el servidor activo.</p>
  </div>
}
