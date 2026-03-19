"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import { RefreshCw, Wrench, X, Play, RotateCcw } from "lucide-react"
import Pagination from "./Pagination"

interface ProcessedRecord {
  id: number; employee_id: number; date: string;
  first_in: string | null; last_out: string | null;
  total_hours: number; tardiness_minutes: number;
  early_departure_minutes: number; overtime_minutes: number;
  status: string; justification: string | null
}
interface User { id: number; first_name: string | null; last_name: string | null }

const STATUS_BADGE: Record<string, string> = {
  OK: "badge-ok", INCOMPLETO: "badge-incompleto",
  JUSTIFICADO: "badge-justificado", ERROR: "badge-error"
}
function today() { return new Date().toISOString().slice(0, 10) }
function daysAgo(n: number) { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10) }

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop">
      <div className="modal-box">
        <div className="modal-title"><span>{title}</span><button className="modal-close" onClick={onClose}><X size={16} /></button></div>
        {children}
      </div>
    </div>
  )
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="form-group"><label>{label}</label>{children}</div>
}

export default function ProcessedTab() {
  const { api } = useAuth()
  const [records, setRecords]   = useState<ProcessedRecord[]>([])
  const [users, setUsers]       = useState<User[]>([])
  const [loading, setLoading]   = useState(true)
  const [dateStart, setDateStart] = useState(daysAgo(30))
  const [dateEnd, setDateEnd]     = useState(today())
  const [empFilter, setEmpFilter] = useState("")
  const [selected, setSelected]   = useState<ProcessedRecord | null>(null)
  const [justIn, setJustIn]       = useState("08:00")
  const [justOut, setJustOut]     = useState("17:00")
  const [justText, setJustText]   = useState("")
  const [saving, setSaving]       = useState(false)
  const [justError, setJustError] = useState("")
  const [actionMsg, setActionMsg] = useState("")
  const [processing, setProcessing] = useState<"pending" | "all" | null>(null)
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null)
  const [page, setPage]           = useState(1)
  const [pageSize, setPageSize]   = useState(50)

  const load = useCallback(async () => {
    setLoading(true)
    const [rec, u] = await Promise.all([
      api.get("/api/processed/", { params: { date_start: dateStart, date_end: dateEnd, limit: 5000 } }),
      api.get("/api/users/?limit=2000")
    ])
    setRecords(rec.data); setUsers(u.data); setLoading(false)
  }, [api, dateStart, dateEnd])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [empFilter, dateStart, dateEnd])

  const nameOf = (emp_id: number) => {
    const u = users.find(x => x.id === emp_id)
    if (!u) return `#${emp_id}`
    return `${u.last_name || ""}, ${u.first_name || ""}`.replace(/^,\s*/, "")
  }

  const filtered = records.filter(r => !empFilter || nameOf(r.employee_id).toLowerCase().includes(empFilter.toLowerCase()))
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)

  useEffect(() => {
    if (selectedRowId == null) return
    const exists = records.some(r => r.id === selectedRowId)
    if (!exists) setSelectedRowId(null)
  }, [records, selectedRowId])

  function openJustify(r: ProcessedRecord) {
    setSelected(r)
    setJustIn(r.first_in ? r.first_in.slice(0, 5) : "08:00")
    setJustOut(r.last_out ? r.last_out.slice(0, 5) : "17:00")
    setJustText(r.justification || "")
    setJustError("")
  }

  function justifySelectedRow() {
    if (selectedRowId == null) {
      setActionMsg("Selecciona una fila para justificar.")
      return
    }
    const rec = records.find(r => r.id === selectedRowId)
    if (!rec) {
      setActionMsg("La fila seleccionada ya no está disponible.")
      return
    }
    openJustify(rec)
  }

  async function runProcess(mode: "pending" | "all") {
    setProcessing(mode)
    setActionMsg("")
    try {
      const endpoint = mode === "pending" ? "/api/processed/process-pending" : "/api/processed/reprocess-all"
      const res = await api.post(endpoint)
      await load()
      setActionMsg(`Proceso completado: ${res.data.processed_days} flujos diarios procesados.`)
    } catch (e: any) {
      setActionMsg(e?.response?.data?.detail || "Error al ejecutar el proceso")
    } finally {
      setProcessing(null)
    }
  }

  async function saveJustify() {
    if (!justText.trim()) { setJustError("Debe explicar el motivo de la justificación."); return }
    setSaving(true)
    try {
      await api.patch(`/api/processed/${selected!.id}/justify`, { first_in: justIn, last_out: justOut, justification: justText })
      setSelected(null); load()
    } catch (e: any) { setJustError(e?.response?.data?.detail || "Error al guardar.")
    } finally { setSaving(false) }
  }

  return (
    <div>
      {selected && (
        <Modal title="Justificar Asistencia" onClose={() => setSelected(null)}>
          <p style={{ marginBottom: 14, fontSize: 13, color: "var(--text-secondary)" }}>{selected.date} — {nameOf(selected.employee_id)}</p>
          <Field label="Entrada Real / Justificada:"><input type="time" value={justIn} onChange={e => setJustIn(e.target.value)} /></Field>
          <Field label="Salida Real / Justificada:"><input type="time" value={justOut} onChange={e => setJustOut(e.target.value)} /></Field>
          <Field label="Razón de Justificación (obligatorio):"><textarea value={justText} onChange={e => setJustText(e.target.value)} rows={3} style={{ resize: "vertical" }} /></Field>
          {justError && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {justError}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button className="btn btn-primary" onClick={saveJustify} disabled={saving}>{saving ? "Guardando..." : "Guardar Justificación"}</button>
            <button className="btn" onClick={() => setSelected(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="filter-bar">
        <label>Desde:</label>
        <input type="date" value={dateStart} onChange={e => setDateStart(e.target.value)} />
        <label>Hasta:</label>
        <input type="date" value={dateEnd} onChange={e => setDateEnd(e.target.value)} />
        <label>Empleado:</label>
        <input type="text" value={empFilter} onChange={e => setEmpFilter(e.target.value)} placeholder="Filtrar nombre..." style={{ width: 180 }} />
        <button className="btn btn-primary" onClick={() => runProcess("pending")} disabled={processing !== null}>
          <Play size={14} /> {processing === "pending" ? "Procesando..." : "Procesar Pendientes"}
        </button>
        <button className="btn" onClick={() => runProcess("all")} disabled={processing !== null}>
          <RotateCcw size={14} /> {processing === "all" ? "Reprocesando..." : "Reprocesar Histórico Completo"}
        </button>
        <button className="btn" onClick={justifySelectedRow}>
          <Wrench size={14} /> Justificar Fila Seleccionada
        </button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /> Actualizar</button>
      </div>

      {actionMsg && <p style={{ fontSize: 13, marginBottom: 10, color: actionMsg.startsWith("Error") ? "var(--status-error)" : "var(--text-secondary)" }}>⚠ {actionMsg}</p>}

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando asistencias...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Empleado</th><th>Fecha</th><th>1ra Entrada</th><th>Última Salida</th>
                  <th>Horas</th><th>Tardanza</th><th>Sal. Ant.</th><th>Hs Extra</th>
                  <th>Estado</th><th>Justificación</th><th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {paginated.length === 0 && <tr><td colSpan={11} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin registros en el rango seleccionado</td></tr>}
                {paginated.map(r => (
                  <tr
                    key={r.id}
                    onClick={() => setSelectedRowId(r.id)}
                    style={{ cursor: "pointer", backgroundColor: selectedRowId === r.id ? "rgba(0, 120, 215, 0.10)" : undefined }}
                  >
                    <td>{nameOf(r.employee_id)}</td>
                    <td>{r.date}</td>
                    <td>{r.first_in || "--:--"}</td>
                    <td>{r.last_out || "--:--"}</td>
                    <td>{r.total_hours} hs</td>
                    <td style={{ color: r.tardiness_minutes > 0 ? "var(--status-error)" : undefined }}>{r.tardiness_minutes}</td>
                    <td style={{ color: r.early_departure_minutes > 0 ? "var(--status-warning)" : undefined }}>{r.early_departure_minutes}</td>
                    <td style={{ color: r.overtime_minutes > 0 ? "var(--status-ok)" : undefined }}>{r.overtime_minutes}</td>
                    <td><span className={`badge ${STATUS_BADGE[r.status] || "badge-error"}`}>{r.status}</span></td>
                    <td style={{ fontSize: 12, maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.justification || <span style={{ opacity: 0.35 }}>—</span>}
                    </td>
                    <td>
                      <button className="btn" style={{ padding: "4px 10px", fontSize: 12, whiteSpace: "nowrap" }} onClick={() => openJustify(r)}>
                        <Wrench size={13} /> Justificar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={filtered.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
        </>
      )}
    </div>
  )
}
