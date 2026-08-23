"use client"

import { useCallback, useEffect, useState } from "react"
import axios from "axios"
import { Check, RefreshCw, RotateCcw, UserX, X } from "lucide-react"
import { useAuth } from "../context/AuthContext"
import Pagination from "./Pagination"
import AttendanceCorrectionModal from "./AttendanceCorrectionModal"

interface AbsenceRecord {
  id: number
  employee_id: number
  date: string
  first_in: string | null
  last_out: string | null
  status: string
  justification: string | null
  previous_status: string | null
  pending_justification: string | null
  requested_by: string | null
}
interface Employee { id: number; first_name: string | null; last_name: string | null; identifier: string }

const STATUS_BADGE: Record<string, string> = {
  AUSENTE: "badge-error", INCOMPLETO: "badge-incompleto", PENDIENTE: "badge-incompleto", JUSTIFICADO: "badge-justificado",
}
const today = () => new Date().toISOString().slice(0, 10)
const daysAgo = (n: number) => {
  const day = new Date()
  day.setDate(day.getDate() - n)
  return day.toISOString().slice(0, 10)
}

function errorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return <div className="modal-backdrop"><div className="modal-box">
    <div className="modal-title"><span>{title}</span><button className="modal-close" onClick={onClose}><X size={16} /></button></div>
    {children}
  </div></div>
}

