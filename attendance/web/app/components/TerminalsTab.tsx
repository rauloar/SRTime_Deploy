"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Plus, RefreshCw, Pencil, Trash2, X, Fingerprint, Activity, Download, Clock, CalendarClock } from "lucide-react"
import Pagination from "./Pagination"

interface Terminal {
  id: number;
  name: string;
  driver_name: string;
  ip: string;
  port: number;
  connection_params: Record<string, string | number | boolean>;
  has_password?: boolean;
  serial_number?: string;
  is_active: boolean;
  last_sync?: string;
  pull_schedule?: PullSchedule;
}

interface PullSchedule {
  enabled: boolean;
  interval_minutes?: number | null;
  window_start?: string | null;
  window_end?: string | null;
  next_pull_at?: string | null;
  last_status?: string | null;
  last_error?: string | null;
}

interface ParserInfo {
  name: string
  is_driver: boolean
  connection_fields: ConnectionField[]
}

interface ConnectionField {
  name: string
  label: string
  type: "text" | "number" | "password"
  default?: string
}

interface TerminalForm {
  id?: number
  name: string
  driver_name: string
  connection_params: Record<string, string | number | boolean>
  is_active: boolean
}

const EMPTY_TERMINAL: TerminalForm = { name: "", driver_name: "", connection_params: {}, is_active: true }

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop">
      <div className="modal-box" style={{ maxWidth: 450 }}>
        <div className="modal-title"><span>{title}</span><button className="modal-close" onClick={onClose}><X size={16} /></button></div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="form-group"><label>{label}</label>{children}</div>
}

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}

