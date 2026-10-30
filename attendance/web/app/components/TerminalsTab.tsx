"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Plus, RefreshCw, Pencil, Trash2, X, Fingerprint, Activity, Download, Clock, CalendarClock, Users, Upload, Wifi, History } from "lucide-react"
import Pagination from "./Pagination"
import AppDialog from "./AppDialog"

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
  mode?: "interval" | "weekly";
  interval_minutes?: number | null;
  weekdays?: number[];
  scheduled_time?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  window_start?: string | null;
  window_end?: string | null;
  next_pull_at?: string | null;
  last_status?: string | null;
  last_error?: string | null;
}

const WEEKDAYS = [
  { value: 0, label: "Lun" }, { value: 1, label: "Mar" }, { value: 2, label: "Mié" },
  { value: 3, label: "Jue" }, { value: 4, label: "Vie" }, { value: 5, label: "Sáb" },
  { value: 6, label: "Dom" },
]

interface ParserInfo {
  name: string
  is_driver: boolean
  connection_fields: ConnectionField[]
  capabilities?: Record<string, boolean>
}

interface TerminalDeviceUser {
  uid: number
  user_id: string
  name: string
  privilege: number
  privilege_label: string
}

interface PullJob {
  id: string
  terminalId: number
  state: string
  current: number
  total: number
  percent: number
  message: string
  result?: { nuevos: number; duplicados: number; total: number }
  error?: string
}

