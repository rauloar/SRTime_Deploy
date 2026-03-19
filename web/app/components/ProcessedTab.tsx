"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"

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
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 8, padding: 28, minWidth: 380, boxShadow: "var(--shadow)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{title}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, cursor: "pointer", color: "var(--fg)" }}>✕</button>
        </div>
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
  const [records, setRecords] = useState<ProcessedRecord[]>([])
  const [users, setUsers]     = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [dateStart, setDateStart] = useState(daysAgo(30))
  const [dateEnd, setDateEnd]     = useState(today())
  const [empFilter, setEmpFilter] = useState("")
  const [selected, setSelected]   = useState<ProcessedRecord | null>(null)
  const [justIn, setJustIn]       = useState("08:00")
  const [justOut, setJustOut]     = useState("17:00")
  const [justText, setJustText]   = useState("")
  const [saving, setSaving]       = useState(false)
  const [justError, setJustError] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    const [rec, u] = await Promise.all([
      api.get("/api/processed/", { params: { date_start: dateStart, date_end: dateEnd, limit: 1000 } }),
      api.get("/api/users/?limit=500")
    ])
    setRecords(rec.data); setUsers(u.data); setLoading(false)
  }, [api, dateStart, dateEnd])

  useEffect(() => { load() }, [load])

  const nameOf = (emp_id: number) => {
    const u = users.find(x => x.id === emp_id)
    if (!u) return `#${emp_id}`
    return `${u.last_name || ""}, ${u.first_name || ""}`.replace(/^,\s*/, "")
  }
  const filtered = records.filter(r => !empFilter || nameOf(r.employee_id).toLowerCase().includes(empFilter.toLowerCase()))

  function openJustify(r: ProcessedRecord) {
    setSelected(r)
    setJustIn(r.first_in ? r.first_in.slice(0, 5) : "08:00")
    setJustOut(r.last_out ? r.last_out.slice(0, 5) : "17:00")
    setJustText(r.justification || "")
    setJustError("")
  }

  async function saveJustify() {
    if (!justText.trim()) { setJustError("Debe explicar el motivo de la justificación."); return }
    setSaving(true)
    try {
      await api.patch(`/api/processed/${selected!.id}/justify`, { first_in: justIn, last_out: justOut, justification: justText })
      setSelected(null); load()
    } catch (e: any) {
      setJustError(e?.response?.data?.detail || "Error al guardar.")
    } finally { setSaving(false) }
  }

  return (
    <div className="tab-content">
      {selected && (
        <Modal title="Justificar Asistencia" onClose={() => setSelected(null)}>
          <p style={{ marginBottom: 12, fontSize: 13, opacity: 0.7 }}>Fecha: {selected.date} — {nameOf(selected.employee_id)}</p>
          <Field label="Entrada Real / Justificada:">
            <input type="time" value={justIn} onChange={e => setJustIn(e.target.value)} />
          </Field>
          <Field label="Salida Real / Justificada:">
            <input type="time" value={justOut} onChange={e => setJustOut(e.target.value)} />
          </Field>
          <Field label="Razón de Justificación (obligatorio):">
            <textarea value={justText} onChange={e => setJustText(e.target.value)} rows={3}
              style={{ resize: "vertical", padding: 8, border: "1px solid var(--border)", borderRadius: 4, background: "var(--bg)", color: "var(--fg)", fontFamily: "inherit", fontSize: 13 }}
            />
          </Field>
          {justError && <p style={{ color: "#c0392b", fontSize: 13, marginBottom: 10 }}>⚠️ {justError}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button className="btn btn-primary" onClick={saveJustify} disabled={saving}>{saving ? "Guardando..." : "Guardar Justificación"}</button>
            <button className="btn" onClick={() => setSelected(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="filter-bar" style={{ marginBottom: 10 }}>
        <label>Desde:</label>
        <input type="date" value={dateStart} onChange={e => setDateStart(e.target.value)} />
        <label>Hasta:</label>
        <input type="date" value={dateEnd} onChange={e => setDateEnd(e.target.value)} />
        <label>Empleado:</label>
        <input type="text" value={empFilter} onChange={e => setEmpFilter(e.target.value)} placeholder="Filtrar nombre..." style={{ width: 180 }} />
        <button className="btn" onClick={load} disabled={loading}>↻ Actualizar</button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando asistencias...</p> : (
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Empleado</th><th>Fecha</th><th>Primera Entrada</th><th>Última Salida</th>
                <th>Horas Totales</th><th>Tardanza (Min)</th><th>Salida Ant. (Min)</th>
                <th>Hs Extra (Min)</th><th>Estado</th><th>Justificación</th><th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan={11} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin registros en el rango seleccionado</td></tr>}
              {filtered.map(r => (
                <tr key={r.id}>
                  <td>{nameOf(r.employee_id)}</td>
                  <td>{r.date}</td>
                  <td>{r.first_in || "--:--"}</td>
                  <td>{r.last_out || "--:--"}</td>
                  <td>{r.total_hours} hs</td>
                  <td style={{ color: r.tardiness_minutes > 0 ? "#c0392b" : undefined }}>{r.tardiness_minutes}</td>
                  <td style={{ color: r.early_departure_minutes > 0 ? "#e67e22" : undefined }}>{r.early_departure_minutes}</td>
                  <td style={{ color: r.overtime_minutes > 0 ? "#27ae60" : undefined }}>{r.overtime_minutes}</td>
                  <td><span className={`badge ${STATUS_BADGE[r.status] || "badge-error"}`}>{r.status}</span></td>
                  <td style={{ fontSize: 12, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.justification || <span style={{ opacity: 0.4 }}>—</span>}
                  </td>
                  <td>
                    <button className="btn" style={{ padding: "4px 10px", fontSize: 12, whiteSpace: "nowrap" }} onClick={() => openJustify(r)}>
                      🛠️ Justificar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: 12, opacity: 0.6, marginTop: 8 }}>{filtered.length} registros</p>
        </div>
      )}
    </div>
  )
}
