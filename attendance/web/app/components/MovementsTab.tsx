"use client"
import { useState, useEffect, useCallback, useMemo } from "react"
import { useAuth } from "../context/AuthContext"
import { Search, RefreshCw, LogIn, LogOut } from "lucide-react"
import Pagination from "./Pagination"
import { downloadFromApi } from "../utils/download"

interface Movement {
  id: number; raw_identifier: string; employee_id: number | null
  first_name: string | null; last_name: string | null
  date: string; time: string | null; mark_type: number | null
}

interface MovementGroup {
  identifier: string
  name: string
  date: string
  movements: Movement[]
}

interface GroupedMovement {
  identifier: string
  name: string
  date: string
  inTime: string
  outTime: string
}

type SortKey = "identifier" | "name" | "date" | "time" | "movement" | "entry" | "exit"

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
  const [viewMode, setViewMode]   = useState<"vertical" | "horizontal">("vertical")
  const [sortKey, setSortKey]     = useState<SortKey>("date")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc")

  const load = useCallback(async () => {
    setLoading(true)
    const res = await api.get("/api/movements/", { params: { date_start: dateStart, date_end: dateEnd, limit: 5000 } })
    setMovements(res.data); setLoading(false)
  }, [api, dateStart, dateEnd])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [empFilter, dateStart, dateEnd, sortKey, sortDirection])

  const nameOf = (mov: Movement) => {
    if (mov.last_name || mov.first_name) return `${mov.last_name || ""}, ${mov.first_name || ""}`.replace(/^,\s*/, "")
    return mov.raw_identifier
  }

  const filtered = movements.filter(m => {
    const search = empFilter.trim().toLocaleLowerCase()
    if (!search) return true
    const movement = m.mark_type === 0 ? "entrada" : m.mark_type === 1 ? "salida" : ""
    return [nameOf(m), m.raw_identifier, m.date, m.time || "", movement]
      .join(" ").toLocaleLowerCase().includes(search)
  })

  const groupedMovements = useMemo(() => {
    if (viewMode !== "horizontal") return []
    const map = new Map<string, MovementGroup>()
    
    filtered.forEach(m => {
      const key = `${m.raw_identifier}_${m.date}`
      if (!map.has(key)) {
        map.set(key, { identifier: m.raw_identifier, name: nameOf(m), date: m.date, movements: [] })
      }
      map.get(key)?.movements.push(m)
    })
    
    return Array.from(map.values()).map(g => {
      g.movements.sort((a, b) => (a.time || "").localeCompare(b.time || ""))
      let inTime = ""
      let outTime = ""
      const ins = g.movements.filter(m => m.mark_type === 0)
      const outs = g.movements.filter(m => m.mark_type === 1)
      
      if (ins.length && outs.length) {
        inTime = ins[0].time || ""
        outTime = outs[outs.length - 1].time || ""
      } else if (g.movements.length >= 2) {
        inTime = g.movements[0].time || ""
        outTime = g.movements[g.movements.length - 1].time || ""
      } else if (g.movements.length === 1) {
        const m = g.movements[0]
        if (m.mark_type === 0) inTime = m.time || ""
        else if (m.mark_type === 1) outTime = m.time || ""
        else inTime = m.time || ""
      }
      
      return {
        identifier: g.identifier,
        name: g.name,
        date: g.date,
        inTime: inTime || "--:--",
        outTime: outTime || "--:--"
      }
    })
  }, [filtered, viewMode])

  const sortedVertical = useMemo(() => [...filtered].sort((a, b) => {
    const aValue = sortKey === "identifier" ? a.raw_identifier : sortKey === "name" ? nameOf(a) : sortKey === "date" ? a.date : sortKey === "time" ? a.time || "" : sortKey === "movement" ? String(a.mark_type ?? 9) : a.date
    const bValue = sortKey === "identifier" ? b.raw_identifier : sortKey === "name" ? nameOf(b) : sortKey === "date" ? b.date : sortKey === "time" ? b.time || "" : sortKey === "movement" ? String(b.mark_type ?? 9) : b.date
    return aValue.localeCompare(bValue) * (sortDirection === "asc" ? 1 : -1)
  }), [filtered, sortKey, sortDirection])
  const sortedHorizontal = useMemo(() => [...groupedMovements].sort((a, b) => {
    const aValue = sortKey === "identifier" ? a.identifier : sortKey === "name" ? a.name : sortKey === "date" ? a.date : sortKey === "entry" ? a.inTime : sortKey === "exit" ? a.outTime : a.date
    const bValue = sortKey === "identifier" ? b.identifier : sortKey === "name" ? b.name : sortKey === "date" ? b.date : sortKey === "entry" ? b.inTime : sortKey === "exit" ? b.outTime : b.date
    return aValue.localeCompare(bValue) * (sortDirection === "asc" ? 1 : -1)
  }), [groupedMovements, sortKey, sortDirection])

  const verticalPage = sortedVertical.slice((page - 1) * pageSize, page * pageSize)
  const horizontalPage: GroupedMovement[] = sortedHorizontal.slice((page - 1) * pageSize, page * pageSize)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDirection(direction => direction === "asc" ? "desc" : "asc")
    else { setSortKey(key); setSortDirection("asc") }
  }

  function SortHeader({ label, column }: { label: string; column: SortKey }) {
    const active = sortKey === column
    return <th><button className="table-sort-button" onClick={() => toggleSort(column)}>{label}<span aria-hidden="true">{active ? (sortDirection === "asc" ? " ▲" : " ▼") : " ↕"}</span></button></th>
  }

  function exportCsv() {
    let rows = []
    let header = []
    
    if (viewMode === "vertical") {
      rows = filtered.map(m => ({
        Identificador: m.raw_identifier,
        Nombre: nameOf(m),
        Fecha: m.date,
        Hora: m.time || "",
        Movimiento: m.mark_type === 0 ? "ENTRADA" : m.mark_type === 1 ? "SALIDA" : "",
      }))
      header = ["Identificador", "Nombre", "Fecha", "Hora", "Movimiento"]
    } else {
      rows = groupedMovements.map(g => ({
        Identificador: g.identifier,
        Nombre: g.name,
        Fecha: g.date,
        Hora: g.inTime,
        Movimiento: g.outTime,
      }))
      header = ["Identificador", "Nombre", "Fecha", "Entrada", "Salida"]
    }

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

  async function exportExcel() {
    await downloadFromApi(api, "/api/movements/export", "movimientos.xlsx", {
      date_start: dateStart,
      date_end: dateEnd,
    })
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
        <label>Vista:</label>
        <select value={viewMode} onChange={e => { setViewMode(e.target.value as "vertical" | "horizontal"); setSortKey("date"); setSortDirection("asc"); setPage(1); }} style={{ padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border-color)", background: "var(--bg-color)", color: "var(--text-color)" }}>
          <option value="vertical">Vertical</option>
          <option value="horizontal">Horizontal</option>
        </select>
        <Search size={15} color="var(--text-muted)" style={{marginLeft: 10}}/>
        <input type="text" value={empFilter} onChange={e => setEmpFilter(e.target.value)}
          placeholder="Nombre, ID, fecha, hora o movimiento..." aria-label="Buscar movimientos" style={{ width: 230 }} />
        <button className="btn" onClick={exportCsv}>Exportar CSV</button>
        <button className="btn" onClick={exportExcel}>Exportar Excel</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /> Actualizar</button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando movimientos...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                {viewMode === "vertical" ? (
                  <tr>
                    <SortHeader label="Identificador" column="identifier" /><SortHeader label="Nombre" column="name" /><SortHeader label="Fecha" column="date" /><SortHeader label="Hora" column="time" /><SortHeader label="Movimiento" column="movement" />
                  </tr>
                ) : (
                  <tr>
                    <SortHeader label="Identificador" column="identifier" /><SortHeader label="Nombre" column="name" /><SortHeader label="Fecha" column="date" /><SortHeader label="Entrada" column="entry" /><SortHeader label="Salida" column="exit" />
                  </tr>
                )}
              </thead>
              <tbody>
                {(viewMode === "vertical" ? verticalPage : horizontalPage).length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin movimientos en el rango seleccionado</td></tr>
                )}
                {viewMode === "vertical" ? verticalPage.map(m => (
                  <tr key={m.id}>
                    <td><code style={{ fontSize: 12 }}>{m.raw_identifier}</code></td>
                    <td>{nameOf(m)}</td>
                    <td>{m.date}</td>
                    <td>{m.time || "--:--"}</td>
                    <td>{markLabel(m.mark_type)}</td>
                  </tr>
                )) : horizontalPage.map((g, idx) => (
                  <tr key={idx}>
                    <td><code style={{ fontSize: 12 }}>{g.identifier}</code></td>
                    <td>{g.name}</td>
                    <td>{g.date}</td>
                    <td>{g.inTime}</td>
                    <td>{g.outTime}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={viewMode === "vertical" ? sortedVertical.length : sortedHorizontal.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
        </>
      )}
    </div>
  )
}
