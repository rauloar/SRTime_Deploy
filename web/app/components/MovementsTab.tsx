"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import { Search, RefreshCw, LogIn, LogOut } from "lucide-react"
import Pagination from "./Pagination"
import * as XLSX from "xlsx"

interface Movement {
  id: number; raw_identifier: string; employee_id: number | null
  first_name: string | null; last_name: string | null
  date: string; time: string | null; mark_type: number | null
}

function today() { return new Date().toISOString().slice(0, 10) }
function daysAgo(n: number) { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10) }

export default function MovementsTab() {
  const { api } = useAuth()
  const [movements, setMovements] = useState<Movement[]>([])
  const [loading, setLoading]     = useState(true)
  const [dateStart, setDateStart] = useState(daysAgo(7))
  const [dateEnd, setDateEnd]     = useState(today())
  const [empFilter, setEmpFilter] = useState("")
  const [page, setPage]           = useState(1)
  const [pageSize, setPageSize]   = useState(50)

  const load = useCallback(async () => {
    setLoading(true)
    const res = await api.get("/api/movements/", { params: { date_start: dateStart, date_end: dateEnd, limit: 5000 } })
    setMovements(res.data); setLoading(false)
  }, [api, dateStart, dateEnd])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [empFilter, dateStart, dateEnd])

  const nameOf = (mov: Movement) => {
    if (mov.last_name || mov.first_name) return `${mov.last_name || ""}, ${mov.first_name || ""}`.replace(/^,\s*/, "")
    return mov.raw_identifier
  }

  const filtered = movements.filter(m => {
    if (!empFilter) return true
    return (nameOf(m) + m.raw_identifier).toLowerCase().includes(empFilter.toLowerCase())
  })
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)

  function exportCsv() {
    const rows = filtered.map(m => ({
      Identificador: m.raw_identifier,
      Nombre: nameOf(m),
      Fecha: m.date,
      Hora: m.time || "",
      Movimiento: m.mark_type === 0 ? "ENTRADA" : m.mark_type === 1 ? "SALIDA" : "",
    }))

    const header = ["Identificador", "Nombre", "Fecha", "Hora", "Movimiento"]
    const lines = [
      header.join(","),
      ...rows.map(r => [r.Identificador, r.Nombre, r.Fecha, r.Hora, r.Movimiento].map(v => `"${String(v).replaceAll('"', '""')}"`).join(",")),
    ]
    const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "movimientos.csv"
    a.click()
    URL.revokeObjectURL(url)
  }

  function exportExcel() {
    const rows = filtered.map(m => ({
      Identificador: m.raw_identifier,
      Nombre: nameOf(m),
      Fecha: m.date,
      Hora: m.time || "",
      Movimiento: m.mark_type === 0 ? "ENTRADA" : m.mark_type === 1 ? "SALIDA" : "",
    }))
    const ws = XLSX.utils.json_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, "Movimientos")
    XLSX.writeFile(wb, "movimientos.xlsx")
  }

  const markLabel = (t: number | null) => {
    if (t === 0) return <span style={{ color: "var(--status-ok)", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 4 }}><LogIn size={13} /> ENTRADA</span>
    if (t === 1) return <span style={{ color: "var(--status-error)", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 4 }}><LogOut size={13} /> SALIDA</span>
    return <span style={{ opacity: 0.5 }}>—</span>
  }

  return (
    <div>
      <div className="filter-bar">
        <label>Desde:</label>
        <input type="date" value={dateStart} onChange={e => setDateStart(e.target.value)} />
        <label>Hasta:</label>
        <input type="date" value={dateEnd} onChange={e => setDateEnd(e.target.value)} />
        <Search size={15} color="var(--text-muted)" />
        <input type="text" value={empFilter} onChange={e => setEmpFilter(e.target.value)}
          placeholder="Nombre o identificador..." style={{ width: 200 }} />
        <button className="btn" onClick={exportCsv}>Exportar CSV</button>
        <button className="btn" onClick={exportExcel}>Exportar Excel</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /> Actualizar</button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando movimientos...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Identificador</th><th>Nombre</th><th>Fecha</th><th>Hora</th><th>Movimiento</th>
                </tr>
              </thead>
              <tbody>
                {paginated.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin movimientos en el rango seleccionado</td></tr>
                )}
                {paginated.map(m => (
                  <tr key={m.id}>
                    <td><code style={{ fontSize: 12 }}>{m.raw_identifier}</code></td>
                    <td>{nameOf(m)}</td>
                    <td>{m.date}</td>
                    <td>{m.time || "--:--"}</td>
                    <td>{markLabel(m.mark_type)}</td>
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