interface ConnectionField {
  name: string
  label: string
  type: "text" | "number" | "password" | "select" | "boolean"
  default?: string | boolean
  options?: Array<{ value: string; label: string }>
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

function scheduleLabel(schedule?: PullSchedule) {
  if (!schedule?.enabled) return "Manual"
  if (schedule.mode === "weekly") {
    const days = (schedule.weekdays || []).map(day => WEEKDAYS.find(item => item.value === day)?.label).filter(Boolean).join(", ")
    return `${days || "Días definidos"}${schedule.scheduled_time ? ` · ${schedule.scheduled_time.slice(0, 5)}` : ""}`
  }
  return `Cada ${schedule.interval_minutes} min`
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
  const [schedule, setSchedule] = useState<PullSchedule>({ enabled: false, mode: "interval", interval_minutes: 60, weekdays: [], scheduled_time: null, start_date: null, end_date: null, window_start: null, window_end: null })
  const [savingSchedule, setSavingSchedule] = useState(false)
  const [pullJob, setPullJob] = useState<PullJob | null>(null)
  const [deviceUsers, setDeviceUsers] = useState<TerminalDeviceUser[]>([])
  const [deviceUsersLimit, setDeviceUsersLimit] = useState<number | null>(null)
  const [loadingDeviceUsers, setLoadingDeviceUsers] = useState(false)
  const [syncingNames, setSyncingNames] = useState(false)
  const [terminalToDelete, setTerminalToDelete] = useState<Terminal | null>(null)
  const [clearMemoryAfterPull, setClearMemoryAfterPull] = useState(false)
  const [pointerDate, setPointerDate] = useState("")
  const [settingPointer, setSettingPointer] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [termRes, parserRes] = await Promise.all([
        api.get("/api/terminals/"),
        api.get("/api/import/parsers")
      ])
      const nextTerminals = (termRes.data.terminals || []) as Terminal[]
      setTerminals(nextTerminals)
      // La primera terminal queda seleccionada al abrir el módulo. Si el
      // usuario ya eligió otra y sigue existiendo, se conserva su selección.
      setSelectedTerminalId(currentId => (
        currentId && nextTerminals.some(terminal => terminal.id === currentId)
          ? currentId
          : nextTerminals[0]?.id ?? null
      ))
      
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

  function selectTerminal(terminalId: number) {
    setSelectedTerminalId(terminalId)
    setDeviceUsers([])
    setDeviceUsersLimit(null)
  }

  function openAdd() { 
    const selected = parsers[0]
    const defaults = Object.fromEntries(
      (selected?.connection_fields || []).map(field => [field.name, field.default ?? ""])
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
    try {
      await api.delete(`/api/terminals/${t.id}`)
      if (selectedTerminalId === t.id) setSelectedTerminalId(null)
      setTerminalToDelete(null)
      load()
    } catch (e) {
      alert(getErrorMessage(e, "Error al eliminar la terminal."))
    }
  }

  async function testConnection(id: number) {
    setTestingId(id)
    try {
      const res = await api.post(`/api/terminals/${id}/test`)
      const details: { label: string; value: string }[] = res.data.details || []
      alert(["✅ Conexión exitosa.", ...details.map(item => `${item.label}: ${item.value}`)].join("\n"))
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

  async function setAttendancePointer(t: Terminal) {
    if (!pointerDate) return
    const shown = pointerDate.split("-").reverse().join("/")
    if (!window.confirm(`La terminal volverá a entregar los registros desde el ${shown}. Los que ya están en SRTime se cuentan como duplicados. ¿Continuar?`)) return
    setSettingPointer(true)
    try {
      await api.post(`/api/terminals/${t.id}/pointer`, { since: pointerDate })
      alert(`✅ Listo. Usá "Bajar registros" para descargar desde el ${shown}.`)
      setPointerDate("")
    } catch (e) {
      alert(getErrorMessage(e, "No se pudo reposicionar la lectura de la terminal."))
    } finally {
      setSettingPointer(false)
    }
  }

  const getCapabilities = (driverName: string) => parsers.find(parser => parser.name === driverName)?.capabilities || {}

  async function pollPullJob(terminalId: number, jobId: string) {
    try {
      const { data } = await api.get(`/api/terminals/${terminalId}/pull/jobs/${jobId}`)
      const next = { ...data, terminalId } as PullJob
      setPullJob(next)
      if (next.state === "queued" || next.state === "running") {
        window.setTimeout(() => { void pollPullJob(terminalId, jobId) }, 700)
      } else {
        setPullingId(null)
        if (next.state === "completed") alert(`✅ Descarga finalizada. ${next.result?.nuevos || 0} nuevos, ${next.result?.duplicados || 0} duplicados.`)
        else alert(next.error || "La descarga no pudo completarse.")
        load()
      }
    } catch (e) {
      setPullingId(null)
      setPullJob(null)
      alert(getErrorMessage(e, "No se pudo consultar el estado de descarga."))
    }
  }

  async function pullLogs(t: Terminal) {
    setPullingId(t.id)
    try {
      const { data } = await api.post(`/api/terminals/${t.id}/pull/jobs`, {
        clear_device_memory: clearMemoryAfterPull,
      })
      setPullJob({ ...data, terminalId: t.id })
      void pollPullJob(t.id, data.id)
    } catch (e) {
      alert(getErrorMessage(e, "No se pudieron descargar los movimientos pendientes."))
      load()
      setPullingId(null)
    }
  }

  async function loadDeviceUsers(t: Terminal) {
    setLoadingDeviceUsers(true)
    try {
      const { data } = await api.get(`/api/terminals/${t.id}/device-users`)
      setDeviceUsers(data.users || [])
      setDeviceUsersLimit(data.name_max_bytes || null)
    } catch (e) {
      alert(getErrorMessage(e, "No se pudieron leer los usuarios de la terminal."))
    } finally {
      setLoadingDeviceUsers(false)
    }
  }

  async function syncNames(t: Terminal) {
    setSyncingNames(true)
    try {
      const { data } = await api.post(`/api/terminals/${t.id}/sync-user-names`)
      alert(`✅ Perfiles sincronizados: ${data.updated} actualizados de ${data.matched} empleados vinculados. Privilegios: ${data.privilege_updated || 0}.`)
      await loadDeviceUsers(t)
    } catch (e) {
      alert(getErrorMessage(e, "No se pudieron sincronizar los perfiles de terminal."))
    } finally {
      setSyncingNames(false)
    }
  }

  function openSchedule(t: Terminal) {
    const saved = t.pull_schedule || { enabled: false, mode: "interval", interval_minutes: 60, weekdays: [], scheduled_time: null, start_date: null, end_date: null, window_start: null, window_end: null }
    setSchedule({ ...saved, mode: saved.mode || "interval", interval_minutes: saved.interval_minutes || 60, weekdays: saved.weekdays || [] })
    setScheduleTerminal(t)
    setError("")
  }

  async function saveSchedule() {
    if (!scheduleTerminal) return
    if (schedule.enabled && schedule.mode === "interval" && (!schedule.interval_minutes || schedule.interval_minutes < 1)) {
      setError("El intervalo debe ser de al menos un minuto.")
      return
    }
    if (schedule.enabled && schedule.mode === "weekly" && (!schedule.weekdays?.length || !schedule.scheduled_time)) {
      setError("Seleccione uno o más días y la hora de descarga.")
      return
    }
    setSavingSchedule(true); setError("")
    try {
      await api.put(`/api/terminals/${scheduleTerminal.id}/pull-schedule`, {
        enabled: schedule.enabled,
        mode: schedule.mode || "interval",
        interval_minutes: schedule.enabled && schedule.mode === "interval" ? Number(schedule.interval_minutes) : null,
        weekdays: schedule.enabled && schedule.mode === "weekly" ? schedule.weekdays : null,
        scheduled_time: schedule.enabled && schedule.mode === "weekly" ? schedule.scheduled_time || null : null,
        start_date: schedule.enabled ? schedule.start_date || null : null,
        end_date: schedule.enabled ? schedule.end_date || null : null,
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
                    (selected?.connection_fields || []).map(field => [field.name, field.default ?? ""])
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
              {field.type === "select" ? (
                <select value={String(current.connection_params[field.name] ?? field.default ?? "")} onChange={e => setCurrent(p => ({ ...p, connection_params: { ...p.connection_params, [field.name]: e.target.value } }))}>
                  {(field.options || []).map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              ) : field.type === "boolean" ? (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    id={`terminal-field-${field.name}`}
                    type="checkbox"
                    checked={Boolean(current.connection_params[field.name] ?? field.default ?? false)}
                    onChange={e => setCurrent(p => ({ ...p, connection_params: { ...p.connection_params, [field.name]: e.target.checked } }))}
                    style={{ width: "auto" }}
                  />
                  <label htmlFor={`terminal-field-${field.name}`} style={{ margin: 0, cursor: "pointer", fontWeight: 400 }}>Sí</label>
                </div>
              ) : (
                <input
                  type={field.type}
                  placeholder={field.type === "password" && modal === "edit" ? "Dejar vacío para conservar" : undefined}
                  value={String(current.connection_params[field.name] ?? "")}
                  onChange={e => setCurrent(p => ({
                    ...p,
                    connection_params: { ...p.connection_params, [field.name]: e.target.value },
                  }))}
                />
              )}
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
            La descarga automática solo guarda movimientos pendientes de procesar. El procesamiento de asistencias se mantiene manual.
          </p>
          <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <input id="schedule-enabled" type="checkbox" checked={schedule.enabled} onChange={e => setSchedule(p => ({ ...p, enabled: e.target.checked }))} style={{ width: "auto" }} />
            <label htmlFor="schedule-enabled" style={{ margin: 0, cursor: "pointer" }}>Descarga automática activa</label>
          </div>
          {schedule.enabled && <>
            <Field label="Ciclo de descarga:">
              <select value={schedule.mode || "interval"} onChange={e => setSchedule(p => ({ ...p, mode: e.target.value as PullSchedule["mode"] }))}>
                <option value="interval">Cada intervalo</option>
                <option value="weekly">Días definidos</option>
              </select>
            </Field>
            {schedule.mode === "interval" ? <>
              <Field label="Intervalo (minutos):">
                <input type="number" min="1" value={schedule.interval_minutes || 60} onChange={e => setSchedule(p => ({ ...p, interval_minutes: Number(e.target.value) }))} />
              </Field>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <Field label="Desde (opcional):"><input type="time" value={schedule.window_start || ""} onChange={e => setSchedule(p => ({ ...p, window_start: e.target.value || null }))} /></Field>
                <Field label="Hasta (opcional):"><input type="time" value={schedule.window_end || ""} onChange={e => setSchedule(p => ({ ...p, window_end: e.target.value || null }))} /></Field>
              </div>
            </> : <>
              <Field label="Hora de descarga:"><input type="time" required value={schedule.scheduled_time || ""} onChange={e => setSchedule(p => ({ ...p, scheduled_time: e.target.value || null }))} /></Field>
              <Field label="Días de ejecución:">
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {WEEKDAYS.map(day => <label key={day.value} className="btn" style={{ cursor: "pointer", padding: "6px 8px", background: schedule.weekdays?.includes(day.value) ? "var(--primary)" : undefined, color: schedule.weekdays?.includes(day.value) ? "white" : undefined }}>
                    <input type="checkbox" checked={schedule.weekdays?.includes(day.value) || false} onChange={() => setSchedule(p => ({ ...p, weekdays: p.weekdays?.includes(day.value) ? p.weekdays.filter(value => value !== day.value) : [...(p.weekdays || []), day.value] }))} style={{ display: "none" }} />{day.label}
                  </label>)}
                </div>
              </Field>
            </>}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <Field label="Desde fecha (opcional):"><input type="date" value={schedule.start_date || ""} onChange={e => setSchedule(p => ({ ...p, start_date: e.target.value || null }))} /></Field>
              <Field label="Hasta fecha (opcional):"><input type="date" min={schedule.start_date || undefined} value={schedule.end_date || ""} onChange={e => setSchedule(p => ({ ...p, end_date: e.target.value || null }))} /></Field>
            </div>
          </>}
          {error && <p style={{ color: "var(--status-error)", fontSize: 13 }}>⚠ {error}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 15 }}>
            <button className="btn btn-primary" disabled={savingSchedule} onClick={saveSchedule}>{savingSchedule ? "Guardando..." : "Guardar automatización"}</button>
            <button className="btn" onClick={() => setScheduleTerminal(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      {terminalToDelete && (
        <AppDialog
          title="Eliminar terminal"
          onClose={() => setTerminalToDelete(null)}
          actions={[
            { label: "Cancelar", onClick: () => setTerminalToDelete(null) },
            { label: "Eliminar terminal", variant: "danger", onClick: () => handleDelete(terminalToDelete) },
          ]}
        >
          <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>
            ¿Está seguro que quiere eliminar la terminal?
          </p>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 8 }}>
            Esta acción elimina el registro de SRTime. No borra la memoria física del equipo.
          </p>
        </AppDialog>
      )}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openAdd}><Plus size={15} /> Registrar Terminal</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /></button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando terminales...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead><tr><th>Estado</th><th>Ubicación</th><th>Tecnología</th><th>Red</th><th>Serie</th><th>Última descarga</th><th>Automatización</th><th>Acciones</th></tr></thead>
              <tbody>
                {paginated.length === 0 && <tr><td colSpan={8} style={{ textAlign: "center", opacity: .5, padding: 28 }}>No hay terminales conectadas. Registra tu equipo biométrico arriba.</td></tr>}
                {paginated.map(t => <tr key={t.id} onClick={() => selectTerminal(t.id)} style={{ cursor: "pointer", opacity: t.is_active ? 1 : .55, background: selectedTerminalId === t.id ? "var(--bg-highlight)" : undefined }}>
                  <td><span className={`badge ${t.is_active ? "badge-ok" : "badge-error"}`}><Activity size={12} /> {t.is_active ? "Activa" : "Inactiva"}</span></td>
                  <td><strong>{t.name}</strong></td>
                  <td><Fingerprint size={13} style={{ verticalAlign: "-2px" }} /> {t.driver_name}</td>
                  <td>{String(t.connection_params?.ip || t.ip || "—")}:{String(t.connection_params?.port || t.port || "—")}</td>
                  <td style={{ fontFamily: "monospace" }}>{t.serial_number || "—"}</td>
                  <td>{t.last_sync ? new Date(t.last_sync).toLocaleString() : "Nunca"}</td>
                  <td>{scheduleLabel(t.pull_schedule)}</td>
                  <td onClick={event => event.stopPropagation()}>
                    <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                      <button className="btn" title="Conectar y probar; la conexión se cierra al finalizar" onClick={() => testConnection(t.id)} disabled={testingId === t.id || !t.is_active}><Wifi size={13} /></button>
                      <button className="btn" title="Actualizar fecha y hora" onClick={() => syncTime(t.id)} disabled={syncingId === t.id || !t.is_active}><Clock size={13} /></button>
                      <button className="btn btn-primary" title="Bajar registros y desconectar al finalizar" onClick={() => pullLogs(t)} disabled={pullingId === t.id || !t.is_active}><Download size={13} /></button>
                      <button className="btn" title="Editar terminal" onClick={() => openEdit(t)}><Pencil size={13} /></button>
                      <button className="btn btn-danger" title="Eliminar terminal" onClick={() => setTerminalToDelete(t)}><Trash2 size={13} /></button>
                    </div>
                  </td>
                </tr>)}
              </tbody>
            </table>
          </div>
          {selectedTerminal && (() => {
            const t = selectedTerminal
            const scheduleState = t.pull_schedule
            const capabilities = getCapabilities(t.driver_name)
            const isPulling = pullJob?.terminalId === t.id && (pullJob.state === "queued" || pullJob.state === "running")
            const statusColor = scheduleState?.last_status === "error" ? "var(--status-error)" : "var(--status-ok)"
            return <section className="table-wrapper" style={{ marginTop: 18, padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div><strong style={{ fontSize: 17 }}>{t.name}</strong><div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>Administración de terminal · {t.driver_name}</div></div>
                <button className="btn" onClick={() => setSelectedTerminalId(null)}><X size={14} /> Cerrar</button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, margin: "18px 0", fontSize: 13 }}>
                <div><span style={{ color: "var(--text-secondary)" }}>Última descarga</span><br />{t.last_sync ? new Date(t.last_sync).toLocaleString() : "Nunca"}</div>
                <div><span style={{ color: "var(--text-secondary)" }}>Estado automático</span><br /><span style={{ color: scheduleState?.enabled ? statusColor : "var(--text-secondary)" }}>{scheduleLabel(scheduleState)}</span></div>
                <div><span style={{ color: "var(--text-secondary)" }}>Próxima descarga</span><br />{scheduleState?.next_pull_at ? new Date(scheduleState.next_pull_at).toLocaleString() : "—"}</div>
              </div>
              {scheduleState?.last_error && <p style={{ color: "var(--status-error)", fontSize: 12, margin: "0 0 12px" }}>Último error: {scheduleState.last_error}</p>}
              {isPulling && <div style={{ margin: "0 0 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-secondary)", marginBottom: 5 }}><span>{pullJob.message}</span><span>{pullJob.total ? `${pullJob.percent}%` : "Preparando"}</span></div>
                <div style={{ height: 8, borderRadius: 5, background: "var(--bg-main)", overflow: "hidden" }}><div style={{ height: "100%", width: `${pullJob.percent || 2}%`, background: "var(--primary)", transition: "width .25s" }} /></div>
              </div>}
              {capabilities.clear_attendance_memory && (
                <label className="checkbox-inline" style={{ marginBottom: 12 }}>
                  <input type="checkbox" checked={clearMemoryAfterPull} onChange={event => setClearMemoryAfterPull(event.target.checked)} />
                  Borrar memoria de la terminal después de bajar registros
                </label>
              )}
              <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
                <button className="btn btn-primary" onClick={() => pullLogs(t)} disabled={pullingId === t.id || !t.is_active}><Download size={14} /> {pullingId === t.id ? "Descargando..." : "Bajar registros"}</button>
                <button className="btn" onClick={() => openSchedule(t)}><CalendarClock size={14} /> Programar</button>
                <button className="btn" onClick={() => testConnection(t.id)} disabled={testingId === t.id || syncingId === t.id || pullingId === t.id || !t.is_active}><Wifi size={14} /> {testingId === t.id ? "Conectando..." : "Conectar"}</button>
                <button className="btn" onClick={() => syncTime(t.id)} disabled={testingId === t.id || syncingId === t.id || pullingId === t.id || !t.is_active}><Clock size={14} /> {syncingId === t.id ? "Sincronizando..." : "Reloj"}</button>
              </div>
              {capabilities.attendance_pointer && <section style={{ marginTop: 18, paddingTop: 16, borderTop: "1px solid var(--border-color)" }}>
                <strong><History size={15} style={{ verticalAlign: "-2px" }} /> Volver a bajar registros</strong>
                <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 3 }}>La terminal vuelve a entregar las marcas desde la fecha elegida en la próxima descarga. Las que ya están en SRTime se cuentan como duplicadas.</div>
                <div style={{ display: "flex", gap: 7, alignItems: "center", flexWrap: "wrap", marginTop: 10 }}>
                  <label style={{ fontSize: 13 }}>Desde: <input type="date" value={pointerDate} max={new Date().toLocaleDateString("en-CA")} onChange={event => setPointerDate(event.target.value)} /></label>
                  <button className="btn" onClick={() => setAttendancePointer(t)} disabled={!pointerDate || settingPointer || pullingId === t.id || !t.is_active}><History size={14} /> {settingPointer ? "Aplicando..." : "Volver a bajar desde esta fecha"}</button>
                </div>
              </section>}
              {capabilities.terminal_users && <section style={{ marginTop: 18, paddingTop: 16, borderTop: "1px solid var(--border-color)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                  <div><strong><Users size={15} style={{ verticalAlign: "-2px" }} /> Usuarios de terminal</strong><div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 3 }}>UID e ID pertenecen al reloj. SRTime sincroniza nombre y privilegio USER/ADMIN desde Empleados.</div></div>
                  <div style={{ display: "flex", gap: 7 }}>
                    <button className="btn" onClick={() => loadDeviceUsers(t)} disabled={loadingDeviceUsers}><Download size={14} /> {loadingDeviceUsers ? "Leyendo..." : "Bajar usuarios"}</button>
                    {capabilities.terminal_user_name_sync && <button className="btn btn-primary" onClick={() => syncNames(t)} disabled={syncingNames || !t.is_active}><Upload size={14} /> {syncingNames ? "Subiendo..." : "Subir usuarios"}</button>}
                  </div>
                </div>
                {deviceUsers.length > 0 && <div className="table-wrapper" style={{ marginTop: 12, maxHeight: 240, overflow: "auto" }}><table className="data-table"><thead><tr><th>UID</th><th>ID</th><th>Nombre en terminal</th><th>Privilegio de terminal</th></tr></thead><tbody>{deviceUsers.map(user => <tr key={`${user.uid}-${user.user_id}`}><td>{user.uid}</td><td>{user.user_id}</td><td>{user.name}</td><td>{user.privilege_label}</td></tr>)}</tbody></table></div>}
                {deviceUsersLimit && <p style={{ color: "var(--text-secondary)", fontSize: 12, margin: "9px 0 0" }}>Límite de nombre informado por la terminal: {deviceUsersLimit} bytes.</p>}
              </section>}
            </section>
          })()}
          <Pagination total={terminals.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
        </>
      )}
    </div>
  )
}
