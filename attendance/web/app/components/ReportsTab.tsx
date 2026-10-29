"use client"
import { useState, useEffect, useMemo } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { FileSpreadsheet, FileText, Search } from "lucide-react"
import { downloadFromApi } from "../utils/download"

interface Employee { id: number; identifier: string; first_name: string | null; last_name: string | null; is_active: boolean }
interface ReportColumn { key: string; label: string }
type ReportRow = Record<string, string | number>
interface MonthlyReport { year: number; month: number; month_name: string; columns: ReportColumn[]; employees: ReportRow[] }

// Nombres de mes desde la configuración regional del navegador: sin listas fijas.
const MONTH_FORMAT = new Intl.DateTimeFormat("es-AR", { month: "long" })
const MONTHS = Array.from({ length: 12 }, (_, index) => {
  const label = MONTH_FORMAT.format(new Date(2000, index, 1))
  return { value: index + 1, label: label.charAt(0).toUpperCase() + label.slice(1) }
})
const NUMBER_FORMAT = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2, minimumFractionDigits: 2 })

function employeeLabel(employee: Employee) {
  const name = `${employee.last_name || ""}, ${employee.first_name || ""}`.replace(/^,\s*|,\s*$/g, "")
  return name ? `${employee.identifier} — ${name}` : employee.identifier
}

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === "string") return detail
  }
  return fallback
}

export default function ReportsTab() {
  const { api } = useAuth()
  const today = new Date()
  const [month, setMonth]           = useState(today.getMonth() + 1)
  const [year, setYear]             = useState(today.getFullYear())
  const [employeeId, setEmployeeId] = useState("")
  const [employees, setEmployees]   = useState<Employee[]>([])
  const [report, setReport]         = useState<MonthlyReport | null>(null)
  const [reportKey, setReportKey]   = useState("")
  const [loading, setLoading]       = useState(false)
  const [exporting, setExporting]   = useState<"xlsx" | "pdf" | null>(null)
  const [message, setMessage]       = useState("")

  useEffect(() => {
    api.get("/api/users/?limit=2000")
      .then(res => setEmployees((res.data as Employee[]).filter(e => e.is_active)
        .sort((a, b) => (a.last_name || "").localeCompare(b.last_name || ""))))
      .catch(() => setEmployees([]))
  }, [api])

  const params = useMemo(() => ({
    year, month, employee_id: employeeId ? Number(employeeId) : undefined,
  }), [year, month, employeeId])

  // Un reporte generado sólo se exporta con los mismos filtros que se ven en pantalla.
  const filtersKey = JSON.stringify(params)
  const canExport = report !== null && reportKey === filtersKey && report.employees.length > 0

  async function generate() {
    if (!Number.isInteger(year)) { setMessage("Ingresá un año válido."); return }
    setLoading(true); setMessage("")
    try {
      const res = await api.get("/api/reports/monthly", { params })
      const data = res.data as MonthlyReport
      setReport(data)
      setReportKey(filtersKey)
      if (!data.employees.length) setMessage("No hay registros para el período seleccionado.")
    } catch (e: unknown) {
      setReport(null); setMessage(getErrorMessage(e, "No se pudo generar el reporte."))
    } finally { setLoading(false) }
  }

  async function exportReport(kind: "xlsx" | "pdf") {
    setExporting(kind); setMessage("")
    try {
      const url = kind === "xlsx" ? "/api/reports/monthly/export" : "/api/reports/monthly/export/pdf"
      await downloadFromApi(api, url, `reporte_${year}_${month}.${kind}`, params)
    } catch (e: unknown) {
      setMessage(getErrorMessage(e, "No se pudo exportar el reporte."))
    } finally { setExporting(null) }
  }

  function renderCell(column: ReportColumn, row: ReportRow) {
    const value = row[column.key]
    return column.key === "total_hours" && typeof value === "number" ? NUMBER_FORMAT.format(value) : value
  }

  return (
    <div>
      <div className="filter-bar">
        <label>Mes:</label>
        <select value={month} onChange={e => setMonth(Number(e.target.value))}>
          {MONTHS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
        <label>Año:</label>
        <input type="number" value={year} step={1} onChange={e => setYear(Number(e.target.value))} style={{ width: 90 }} />
        <label>Empleado:</label>
        <select value={employeeId} onChange={e => setEmployeeId(e.target.value)} style={{ maxWidth: 260 }}>
          <option value="">Todos</option>
          {employees.map(e => <option key={e.id} value={e.id}>{employeeLabel(e)}</option>)}
        </select>
        <button className="btn btn-primary" onClick={generate} disabled={loading}>
          <Search size={14} /> {loading ? "Generando..." : "Generar Reporte"}
        </button>
        <button className="btn" onClick={() => exportReport("xlsx")} disabled={!canExport || exporting !== null}>
          <FileSpreadsheet size={14} /> {exporting === "xlsx" ? "Exportando..." : "Exportar Excel"}
        </button>
        <button className="btn" onClick={() => exportReport("pdf")} disabled={!canExport || exporting !== null}>
          <FileText size={14} /> {exporting === "pdf" ? "Exportando..." : "Exportar PDF"}
        </button>
      </div>

      {message && <p style={{ fontSize: 13, marginBottom: 10, color: "var(--text-secondary)" }}>⚠ {message}</p>}

      {report && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>{report.columns.map(column => <th key={column.key}>{column.label}</th>)}</tr>
            </thead>
            <tbody>
              {report.employees.length === 0 && (
                <tr><td colSpan={report.columns.length} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin registros en el período</td></tr>
              )}
              {report.employees.map(row => (
                <tr key={String(row.employee_id)}>
                  {report.columns.map(column => <td key={column.key}>{renderCell(column, row)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
