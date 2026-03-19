"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"

interface Movement {
  id: number
  raw_identifier: string
  employee_id: number | null
  first_name: string | null
  last_name: string | null
  date: string
  time: string | null
  mark_type: number | null
}

interface User { id: number; identifier: string; first_name: string | null; last_name: string | null }

function today() { return new Date().toISOString().slice(0, 10) }
function daysAgo(n: number) { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10) }

export default function MovementsTab() {
  const { api } = useAuth()
  const [movements, setMovements] = useState<Movement[]>([])
  const [users, setUsers]         = useState<User[]>([])
  const [loading, setLoading]     = useState(true)
  const [dateStart, setDateStart] = useState(daysAgo(7))
  const [dateEnd, setDateEnd]     = useState(today())
  const [empFilter, setEmpFilter] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    const [m, u] = await Promise.all([
      api.get("/api/movements/", { params: { date_start: dateStart, date_end: dateEnd, limit: 2000 } }),
      api.get("/api/users/")
    ])
    setMovements(m.data)
    setUsers(u.data)
    setLoading(false)
  }, [api, dateStart, dateEnd])

  useEffect(() => { load() }, [load])

  // Build a lookup map for user display names
  const nameOf = (mov: Movement) => {
    if (mov.last_name || mov.first_name) {
      return `${mov.last_name || ""}, ${mov.first_name || ""}`.replace(/^,\s*/, "")
    }
    return mov.raw_identifier
  }

  const filtered = movements.filter(m => {
    if (!empFilter) return true
    const n = nameOf(m).toLowerCase() + m.raw_identifier.toLowerCase()
    return n.includes(empFilter.toLowerCase())
  })

  const markLabel = (t: number | null) => {
    if (t === 0) return <span style={{ color: "#27ae60", fontWeight: 700 }}>⬆ ENTRADA</span>
    if (t === 1) return <span style={{ color: "#c0392b", fontWeight: 700 }}>⬇ SALIDA</span>
    return <span style={{ opacity: 0.5 }}>—</span>
  }

  return (
    <div className="tab-content">
      <div className="filter-bar" style={{ marginBottom: 10 }}>
        <label>Desde:</label>
        <input type="date" value={dateStart} onChange={e => setDateStart(e.target.value)} />
        <label>Hasta:</label>
        <input type="date" value={dateEnd} onChange={e => setDateEnd(e.target.value)} />
        <label>🔍 Empleado:</label>
        <input
          type="text"
          value={empFilter}
          onChange={e => setEmpFilter(e.target.value)}
          placeholder="Nombre o identificador..."
          style={{ width: 200 }}
        />
        <button className="btn" onClick={load} disabled={loading}>↻ Actualizar</button>
      </div>

      {loading ? (
        <p style={{ padding: 20, opacity: 0.6 }}>Cargando movimientos...</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Identificador</th>
                <th>Nombre</th>
                <th>Fecha</th>
                <th>Hora</th>
                <th>Movimiento</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>
                    Sin movimientos en el rango seleccionado
                  </td>
                </tr>
              )}
              {filtered.map(m => (
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
          <p style={{ fontSize: 12, opacity: 0.6, marginTop: 8 }}>
            {filtered.length} de {movements.length} movimientos
          </p>
        </div>
      )}
    </div>
  )
}
