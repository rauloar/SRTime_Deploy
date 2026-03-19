"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import { Plus, RefreshCw, Pencil, Trash2, X, Search } from "lucide-react"
import Pagination from "./Pagination"

interface User { id: number; identifier: string; first_name: string | null; last_name: string | null; is_active: boolean; shift_id: number | null }
interface Shift { id: number; name: string }
const EMPTY: Partial<User> = { identifier: "", first_name: "", last_name: "", is_active: true, shift_id: null }

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

export default function UsersTab() {
  const { api } = useAuth()
  const [users, setUsers]   = useState<User[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch]   = useState("")
  const [modal, setModal]     = useState<"add" | "edit" | null>(null)
  const [current, setCurrent] = useState<Partial<User>>(EMPTY)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState("")
  const [page, setPage]       = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const load = useCallback(async () => {
    setLoading(true)
    const [u, s] = await Promise.all([api.get("/api/users/?limit=2000"), api.get("/api/shifts/")])
    setUsers(u.data); setShifts(s.data); setLoading(false)
  }, [api])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [search])

  const filtered = users.filter(u =>
    (u.identifier + " " + (u.first_name || "") + " " + (u.last_name || "")).toLowerCase().includes(search.toLowerCase())
  )
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)
  const shiftName = (id: number | null) => id ? (shifts.find(s => s.id === id)?.name || "Sin Turno") : "Sin Turno"

  function openAdd() { setCurrent(EMPTY); setError(""); setModal("add") }
  function openEdit(u: User) { setCurrent({ ...u }); setError(""); setModal("edit") }

  async function handleSave() {
    if (!current.identifier?.trim()) { setError("El identificador es obligatorio."); return }
    setSaving(true); setError("")
    try {
      if (modal === "add")
        await api.post("/api/users/", { identifier: current.identifier, first_name: current.first_name, last_name: current.last_name, is_active: current.is_active, shift_id: current.shift_id || null })
      else
        await api.put(`/api/users/${current.id}`, { identifier: current.identifier, first_name: current.first_name, last_name: current.last_name, is_active: current.is_active, shift_id: current.shift_id || null })
      setModal(null); load()
    } catch (e: any) { setError(e?.response?.data?.detail || "Error al guardar.")
    } finally { setSaving(false) }
  }

  async function handleDelete(u: User) {
    if (!confirm(`¿Eliminar usuario '${u.identifier}'?`)) return
    await api.delete(`/api/users/${u.id}`); load()
  }

  return (
    <div>
      {(modal === "add" || modal === "edit") && (
        <Modal title={modal === "add" ? "Agregar Usuario" : "Editar Usuario"} onClose={() => setModal(null)}>
          <Field label="Identificador (Obligatorio):"><input value={current.identifier || ""} onChange={e => setCurrent(p => ({ ...p, identifier: e.target.value }))} /></Field>
          <Field label="Nombre:"><input value={current.first_name || ""} onChange={e => setCurrent(p => ({ ...p, first_name: e.target.value }))} /></Field>
          <Field label="Apellido:"><input value={current.last_name || ""} onChange={e => setCurrent(p => ({ ...p, last_name: e.target.value }))} /></Field>
          <Field label="Turno Horario:">
            <select value={current.shift_id || ""} onChange={e => setCurrent(p => ({ ...p, shift_id: e.target.value ? Number(e.target.value) : null }))}>
              <option value="">Sin Turno</option>
              {shifts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <Field label="Activo:">
            <select value={current.is_active ? "si" : "no"} onChange={e => setCurrent(p => ({ ...p, is_active: e.target.value === "si" }))}>
              <option value="si">Sí</option><option value="no">No</option>
            </select>
          </Field>
          {error && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {error}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button>
            <button className="btn" onClick={() => setModal(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="filter-bar">
        <Search size={15} color="var(--text-muted)" />
        <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Identificador o nombre..." style={{ width: 220 }} />
        <button className="btn btn-primary" onClick={openAdd}><Plus size={15} /> Agregar</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /></button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando empleados...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr><th>Identificador</th><th>Nombre</th><th>Apellido</th><th>Turno</th><th>Activo</th><th>Acciones</th></tr>
              </thead>
              <tbody>
                {paginated.length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin resultados</td></tr>}
                {paginated.map(u => (
                  <tr key={u.id}>
                    <td><code style={{ fontSize: 12 }}>{u.identifier}</code></td>
                    <td>{u.first_name || <span style={{ opacity: 0.4 }}>—</span>}</td>
                    <td>{u.last_name || <span style={{ opacity: 0.4 }}>—</span>}</td>
                    <td>{shiftName(u.shift_id)}</td>
                    <td><span className={`badge ${u.is_active ? "badge-ok" : "badge-error"}`}>{u.is_active ? "Activo" : "Inactivo"}</span></td>
                    <td style={{ display: "flex", gap: 6 }}>
                      <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => openEdit(u)}><Pencil size={13} /> Editar</button>
                      <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => handleDelete(u)}><Trash2 size={13} /> Eliminar</button>
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