export default function AbsencesTab() {
  const { api, role } = useAuth()
  const [records, setRecords] = useState<AbsenceRecord[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [dateStart, setDateStart] = useState(daysAgo(30))
  const [dateEnd, setDateEnd] = useState(today())
  const [employeeFilter, setEmployeeFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [loading, setLoading] = useState(true)
  const [reprocessing, setReprocessing] = useState(false)
  const [message, setMessage] = useState("")
  const [selected, setSelected] = useState<AbsenceRecord | null>(null)
  const [selectedIncomplete, setSelectedIncomplete] = useState<AbsenceRecord | null>(null)
  const [reason, setReason] = useState("")
  const [saving, setSaving] = useState(false)
  const [modalError, setModalError] = useState("")
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const canManage = role === "root" || role === "admin" || role === "supervisor"
  const isRoot = role === "root"

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [absenceResponse, employeesResponse] = await Promise.all([
        api.get("/api/absences/", { params: { date_start: dateStart, date_end: dateEnd, status: statusFilter || undefined } }),
        api.get("/api/users/?limit=2000"),
      ])
      setRecords(absenceResponse.data)
      setEmployees(employeesResponse.data)
    } catch (error: unknown) {
      setMessage(errorMessage(error, "No se pudieron cargar las ausencias."))
    } finally {
      setLoading(false)
    }
  }, [api, dateStart, dateEnd, statusFilter])

  useEffect(() => { void load() }, [load])
  useEffect(() => { setPage(1) }, [employeeFilter, statusFilter, dateStart, dateEnd])

  function employeeName(employeeId: number) {
    const employee = employees.find(item => item.id === employeeId)
    if (!employee) return `#${employeeId}`
    return `${employee.last_name || ""}, ${employee.first_name || ""}`.replace(/^,\s*/, "") || employee.identifier
  }

  const filtered = records.filter(record => !employeeFilter || employeeName(record.employee_id).toLowerCase().includes(employeeFilter.toLowerCase()))
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)

  function openJustification(record: AbsenceRecord) {
    setSelected(record)
    setReason(record.justification || record.pending_justification || "")
    setModalError("")
  }

  function openIncompleteCorrection(record: AbsenceRecord) {
    setSelectedIncomplete(record)
  }

  async function reprocess() {
    setReprocessing(true)
    setMessage("")
    try {
      const response = await api.post("/api/absences/reprocess", { date_start: dateStart, date_end: dateEnd })
      setMessage(`Reproceso finalizado: ${response.data.created_absences} ausencia(s) nueva(s).`)
      await load()
    } catch (error: unknown) {
      setMessage(errorMessage(error, "No se pudieron reprocesar las ausencias."))
    } finally {
      setReprocessing(false)
    }
  }

  async function saveJustification() {
    if (!selected || !reason.trim()) { setModalError("Debe indicar el motivo de la justificación."); return }
    setSaving(true)
    try {
      const endpoint = isRoot ? "justify" : "request-justify"
      await api.patch(`/api/absences/${selected.id}/${endpoint}`, { justification: reason.trim() })
      setSelected(null)
      setMessage(isRoot ? "Ausencia justificada." : "Solicitud de justificación enviada a root.")
      await load()
    } catch (error: unknown) {
      setModalError(errorMessage(error, "No se pudo guardar la justificación."))
    } finally {
      setSaving(false)
    }
  }

  async function resolve(record: AbsenceRecord, action: "approve-justify" | "reject-justify") {
    setMessage("")
    try {
      await api.patch(`/api/absences/${record.id}/${action}`)
      setMessage(action === "approve-justify" ? "Justificación aprobada." : "Justificación rechazada.")
      await load()
    } catch (error: unknown) {
      setMessage(errorMessage(error, "No se pudo completar la acción."))
    }
  }

  async function saveIncompleteCorrection(firstIn: string, lastOut: string, justification: string) {
    if (!selectedIncomplete) return
    const endpoint = isRoot ? "justify" : "request-justify"
    await api.patch(`/api/processed/${selectedIncomplete.id}/${endpoint}`, {
      first_in: firstIn,
      last_out: lastOut,
      justification,
    })
    setSelectedIncomplete(null)
    setMessage(isRoot ? "Movimiento incompleto corregido y justificado." : "Solicitud de corrección enviada a root.")
    await load()
  }

  return <div>
    {selectedIncomplete && <AttendanceCorrectionModal
      title={isRoot ? "Corregir y justificar movimiento incompleto" : "Solicitar corrección de movimiento incompleto"}
      context={`${selectedIncomplete.date} — ${employeeName(selectedIncomplete.employee_id)}`}
      firstIn={selectedIncomplete.first_in}
      lastOut={selectedIncomplete.last_out}
      justification={selectedIncomplete.justification}
      onClose={() => setSelectedIncomplete(null)}
      onSave={values => saveIncompleteCorrection(values.firstIn, values.lastOut, values.justification)}
    />}
    {selected && <Modal title={isRoot ? "Justificar ausencia" : "Solicitar justificación"} onClose={() => setSelected(null)}>
      <p className="absence-modal-context">{selected.date} — {employeeName(selected.employee_id)}</p>
      <div className="form-group"><label>Motivo (obligatorio)</label><textarea rows={3} value={reason} onChange={event => setReason(event.target.value)} /></div>
      {modalError && <p className="absence-message absence-message-error">⚠ {modalError}</p>}
      <div className="modal-actions"><button className="btn btn-primary" onClick={saveJustification} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button><button className="btn" onClick={() => setSelected(null)}>Cancelar</button></div>
    </Modal>}

    <div className="filter-bar">
      <label>Desde:</label><input type="date" value={dateStart} onChange={event => setDateStart(event.target.value)} />
      <label>Hasta:</label><input type="date" value={dateEnd} onChange={event => setDateEnd(event.target.value)} />
      <label>Empleado:</label><input type="text" value={employeeFilter} onChange={event => setEmployeeFilter(event.target.value)} placeholder="Filtrar nombre..." />
      <label>Estado:</label><select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">Todos</option><option value="AUSENTE">Ausente</option><option value="INCOMPLETO">Incompleto</option><option value="PENDIENTE">Pendiente</option><option value="JUSTIFICADO">Justificado</option></select>
      {canManage && <button className="btn btn-primary" onClick={reprocess} disabled={reprocessing}><RotateCcw size={14} /> {reprocessing ? "Reprocesando..." : "Reprocesar ausencias"}</button>}
      <button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Actualizar</button>
    </div>

    {message && <p className={`absence-message ${message.startsWith("No ") ? "absence-message-error" : ""}`}>{message}</p>}

    {loading ? <p className="table-empty">Cargando ausencias...</p> : <>
      <div className="table-wrapper"><table className="data-table"><thead><tr>
        <th>Empleado</th><th>Fecha</th><th>Estado</th><th>Motivo</th><th>Solicitado por</th><th>Acciones</th>
      </tr></thead><tbody>
        {paginated.length === 0 && <tr><td colSpan={6} className="table-empty">Sin ausencias en el rango seleccionado</td></tr>}
        {paginated.map(record => <tr key={record.id}>
          <td>{employeeName(record.employee_id)}</td><td>{record.date}</td>
          <td><span className={`badge ${STATUS_BADGE[record.status] || "badge-error"}`}>{record.status}</span></td>
          <td>{record.justification || record.pending_justification || <span className="absence-empty">—</span>}</td>
          <td>{record.requested_by || <span className="absence-empty">—</span>}</td>
          <td><div className="absence-actions">
            {record.status === "AUSENTE" && canManage && <button className="btn" onClick={() => openJustification(record)}><UserX size={13} /> {isRoot ? "Justificar" : "Solicitar"}</button>}
            {record.status === "INCOMPLETO" && canManage && <button className="btn" onClick={() => openIncompleteCorrection(record)}><UserX size={13} /> {isRoot ? "Corregir y justificar" : "Solicitar corrección"}</button>}
            {record.status === "PENDIENTE" && record.previous_status === "AUSENTE" && isRoot && <><button className="btn btn-primary" onClick={() => void resolve(record, "approve-justify")}><Check size={13} /> Aprobar</button><button className="btn btn-danger" onClick={() => void resolve(record, "reject-justify")}><X size={13} /> Rechazar</button></>}
          </div></td>
        </tr>)}
      </tbody></table></div>
      <Pagination total={filtered.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
    </>}
  </div>
}
