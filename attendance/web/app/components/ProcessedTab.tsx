"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { RefreshCw, Wrench, Play, RotateCcw } from "lucide-react"
import Pagination from "./Pagination"
import { downloadFromApi } from "../utils/download"
import OperationProgress, { OperationJob } from "./OperationProgress"
import AttendanceCorrectionModal from "./AttendanceCorrectionModal"

interface ProcessedRecord {
  id: number; employee_id: number; date: string;
  first_in: string | null; last_out: string | null;
  total_hours: number; tardiness_minutes: number;
  early_departure_minutes: number; overtime_minutes: number;
  status: string; justification: string | null; previous_status?: string | null
}
interface User { id: number; first_name: string | null; last_name: string | null }

const STATUS_BADGE: Record<string, string> = {
  OK: "badge-ok", INCOMPLETO: "badge-incompleto",
  JUSTIFICADO: "badge-justificado", ERROR: "badge-error"
}
function today() { return new Date().toISOString().slice(0, 10) }
function daysAgo(n: number) { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10) }

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
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
  const [actionMsg, setActionMsg] = useState("")
  const [processing, setProcessing] = useState<"pending" | "all" | null>(null)
  const [job, setJob] = useState<OperationJob | null>(null)
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

  useEffect(() => {
    if (!job || job.state === "completed" || job.state === "failed") return
    const timer = window.setInterval(async () => {
      try {
        const res = await api.get(`/api/processed/jobs/${job.id}`)
        const next = res.data as OperationJob
        setJob(next)
        if (next.state === "completed") {
          await load()
          setActionMsg(`Proceso completado: ${next.result?.processed_days || 0} flujos diarios procesados.`)
          setProcessing(null)
        }
        if (next.state === "failed") { setActionMsg(next.error || next.message); setProcessing(null) }
      } catch { setActionMsg("No se pudo consultar el progreso del proceso"); setProcessing(null) }
    }, 500)
    return () => window.clearInterval(timer)
  }, [api, job, load])

  const nameOf = (emp_id: number) => {
    const u = users.find(x => x.id === emp_id)
    if (!u) return `#${emp_id}`
    return `${u.last_name || ""}, ${u.first_name || ""}`.replace(/^,\s*/, "")
  }

  const filtered = records.filter(r => !empFilter || nameOf(r.employee_id).toLowerCase().includes(empFilter.toLowerCase()))
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)

  function exportCsv() {
    const rows = filtered.map(r => ({
      Empleado: nameOf(r.employee_id),
      Fecha: r.date,
      "Primera Entrada": r.first_in || "",
      "Última Salida": r.last_out || "",
      "Horas Totales": r.total_hours,
      "Tardanza (Min)": r.tardiness_minutes,
      "Salida Ant. (Min)": r.early_departure_minutes,
      "Hs Extra (Min)": r.overtime_minutes,
      Estado: r.status,
      Justificación: r.justification || "",
    }))

    const header = [
      "Empleado",
      "Fecha",
      "Primera Entrada",
      "Última Salida",
      "Horas Totales",
      "Tardanza (Min)",
      "Salida Ant. (Min)",
      "Hs Extra (Min)",
      "Estado",
      "Justificación",
    ]
    const lines = [
      header.join(","),
      ...rows.map(r => [
        r.Empleado,
        r.Fecha,
        r["Primera Entrada"],
        r["Última Salida"],
        r["Horas Totales"],
        r["Tardanza (Min)"],
        r["Salida Ant. (Min)"],
        r["Hs Extra (Min)"],
        r.Estado,
        r.Justificación,
      ].map(v => `"${String(v).replaceAll('"', '""')}"`).join(",")),
    ]

    const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "asistencia_procesada.csv"
    a.click()
    URL.revokeObjectURL(url)
  }

  async function exportExcel() {
    await downloadFromApi(api, "/api/processed/export", "asistencia_procesada.xlsx", {
      date_start: dateStart,
      date_end: dateEnd,
    })
  }

  useEffect(() => {
    if (selectedRowId == null) return
    const exists = records.some(r => r.id === selectedRowId)
    if (!exists) setSelectedRowId(null)
  }, [records, selectedRowId])

  function openJustify(r: ProcessedRecord) {
    if (r.status === "OK") {
      const proceed = window.confirm("Este registro ya está OK. ¿Deseas justificarlo de todos modos?")
      if (!proceed) return
    }
    setSelected(r)
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
    if (rec.status === "AUSENTE" || rec.previous_status === "AUSENTE") {
      setActionMsg("Las ausencias se justifican desde la pestaña Ausencias.")
      return
    }
    openJustify(rec)
  }

  async function runProcess(mode: "pending" | "all") {
    setProcessing(mode)
    setActionMsg("")
    try {
      const res = await api.post(`/api/processed/jobs/${mode}`)
      setJob(res.data as OperationJob)
    } catch (e: unknown) {
      setActionMsg(getErrorMessage(e, "Error al ejecutar el proceso"))
      setProcessing(null)
    }
  }

  return (
    <div>
      {selected && (
        <AttendanceCorrectionModal
          title="Justificar asistencia"
          context={`${selected.date} — ${nameOf(selected.employee_id)}`}
          firstIn={selected.first_in}
          lastOut={selected.last_out}
          justification={selected.justification}
          onClose={() => setSelected(null)}
          onSave={async values => {
            await api.patch(`/api/processed/${selected.id}/justify`, { first_in: values.firstIn, last_out: values.lastOut, justification: values.justification })
            setSelected(null)
            await load()
          }}
        />
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
        <button className="btn" onClick={exportCsv}>Exportar CSV</button>
        <button className="btn" onClick={exportExcel}>Exportar Excel</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /> Actualizar</button>
      </div>

      <OperationProgress job={job} />

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
                    <td>{r.status !== "AUSENTE" && r.previous_status !== "AUSENTE" &&
                      <button className="btn" style={{ padding: "4px 10px", fontSize: 12, whiteSpace: "nowrap" }} onClick={() => openJustify(r)}>
                        <Wrench size={13} /> Justificar
                      </button>
                    }</td>
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
