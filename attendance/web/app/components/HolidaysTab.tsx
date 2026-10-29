"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Plus, RefreshCw, Pencil, Trash2 } from "lucide-react"
import AppDialog from "./AppDialog"
import Pagination from "./Pagination"

interface Holiday { id: number; date: string; name: string; is_recurring: boolean }
interface HolidayForm { id?: number; date: string; name: string; is_recurring: boolean }

// Mismos roles que exige la API (require_supervisor_or_root / require_root).
const EDITOR_ROLES = ["root", "admin", "supervisor"]

function todayIso() {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

function formatDate(iso: string) {
  const [year, month, day] = iso.split("-")
  return `${day}/${month}/${year}`
}

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === "string") return detail
  }
  return fallback
}

export default function HolidaysTab() {
  const { api, role } = useAuth()
  const canEdit = EDITOR_ROLES.includes(role || "")
  const canDelete = role === "root"
  const [holidays, setHolidays] = useState<Holiday[]>([])
  const [loading, setLoading]   = useState(true)
  const [modal, setModal]       = useState<"add" | "edit" | null>(null)
  const [current, setCurrent]   = useState<HolidayForm>({ date: todayIso(), name: "", is_recurring: false })
  const [toDelete, setToDelete] = useState<Holiday | null>(null)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState("")
  const [listError, setListError] = useState("")
  const [page, setPage]         = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const load = useCallback(async () => {
    setLoading(true); setListError("")
    try {
      const res = await api.get("/api/holidays/")
      setHolidays(res.data)
    } catch (e: unknown) {
      setListError(getErrorMessage(e, "No se pudieron cargar los feriados."))
    } finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const paginated = holidays.slice((page - 1) * pageSize, page * pageSize)

  function openAdd() { setCurrent({ date: todayIso(), name: "", is_recurring: false }); setError(""); setModal("add") }
  function openEdit(h: Holiday) { setCurrent({ ...h }); setError(""); setModal("edit") }

  async function handleSave() {
    if (!current.date) { setError("La fecha es obligatoria."); return }
    if (!current.name.trim()) { setError("El nombre es obligatorio."); return }
    setSaving(true); setError("")
    try {
      const payload = { date: current.date, name: current.name.trim(), is_recurring: current.is_recurring }
      if (modal === "add") await api.post("/api/holidays/", payload)
      else await api.put(`/api/holidays/${current.id}`, payload)
      setModal(null); load()
    } catch (e: unknown) { setError(getErrorMessage(e, "Error al guardar el feriado."))
    } finally { setSaving(false) }
  }

  async function handleDelete() {
    if (!toDelete) return
    setSaving(true)
    try {
      await api.delete(`/api/holidays/${toDelete.id}`)
      setToDelete(null); load()
    } catch (e: unknown) {
      setListError(getErrorMessage(e, "No se pudo eliminar el feriado.")); setToDelete(null)
    } finally { setSaving(false) }
  }

  return (
    <div>
      {(modal === "add" || modal === "edit") && (
        <AppDialog
          title={modal === "add" ? "Nuevo Feriado" : "Editar Feriado"}
          onClose={() => setModal(null)}
          actions={[
            { label: saving ? "Guardando..." : "Guardar", onClick: handleSave, variant: "primary", disabled: saving },
            { label: "Cancelar", onClick: () => setModal(null) },
          ]}
        >
          <div className="form-group"><label>Fecha:</label>
            <input type="date" required value={current.date} onChange={e => setCurrent(p => ({ ...p, date: e.target.value }))} />
          </div>
          <div className="form-group"><label>Nombre:</label>
            <input value={current.name} onChange={e => setCurrent(p => ({ ...p, name: e.target.value }))} />
          </div>
          <div className="form-group">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" checked={current.is_recurring} onChange={e => setCurrent(p => ({ ...p, is_recurring: e.target.checked }))} />
              Repite anualmente
            </label>
          </div>
          {error && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {error}</p>}
        </AppDialog>
      )}

      {toDelete && (
        <AppDialog
          title="Eliminar Feriado"
          onClose={() => setToDelete(null)}
          actions={[
            { label: "Eliminar", onClick: handleDelete, variant: "danger", disabled: saving },
            { label: "Cancelar", onClick: () => setToDelete(null) },
          ]}
        >
          <p>¿Eliminar &apos;{toDelete.name}&apos; ({formatDate(toDelete.date)})?</p>
        </AppDialog>
      )}

      <div className="toolbar">
        {canEdit && <button className="btn btn-primary" onClick={openAdd}><Plus size={15} /> Nuevo Feriado</button>}
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /></button>
      </div>

      {listError && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {listError}</p>}

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando feriados...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr><th>Fecha</th><th>Nombre</th><th>Repite anualmente</th>{(canEdit || canDelete) && <th>Acciones</th>}</tr>
              </thead>
              <tbody>
                {paginated.length === 0 && <tr><td colSpan={4} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin feriados cargados</td></tr>}
                {paginated.map(h => (
                  <tr key={h.id}>
                    <td>{formatDate(h.date)}</td>
                    <td>{h.name}</td>
                    <td>{h.is_recurring ? "Sí" : "No"}</td>
                    {(canEdit || canDelete) && (
                      <td style={{ display: "flex", gap: 6 }}>
                        {canEdit && <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => openEdit(h)}><Pencil size={13} /> Editar</button>}
                        {canDelete && <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setToDelete(h)}><Trash2 size={13} /> Eliminar</button>}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={holidays.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
        </>
      )}
    </div>
  )
}
