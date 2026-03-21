"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Plus, RefreshCw, Pencil, Trash2, X } from "lucide-react"
import Pagination from "./Pagination"

interface Shift { id: number; name: string; expected_in: string; expected_out: string; grace_period_minutes: number }
interface ShiftForm { id?: number; name: string; expected_in: string; expected_out: string; grace_period_minutes: number }
const EMPTY_SHIFT = { name: "", expected_in: "09:00", expected_out: "18:00", grace_period_minutes: 15 }

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

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}

export default function ShiftsTab() {
  const { api } = useAuth()
  const [shifts, setShifts]     = useState<Shift[]>([])
  const [loading, setLoading]   = useState(true)
  const [modal, setModal]       = useState<"add" | "edit" | null>(null)
  const [current, setCurrent]   = useState<ShiftForm>(EMPTY_SHIFT)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState("")
  const [page, setPage]         = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const load = useCallback(async () => {
    setLoading(true)
    const res = await api.get("/api/shifts/")
    setShifts(res.data); setLoading(false)
  }, [api])

  useEffect(() => { load() }, [load])

  const paginated = shifts.slice((page - 1) * pageSize, page * pageSize)

  function openAdd() { setCurrent({ ...EMPTY_SHIFT }); setError(""); setModal("add") }
  function openEdit(s: Shift) {
    setCurrent({ ...s, expected_in: s.expected_in.slice(0, 5), expected_out: s.expected_out.slice(0, 5) })
    setError(""); setModal("edit")
  }

  async function handleSave() {
    if (!current.name?.trim()) { setError("El nombre del turno es obligatorio."); return }
    setSaving(true); setError("")
    try {
      const payload = { name: current.name, expected_in: current.expected_in, expected_out: current.expected_out, grace_period_minutes: Number(current.grace_period_minutes) }
      if (modal === "add") await api.post("/api/shifts/", payload)
      else await api.put(`/api/shifts/${current.id}`, payload)
      setModal(null); load()
    } catch (e: unknown) { setError(getErrorMessage(e, "Error al guardar."))
    } finally { setSaving(false) }
  }

  async function handleDelete(s: Shift) {
    if (!confirm(`¿Eliminar el turno '${s.name}'?`)) return
    await api.delete(`/api/shifts/${s.id}`); load()
  }

  return (
    <div>
      {(modal === "add" || modal === "edit") && (
        <Modal title={modal === "add" ? "Crear Nuevo Turno" : "Editar Turno"} onClose={() => setModal(null)}>
          <Field label="Nombre del Turno:"><input value={current.name} onChange={e => setCurrent(p => ({ ...p, name: e.target.value }))} /></Field>
          <Field label="Hora de Entrada:"><input type="time" value={current.expected_in} onChange={e => setCurrent(p => ({ ...p, expected_in: e.target.value }))} /></Field>
          <Field label="Hora de Salida:"><input type="time" value={current.expected_out} onChange={e => setCurrent(p => ({ ...p, expected_out: e.target.value }))} /></Field>
          <Field label="Minutos de Tolerancia:"><input type="number" min="0" value={current.grace_period_minutes} onChange={e => setCurrent(p => ({ ...p, grace_period_minutes: Number(e.target.value) }))} /></Field>
          {error && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {error}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button>
            <button className="btn" onClick={() => setModal(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openAdd}><Plus size={15} /> Nuevo Turno</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /></button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando turnos...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr><th>#</th><th>Nombre</th><th>Hora Entrada</th><th>Hora Salida</th><th>Tolerancia (Min)</th><th>Acciones</th></tr>
              </thead>
              <tbody>
                {paginated.length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin turnos configurados</td></tr>}
                {paginated.map(s => (
                  <tr key={s.id}>
                    <td style={{ opacity: 0.5 }}>{s.id}</td>
                    <td><strong>{s.name}</strong></td>
                    <td>{s.expected_in}</td>
                    <td>{s.expected_out}</td>
                    <td>{s.grace_period_minutes} min</td>
                    <td style={{ display: "flex", gap: 6 }}>
                      <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => openEdit(s)}><Pencil size={13} /> Editar</button>
                      <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => handleDelete(s)}><Trash2 size={13} /> Eliminar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={shifts.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
        </>
      )}
    </div>
  )
}
