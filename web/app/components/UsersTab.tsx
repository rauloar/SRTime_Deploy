"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"

interface User { id: number; identifier: string; first_name: string | null; last_name: string | null; is_active: boolean; shift_id: number | null }
interface Shift { id: number; name: string }
const EMPTY: Partial<User> = { identifier: "", first_name: "", last_name: "", is_active: true, shift_id: null }

// ──────── MODAL OVERLAY ────────
function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 8, padding: 28, minWidth: 360, maxWidth: 480, boxShadow: "var(--shadow)" }}>
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
  return <div className="form-group">{<label>{label}</label>}{children}</div>
}

export default function UsersTab() {
  const { api } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [modal, setModal] = useState<"add" | "edit" | null>(null)
  const [current, setCurrent] = useState<Partial<User>>(EMPTY)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    const [u, s] = await Promise.all([api.get("/api/users/?limit=500"), api.get("/api/shifts/")])
    setUsers(u.data); setShifts(s.data); setLoading(false)
  }, [api])

  useEffect(() => { load() }, [load])

  const filtered = users.filter(u =>
    (u.identifier + " " + (u.first_name||"") + " " + (u.last_name||"")).toLowerCase().includes(search.toLowerCase())
  )
  const shiftName = (id: number | null) => id ? (shifts.find(s => s.id === id)?.name || "Sin Turno") : "Sin Turno"

  function openAdd() { setCurrent(EMPTY); setError(""); setModal("add") }
  function openEdit(u: User) { setCurrent({ ...u }); setError(""); setModal("edit") }
  function closeModal() { setModal(null) }

  async function handleSave() {
    if (!current.identifier?.trim()) { setError("El identificador es obligatorio."); return }
    setSaving(true); setError("")
    try {
      if (modal === "add") {
        await api.post("/api/users/", { identifier: current.identifier, first_name: current.first_name, last_name: current.last_name, is_active: current.is_active, shift_id: current.shift_id || null })
      } else {
        await api.put(`/api/users/${current.id}`, { identifier: current.identifier, first_name: current.first_name, last_name: current.last_name, is_active: current.is_active, shift_id: current.shift_id || null })
      }
      setModal(null); load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Error al guardar.")
    } finally { setSaving(false) }
  }

  async function handleDelete(u: User) {
    if (!confirm(`¿Eliminar usuario '${u.identifier}'?`)) return
    await api.delete(`/api/users/${u.id}`)
    load()
  }

  return (
    <div className="tab-content">
      {(modal === "add" || modal === "edit") && (
        <Modal title={modal === "add" ? "Agregar Usuario" : "Editar Usuario"} onClose={closeModal}>
          <Field label="Identificador (Obligatorio):">
            <input value={current.identifier || ""} onChange={e => setCurrent(p => ({ ...p, identifier: e.target.value }))} />
          </Field>
          <Field label="Nombre:">
            <input value={current.first_name || ""} onChange={e => setCurrent(p => ({ ...p, first_name: e.target.value }))} />
          </Field>
          <Field label="Apellido:">
            <input value={current.last_name || ""} onChange={e => setCurrent(p => ({ ...p, last_name: e.target.value }))} />
          </Field>
          <Field label="Turno Horario:">
            <select value={current.shift_id || ""} onChange={e => setCurrent(p => ({ ...p, shift_id: e.target.value ? Number(e.target.value) : null }))}>
              <option value="">Sin Turno</option>
              {shifts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <Field label="Activo:">
            <select value={current.is_active ? "si" : "no"} onChange={e => setCurrent(p => ({ ...p, is_active: e.target.value === "si" }))}>
              <option value="si">Sí</option>
              <option value="no">No</option>
            </select>
          </Field>
          {error && <p style={{ color: "#c0392b", fontSize: 13, marginBottom: 10 }}>⚠️ {error}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button>
            <button className="btn" onClick={closeModal}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="filter-bar" style={{ marginBottom: 10 }}>
        <label>🔍 Buscar:</label>
        <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Identificador o nombre..." style={{ width: 240 }} />
        <button className="btn btn-primary" onClick={openAdd}>+ Agregar Usuario</button>
        <button className="btn" onClick={load} disabled={loading}>↻ Actualizar</button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando empleados...</p> : (
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Identificador</th><th>Nombre</th><th>Apellido</th>
                <th>Turno</th><th>Activo</th><th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin resultados</td></tr>}
              {filtered.map(u => (
                <tr key={u.id}>
                  <td><code style={{ fontSize: 12 }}>{u.identifier}</code></td>
                  <td>{u.first_name || <span style={{ opacity: 0.4 }}>—</span>}</td>
                  <td>{u.last_name || <span style={{ opacity: 0.4 }}>—</span>}</td>
                  <td>{shiftName(u.shift_id)}</td>
                  <td><span className={`badge ${u.is_active ? "badge-ok" : "badge-error"}`}>{u.is_active ? "Activo" : "Inactivo"}</span></td>
                  <td style={{ display: "flex", gap: 6 }}>
                    <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => openEdit(u)}>✏️ Editar</button>
                    <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => handleDelete(u)}>🗑️ Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: 12, opacity: 0.6, marginTop: 8 }}>{filtered.length} de {users.length} empleados</p>
        </div>
      )}
    </div>
  )
}
