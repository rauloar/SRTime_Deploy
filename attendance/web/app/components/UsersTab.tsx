"use client"
import { useState, useEffect, useCallback, useRef } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Plus, RefreshCw, Pencil, Trash2, X, Search, Upload } from "lucide-react"
import Pagination from "./Pagination"
import { downloadCsv, downloadFromApi } from "../utils/download"

interface User { id: number; identifier: string; first_name: string | null; last_name: string | null; is_active: boolean; shift_id: number | null; group_id: number | null; shift_assignment_source: string; terminal_privilege: number }
interface Shift { id: number; name: string }
interface EmployeeGroup { id: number; name: string; description: string | null; shift_id: number | null; is_active: boolean; employee_count: number }
const EMPTY: Partial<User> = { identifier: "", first_name: "", last_name: "", is_active: true, shift_id: null, terminal_privilege: 0 }
const TERMINAL_PRIVILEGES = [
  { value: 0, label: "USER" },
  { value: 14, label: "ADMIN" },
]

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

export default function UsersTab() {
  const { api } = useAuth()
  const [users, setUsers]   = useState<User[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [groups, setGroups] = useState<EmployeeGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch]   = useState("")
  const [modal, setModal]     = useState<"add" | "edit" | null>(null)
  const [current, setCurrent] = useState<Partial<User>>(EMPTY)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState("")
  const [page, setPage]       = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([])
  const [selectedGroupId, setSelectedGroupId] = useState<number | "">("")
  const [overrideManual, setOverrideManual] = useState(false)
  const [groupForm, setGroupForm] = useState({ name: "", description: "", shift_id: "" as number | "" })
  const [groupSaving, setGroupSaving] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    const [u, s, g] = await Promise.all([api.get("/api/users/?limit=2000"), api.get("/api/shifts/"), api.get("/api/employee-groups/")])
    setUsers(u.data); setShifts(s.data); setGroups(g.data); setLoading(false)
  }, [api])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [search])

  const filtered = users.filter(u =>
    (u.identifier + " " + (u.first_name || "") + " " + (u.last_name || "")).toLowerCase().includes(search.toLowerCase())
  )
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)
  const shiftName = (id: number | null) => id ? (shifts.find(s => s.id === id)?.name || "Sin Turno") : "Sin Turno"
  const groupName = (id: number | null) => id ? (groups.find(g => g.id === id)?.name || "Sin Grupo") : "Sin Grupo"
  const sourceLabel = (source: string | null | undefined) => source === "GROUP" ? "Grupo" : "Manual"
  const terminalPrivilegeLabel = (value: number | null | undefined) => value === 14 ? "ADMIN" : "USER"
  const pageSelected = paginated.length > 0 && paginated.every(u => selectedUserIds.includes(u.id))
  const activeGroups = groups.filter(g => g.is_active)

  function exportCsv() {
    const headers = ["Identificador", "Nombre", "Apellido", "Turno", "Privilegio Terminal", "Activo"]
    const rows = filtered.map(u => ({
      Identificador: u.identifier,
      Nombre: u.first_name || "",
      Apellido: u.last_name || "",
      Turno: shiftName(u.shift_id),
      "Privilegio Terminal": terminalPrivilegeLabel(u.terminal_privilege),
      Activo: u.is_active ? "Si" : "No",
    }))
    downloadCsv(headers, rows, "empleados.csv")
  }

  async function exportExcel() {
    await downloadFromApi(api, "/api/users/export", "empleados.xlsx")
  }

  async function importCsv(file: File) {
    const form = new FormData()
    form.append("file", file)
    setSaving(true); setError("")
    try {
      const { data } = await api.post("/api/users/import-csv", form, { headers: { "Content-Type": "multipart/form-data" } })
      alert(`✅ Importación finalizada. ${data.created} creados, ${data.updated} actualizados, ${data.skipped} omitidos.`)
      await load()
    } catch (e: unknown) {
      setError(getErrorMessage(e, "No se pudo importar el CSV."))
    } finally {
      setSaving(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  function toggleSelected(userId: number) {
    setSelectedUserIds(prev => prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId])
  }

  function togglePageSelected() {
    const pageIds = paginated.map(u => u.id)
    if (pageSelected) {
      setSelectedUserIds(prev => prev.filter(id => !pageIds.includes(id)))
    } else {
      setSelectedUserIds(prev => Array.from(new Set([...prev, ...pageIds])))
    }
  }

  async function createEmployeeGroup() {
    if (!groupForm.name.trim()) { setError("El nombre del grupo es obligatorio."); return }
    setGroupSaving(true); setError("")
    try {
      const { data } = await api.post("/api/employee-groups/", {
        name: groupForm.name,
        description: groupForm.description || null,
        shift_id: groupForm.shift_id === "" ? null : Number(groupForm.shift_id),
        is_active: true,
      })
      setGroupForm({ name: "", description: "", shift_id: "" })
      setSelectedGroupId(data.id)
      await load()
    } catch (e: unknown) {
      setError(getErrorMessage(e, "No se pudo crear el grupo."))
    } finally {
      setGroupSaving(false)
    }
  }

  async function assignSelectedToGroup() {
    if (!selectedGroupId) { setError("Seleccioná un grupo para asignar empleados."); return }
    if (selectedUserIds.length === 0) { setError("Seleccioná al menos un empleado."); return }
    setGroupSaving(true); setError("")
    try {
      const { data } = await api.post(`/api/employee-groups/${selectedGroupId}/assign`, {
        user_ids: selectedUserIds,
        override_manual: overrideManual,
      })
      alert(`✅ Grupo aplicado. ${data.assigned} asignados, ${data.shift_updated} turnos actualizados, ${data.manual_preserved} manuales preservados.`)
      setSelectedUserIds([])
      await load()
    } catch (e: unknown) {
      setError(getErrorMessage(e, "No se pudo asignar el grupo."))
    } finally {
      setGroupSaving(false)
    }
  }

  async function applySelectedGroupShift() {
    if (!selectedGroupId) { setError("Seleccioná un grupo."); return }
    setGroupSaving(true); setError("")
    try {
      const { data } = await api.post(`/api/employee-groups/${selectedGroupId}/apply-shift`, {
        include_manual: overrideManual,
      })
      alert(`✅ Turno del grupo aplicado. ${data.shift_updated} turnos actualizados, ${data.manual_preserved} manuales preservados.`)
      await load()
    } catch (e: unknown) {
      setError(getErrorMessage(e, "No se pudo aplicar el turno del grupo."))
    } finally {
      setGroupSaving(false)
    }
  }

  function openAdd() { setCurrent(EMPTY); setError(""); setModal("add") }
  function openEdit(u: User) { setCurrent({ ...u }); setError(""); setModal("edit") }

  async function handleSave() {
    if (!current.identifier?.trim()) { setError("El identificador es obligatorio."); return }
    setSaving(true); setError("")
    try {
      if (modal === "add")
        await api.post("/api/users/", { identifier: current.identifier, first_name: current.first_name, last_name: current.last_name, is_active: current.is_active, shift_id: current.shift_id || null, terminal_privilege: current.terminal_privilege ?? 0 })
      else
        await api.put(`/api/users/${current.id}`, { identifier: current.identifier, first_name: current.first_name, last_name: current.last_name, is_active: current.is_active, shift_id: current.shift_id || null, terminal_privilege: current.terminal_privilege ?? 0 })
      setModal(null); load()
    } catch (e: unknown) { setError(getErrorMessage(e, "Error al guardar."))
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
          <Field label="Privilegio en terminal:">
            <select value={current.terminal_privilege ?? 0} onChange={e => setCurrent(p => ({ ...p, terminal_privilege: Number(e.target.value) }))}>
              {TERMINAL_PRIVILEGES.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
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
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          style={{ display: "none" }}
          onChange={e => {
            const file = e.target.files?.[0]
            if (file) void importCsv(file)
          }}
        />
        <button className="btn" onClick={() => fileInputRef.current?.click()} disabled={saving}><Upload size={14} /> Importar CSV</button>
        <button className="btn" onClick={exportCsv}>Exportar CSV</button>
        <button className="btn" onClick={exportExcel}>Exportar Excel</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /></button>
      </div>

      <div className="employee-group-panel">
        <div>
          <h3>Grupos de Empleados</h3>
          <p>Asignación masiva de turnos sin romper cambios manuales. El motor sigue procesando por turno del empleado.</p>
          <p className="employee-group-help">
            Uso rápido: cree un grupo, seleccione empleados en la tabla, elija el grupo y pulse “Asignar seleccionados”.
            La opción “Sobrescribir turnos manuales” permite que el turno del grupo reemplace un turno cargado directamente en la ficha del empleado.
            Si no se marca, esos turnos manuales se conservan.
          </p>
        </div>
        <div className="employee-group-grid">
          <Field label="Nuevo grupo">
            <input value={groupForm.name} onChange={e => setGroupForm(p => ({ ...p, name: e.target.value }))} placeholder="Ej: Fábrica" />
          </Field>
          <Field label="Descripción">
            <input value={groupForm.description} onChange={e => setGroupForm(p => ({ ...p, description: e.target.value }))} placeholder="Opcional" />
          </Field>
          <Field label="Turno del grupo">
            <select value={groupForm.shift_id} onChange={e => setGroupForm(p => ({ ...p, shift_id: e.target.value ? Number(e.target.value) : "" }))}>
              <option value="">Sin turno</option>
              {shifts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <div className="employee-group-actions">
            <button className="btn btn-primary" onClick={createEmployeeGroup} disabled={groupSaving}><Plus size={14} /> Crear grupo</button>
          </div>
        </div>
        <div className="employee-group-grid">
          <Field label="Grupo para empleados seleccionados">
            <select value={selectedGroupId} onChange={e => setSelectedGroupId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Seleccionar grupo</option>
              {activeGroups.map(g => <option key={g.id} value={g.id}>{g.name} · {shiftName(g.shift_id)} · {g.employee_count} empleados</option>)}
            </select>
          </Field>
          <label className="checkbox-inline">
            <input type="checkbox" checked={overrideManual} onChange={e => setOverrideManual(e.target.checked)} />
            Sobrescribir turnos manuales del empleado
          </label>
          <div className="employee-group-actions">
            <button className="btn" onClick={assignSelectedToGroup} disabled={groupSaving || selectedUserIds.length === 0}>Asignar seleccionados ({selectedUserIds.length})</button>
            <button className="btn" onClick={applySelectedGroupShift} disabled={groupSaving || !selectedGroupId}>Aplicar turno al grupo</button>
          </div>
        </div>
        {activeGroups.length > 0 && (
          <div className="employee-group-summary">
            <div className="employee-group-summary-title">Grupos</div>
            <div className="employee-group-list">
              {activeGroups.map(g => (
                <span key={g.id} className="employee-group-chip employee-group-chip-strong">{g.name} · {shiftName(g.shift_id)} · {g.employee_count}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando empleados...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr><th><input type="checkbox" checked={pageSelected} onChange={togglePageSelected} aria-label="Seleccionar página" /></th><th>Identificador</th><th>Nombre</th><th>Apellido</th><th>Grupo</th><th>Turno</th><th>Origen</th><th>Privilegio Terminal</th><th>Activo</th><th>Acciones</th></tr>
              </thead>
              <tbody>
                {paginated.length === 0 && <tr><td colSpan={10} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin resultados</td></tr>}
                {paginated.map(u => (
                  <tr key={u.id}>
                    <td><input type="checkbox" checked={selectedUserIds.includes(u.id)} onChange={() => toggleSelected(u.id)} aria-label={`Seleccionar ${u.identifier}`} /></td>
                    <td><code style={{ fontSize: 12 }}>{u.identifier}</code></td>
                    <td>{u.first_name || <span style={{ opacity: 0.4 }}>—</span>}</td>
                    <td>{u.last_name || <span style={{ opacity: 0.4 }}>—</span>}</td>
                    <td>{groupName(u.group_id)}</td>
                    <td>{shiftName(u.shift_id)}</td>
                    <td><span className={`badge ${u.shift_assignment_source === "GROUP" ? "badge-justificado" : "badge-ok"}`}>{sourceLabel(u.shift_assignment_source)}</span></td>
                    <td><span className={`badge ${u.terminal_privilege === 14 ? "badge-incompleto" : "badge-ok"}`}>{terminalPrivilegeLabel(u.terminal_privilege)}</span></td>
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
