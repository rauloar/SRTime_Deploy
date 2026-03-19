"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"

interface Shift { id: number; name: string; expected_in: string; expected_out: string; grace_period_minutes: number }
const EMPTY_SHIFT = { name: "", expected_in: "09:00", expected_out: "18:00", grace_period_minutes: 15 }

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 8, padding: 28, minWidth: 360, boxShadow: "var(--shadow)" }}>
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

export default function ShiftsTab() {
  const { api } = useAuth()
  const [shifts, setShifts] = useState<Shift[]>([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState<"add" | "edit" | null>(null)
  const [current, setCurrent] = useState<any>(EMPTY_SHIFT)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    const res = await api.get("/api/shifts/")
    setShifts(res.data); setLoading(false)
  }, [api])

  useEffect(() => { load() }, [load])

  function openAdd() { setCurrent({ ...EMPTY_SHIFT }); setError(""); setModal("add") }
  function openEdit(s: Shift) { setCurrent({ ...s, expected_in: s.expected_in.slice(0,5), expected_out: s.expected_out.slice(0,5) }); setError(""); setModal("edit") }

  async function handleSave() {
    if (!current.name?.trim()) { setError("El nombre del turno es obligatorio."); return }
    setSaving(true); setError("")
    try {
      const payload = { name: current.name, expected_in: current.expected_in, expected_out: current.expected_out, grace_period_minutes: Number(current.grace_period_minutes) }
      if (modal === "add") await api.post("/api/shifts/", payload)
      else await api.put(`/api/shifts/${current.id}`, payload)
      setModal(null); load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Error al guardar.")
    } finally { setSaving(false) }
  }

  async function handleDelete(s: Shift) {
    if (!confirm(`¿Eliminar el turno '${s.name}'?\nEsto podría afectar los cálculos de los empleados que lo tengan asignado.`)) return
    await api.delete(`/api/shifts/${s.id}`)
    load()
  }

  return (
    <div className="tab-content">
      {(modal === "add" || modal === "edit") && (
        <Modal title={modal === "add" ? "Crear Nuevo Turno" : "Editar Turno"} onClose={() => setModal(null)}>
          <Field label="Nombre del Turno (ej: Mañana):">
            <input value={current.name} onChange={e => setCurrent((p: any) => ({ ...p, name: e.target.value }))} />
          </Field>
          <Field label="Hora de Entrada:">
            <input type="time" value={current.expected_in} onChange={e => setCurrent((p: any) => ({ ...p, expected_in: e.target.value }))} />
          </Field>
          <Field label="Hora de Salida:">
            <input type="time" value={current.expected_out} onChange={e => setCurrent((p: any) => ({ ...p, expected_out: e.target.value }))} />
          </Field>
          <Field label="Minutos de Tolerancia (Tardanza):">
            <input type="number" min="0" value={current.grace_period_minutes} onChange={e => setCurrent((p: any) => ({ ...p, grace_period_minutes: e.target.value }))} />
          </Field>
          {error && <p style={{ color: "#c0392b", fontSize: 13, marginBottom: 10 }}>⚠️ {error}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button>
            <button className="btn" onClick={() => setModal(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="toolbar" style={{ marginBottom: 8 }}>
        <button className="btn btn-primary" onClick={openAdd}>+ Nuevo Turno</button>
        <button className="btn" onClick={load} disabled={loading}>↻ Actualizar</button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando turnos...</p> : (
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr><th>#</th><th>Nombre</th><th>Hora Entrada</th><th>Hora Salida</th><th>Tolerancia (Min)</th><th>Acciones</th></tr>
            </thead>
            <tbody>
              {shifts.length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin turnos configurados</td></tr>}
              {shifts.map(s => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.expected_in}</td>
                  <td>{s.expected_out}</td>
                  <td>{s.grace_period_minutes} min</td>
                  <td style={{ display: "flex", gap: 6 }}>
                    <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => openEdit(s)}>✏️ Editar</button>
                    <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => handleDelete(s)}>🗑️ Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