export default function TerminalsTab() {
  const { api } = useAuth()
  const [terminals, setTerminals] = useState<Terminal[]>([])
  const [parsers, setParsers]     = useState<ParserInfo[]>([])
  const [loading, setLoading]   = useState(true)
  const [modal, setModal]       = useState<"add" | "edit" | null>(null)
  const [current, setCurrent]   = useState<TerminalForm>(EMPTY_TERMINAL)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState("")
  const [page, setPage]         = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [selectedTerminalId, setSelectedTerminalId] = useState<number | null>(null)
  
  const [testingId, setTestingId] = useState<number | null>(null)
  const [syncingId, setSyncingId] = useState<number | null>(null)
  const [pullingId, setPullingId] = useState<number | null>(null)
  const [scheduleTerminal, setScheduleTerminal] = useState<Terminal | null>(null)
  const [schedule, setSchedule] = useState<PullSchedule>({ enabled: false, interval_minutes: 60, window_start: null, window_end: null })
  const [savingSchedule, setSavingSchedule] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [termRes, parserRes] = await Promise.all([
        api.get("/api/terminals/"),
        api.get("/api/import/parsers")
      ])
      setTerminals(termRes.data.terminals || [])
      
      const pList = parserRes.data.parsers || []
      setParsers((pList as ParserInfo[]).filter(p => p.is_driver))
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  const paginated = terminals.slice((page - 1) * pageSize, page * pageSize)
  const selectedTerminal = terminals.find(t => t.id === selectedTerminalId) || null

  function openAdd() { 
    const selected = parsers[0]
    const defaults = Object.fromEntries(
      (selected?.connection_fields || []).map(field => [field.name, field.default || ""])
    )
    setCurrent({ ...EMPTY_TERMINAL, driver_name: selected?.name || "", connection_params: defaults })
    setError(""); setModal("add") 
  }
  function openEdit(t: Terminal) {
    setCurrent({
      id: t.id,
      name: t.name,
      driver_name: t.driver_name,
      connection_params: { ...(t.connection_params || {}) },
      is_active: t.is_active,
    })
    setError(""); setModal("edit")
  }

  async function handleSave() {
    if (!current.name?.trim()) { setError("El nombre de la terminal es obligatorio."); return }
    setSaving(true); setError("")
    try {
      const payload = { 
        name: current.name, 
        driver_name: current.driver_name,
        ip: String(current.connection_params.ip || "") || null,
        port: current.connection_params.port ? Number(current.connection_params.port) : null,
        connection_params: current.connection_params,
        is_active: current.is_active
      }
      
      if (modal === "add") {
        const response = await api.post("/api/terminals/", payload)
        setSelectedTerminalId(response.data.id)
      } else {
        await api.put(`/api/terminals/${current.id}`, payload)
        setSelectedTerminalId(current.id || null)
      }
      setModal(null); load()
    } catch (e: unknown) { 
      setError(getErrorMessage(e, "Error al guardar el equipo."))
    } finally { 
      setSaving(false) 
    }
  }

  async function handleDelete(t: Terminal) {
    if (!confirm(`¿Eliminar la terminal '${t.name}' definitivamente?`)) return
    try {
      await api.delete(`/api/terminals/${t.id}`)
      if (selectedTerminalId === t.id) setSelectedTerminalId(null)
      load()
    } catch (e) {
      alert(getErrorMessage(e, "Error al eliminar la terminal."))
    }
  }

  async function testConnection(id: number) {
    setTestingId(id)
    try {
      const res = await api.post(`/api/terminals/${id}/test`)
      alert(`✅ Conexión exitosa. MAC: ${res.data.mac} | SN: ${res.data.serial_number}`)
      load() // recargar para mostrar el serial number en la tabla
    } catch (e) {
      alert(getErrorMessage(e, "Error al conectar."))
    } finally {
      setTestingId(null)
    }
  }

  async function syncTime(id: number) {
    setSyncingId(id)
    try {
      await api.post(`/api/terminals/${id}/sync`)
      alert("✅ Sincronización completada.")
    } catch (e) {
      alert(getErrorMessage(e, "Error al sincronizar reloj."))
    } finally {
      setSyncingId(null)
    }
  }

  async function pullLogs(t: Terminal) {
    setPullingId(t.id)
    try {
      const result = await api.post(`/api/terminals/${t.id}/pull`)
      const data = result.data
      alert(`✅ Descarga finalizada en ${t.name}.\n${data.nuevos} nuevos, ${data.duplicados} duplicados (${data.total} leídos).\nLos registros quedaron en Movimientos para su procesamiento.`)
      load()
    } catch (e) {
      alert(getErrorMessage(e, "No se pudieron descargar los movimientos raw."))
      load()
    } finally {
      setPullingId(null)
    }
  }

  function openSchedule(t: Terminal) {
    const saved = t.pull_schedule || { enabled: false, interval_minutes: 60, window_start: null, window_end: null }
    setSchedule({ ...saved, interval_minutes: saved.interval_minutes || 60 })
    setScheduleTerminal(t)
    setError("")
  }

  async function saveSchedule() {
    if (!scheduleTerminal) return
    if (schedule.enabled && (!schedule.interval_minutes || schedule.interval_minutes < 1)) {
      setError("El intervalo debe ser de al menos un minuto.")
      return
    }
    setSavingSchedule(true); setError("")
    try {
      await api.put(`/api/terminals/${scheduleTerminal.id}/pull-schedule`, {
        enabled: schedule.enabled,
        interval_minutes: schedule.enabled ? Number(schedule.interval_minutes) : null,
        window_start: schedule.enabled ? schedule.window_start || null : null,
        window_end: schedule.enabled ? schedule.window_end || null : null,
      })
      setScheduleTerminal(null)
      load()
    } catch (e) {
      setError(getErrorMessage(e, "No se pudo guardar la automatización."))
    } finally {
      setSavingSchedule(false)
    }
  }

  return (
    <div>
      {(modal === "add" || modal === "edit") && (
        <Modal title={modal === "add" ? "Registrar Terminal" : "Editar Terminal"} onClose={() => setModal(null)}>
          <Field label="Ubicación / Nombre:">
            <input placeholder="Ej: Puerta Principal" value={current.name} onChange={e => setCurrent(p => ({ ...p, name: e.target.value }))} />
          </Field>
          
          {modal === "add" && (
            <Field label="Tecnología (Driver):">
              <select value={current.driver_name} onChange={e => {
                const selected = parsers.find(parser => parser.name === e.target.value)
                setCurrent(p => ({
                  ...p,
                  driver_name: e.target.value,
                  connection_params: Object.fromEntries(
                    (selected?.connection_fields || []).map(field => [field.name, field.default || ""])
                  ),
                }))
              }}>
                <option value="" disabled>Seleccione marca</option>
                {parsers.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
              </select>
            </Field>
          )}

          {(parsers.find(parser => parser.name === current.driver_name)?.connection_fields || []).map(field => (
            <Field key={field.name} label={field.label}>
              <input
                type={field.type}
                placeholder={field.type === "password" && modal === "edit" ? "Dejar vacío para conservar" : undefined}
                value={String(current.connection_params[field.name] ?? "")}
                onChange={e => setCurrent(p => ({
                  ...p,
                  connection_params: { ...p.connection_params, [field.name]: e.target.value },
                }))}
              />
            </Field>
          ))}
          
          <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: 10, marginTop: 10 }}>
            <input 
              type="checkbox" 
              id="is_active" 
              checked={current.is_active} 
              onChange={e => setCurrent(p => ({ ...p, is_active: e.target.checked }))}
              style={{ width: "auto" }}
            />
            <label htmlFor="is_active" style={{ margin: 0, cursor: "pointer" }}>Terminal Activa</label>
          </div>

          {error && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {error}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 15 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? "Guardando..." : "Guardar Equipo"}</button>
            <button className="btn" onClick={() => setModal(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      {scheduleTerminal && (
        <Modal title={`Automatización · ${scheduleTerminal.name}`} onClose={() => setScheduleTerminal(null)}>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 0 }}>
            La descarga automática solo guarda movimientos raw. El procesamiento de asistencias se mantiene manual.
          </p>
          <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <input id="schedule-enabled" type="checkbox" checked={schedule.enabled} onChange={e => setSchedule(p => ({ ...p, enabled: e.target.checked }))} style={{ width: "auto" }} />
            <label htmlFor="schedule-enabled" style={{ margin: 0, cursor: "pointer" }}>Descarga automática activa</label>
          </div>
          {schedule.enabled && <>
            <Field label="Intervalo (minutos):">
              <input type="number" min="1" value={schedule.interval_minutes || 60} onChange={e => setSchedule(p => ({ ...p, interval_minutes: Number(e.target.value) }))} />
            </Field>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <Field label="Desde (opcional):"><input type="time" value={schedule.window_start || ""} onChange={e => setSchedule(p => ({ ...p, window_start: e.target.value || null }))} /></Field>
              <Field label="Hasta (opcional):"><input type="time" value={schedule.window_end || ""} onChange={e => setSchedule(p => ({ ...p, window_end: e.target.value || null }))} /></Field>
            </div>
          </>}
          {error && <p style={{ color: "var(--status-error)", fontSize: 13 }}>⚠ {error}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 15 }}>
            <button className="btn btn-primary" disabled={savingSchedule} onClick={saveSchedule}>{savingSchedule ? "Guardando..." : "Guardar automatización"}</button>
            <button className="btn" onClick={() => setScheduleTerminal(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openAdd}><Plus size={15} /> Registrar Terminal</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /></button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando terminales...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead><tr><th>Estado</th><th>Ubicación</th><th>Tecnología</th><th>Red</th><th>Serie</th><th>Última descarga</th><th>Automatización</th></tr></thead>
              <tbody>
                {paginated.length === 0 && <tr><td colSpan={7} style={{ textAlign: "center", opacity: .5, padding: 28 }}>No hay terminales conectadas. Registra tu equipo biométrico arriba.</td></tr>}
                {paginated.map(t => <tr key={t.id} onClick={() => setSelectedTerminalId(t.id)} style={{ cursor: "pointer", opacity: t.is_active ? 1 : .55, background: selectedTerminalId === t.id ? "var(--bg-hover)" : undefined }}>
                  <td style={{ textAlign: "center" }}><Activity size={18} color={t.is_active ? "var(--status-active)" : "var(--status-error)"} /></td>
                  <td><strong>{t.name}</strong></td>
                  <td><Fingerprint size={13} style={{ verticalAlign: "-2px" }} /> {t.driver_name}</td>
                  <td>{String(t.connection_params?.ip || t.ip || "—")}:{String(t.connection_params?.port || t.port || "—")}</td>
                  <td style={{ fontFamily: "monospace" }}>{t.serial_number || "—"}</td>
                  <td>{t.last_sync ? new Date(t.last_sync).toLocaleString() : "Nunca"}</td>
                  <td>{t.pull_schedule?.enabled ? `Cada ${t.pull_schedule.interval_minutes} min` : "Manual"}</td>
                </tr>)}
              </tbody>
            </table>
          </div>
          {selectedTerminal && (() => {
            const t = selectedTerminal
            const scheduleState = t.pull_schedule
            const statusColor = scheduleState?.last_status === "error" ? "var(--status-error)" : "var(--status-active)"
            return <section className="table-wrapper" style={{ marginTop: 18, padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div><strong style={{ fontSize: 17 }}>{t.name}</strong><div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>Administración de terminal · {t.driver_name}</div></div>
                <button className="btn" onClick={() => setSelectedTerminalId(null)}><X size={14} /> Cerrar</button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, margin: "18px 0", fontSize: 13 }}>
                <div><span style={{ color: "var(--text-secondary)" }}>Última descarga</span><br />{t.last_sync ? new Date(t.last_sync).toLocaleString() : "Nunca"}</div>
                <div><span style={{ color: "var(--text-secondary)" }}>Estado automático</span><br /><span style={{ color: scheduleState?.enabled ? statusColor : "var(--text-secondary)" }}>{scheduleState?.enabled ? `Cada ${scheduleState.interval_minutes} min` : "Manual"}</span></div>
                <div><span style={{ color: "var(--text-secondary)" }}>Próxima descarga</span><br />{scheduleState?.next_pull_at ? new Date(scheduleState.next_pull_at).toLocaleString() : "—"}</div>
              </div>
              {scheduleState?.last_error && <p style={{ color: "var(--status-error)", fontSize: 12, margin: "0 0 12px" }}>Último error: {scheduleState.last_error}</p>}
              <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
                <button className="btn btn-primary" onClick={() => pullLogs(t)} disabled={pullingId === t.id || !t.is_active}><Download size={14} /> {pullingId === t.id ? "Descargando..." : "Bajar registros"}</button>
                <button className="btn" onClick={() => openSchedule(t)}><CalendarClock size={14} /> Programar</button>
                <button className="btn" onClick={() => testConnection(t.id)} disabled={testingId === t.id || syncingId === t.id || pullingId === t.id || !t.is_active}><Activity size={14} /> {testingId === t.id ? "Probando..." : "Píng"}</button>
                <button className="btn" onClick={() => syncTime(t.id)} disabled={testingId === t.id || syncingId === t.id || pullingId === t.id || !t.is_active}><Clock size={14} /> {syncingId === t.id ? "Sincronizando..." : "Reloj"}</button>
                <button className="btn" onClick={() => openEdit(t)}><Pencil size={14} /> Editar</button>
                <button className="btn btn-danger" onClick={() => handleDelete(t)}><Trash2 size={14} /> Borrar</button>
              </div>
            </section>
          })()}
          <Pagination total={terminals.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
        </>
      )}
    </div>
  )
}
