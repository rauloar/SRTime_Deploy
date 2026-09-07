"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useAuth } from "../context/AuthContext"
import { AlertTriangle, ArrowRight, CalendarDays, Clock3, Database, MonitorSmartphone, RefreshCw, Search, Timer, Users } from "lucide-react"

interface Option { id: number; name: string }
interface DashboardCard {
  key: string
  label: string
  count: number
  percentage: number
  denominator: number
  period: { date_start: string; date_end: string }
  data_freshness: string
  severity: string
}
interface ActionItem { label: string; severity: string; count: number; target_tab: string; drilldown: Record<string, string | number | null> }
interface GroupStatus { group_id: number | null; group_name: string; expected_count: number; status_counts: Record<string, number>; rates: Record<string, number> }
interface TrendPoint { date: string; denominator: number; normal_rate: number; absence_rate: number; incomplete_rate: number; pending_rate: number }
interface HeatmapCell { group: string; date: string; expected_count: number; novelty_count: number; novelty_rate: number }
interface RecentActivity { date: string; time: string; employee: string; event_type: string; terminal: string; status: string; source: string }
interface DeviceHealth { terminal_id: number; name: string; driver_name: string; status: string; severity: string; last_sync: string | null; activity_count: number; minutes_since_sync: number | null }
interface DataQuality { unknown_events: number; duplicate_events: number; pending_raw_events: number; late_events: number; recent_import_sources: { source: string; count: number }[]; notes: string[] }
interface DashboardData {
  period: { date_start: string; date_end: string; timezone?: string }
  filters: Record<string, string | number | null>
  filter_options: { groups: Option[]; shifts: Option[]; terminals: Option[]; statuses: string[]; branches: string[]; sectors: string[] }
  generated_at: string
  overview: {
    cards: DashboardCard[]
    active_employees: number
    active_terminals: number
    raw_pending: number
    total_hours: number
    total_tardiness_minutes: number
    total_overtime_minutes: number
  }
  action_items: ActionItem[]
  status_by_group: GroupStatus[]
  trends: TrendPoint[]
  heatmap: HeatmapCell[]
  recent_activity: RecentActivity[]
  data_quality: DataQuality
  device_health: DeviceHealth[]
  status_counts: Record<string, number>
}

const STATUS_ORDER = ["OK", "INCOMPLETO", "AUSENTE", "PENDIENTE", "JUSTIFICADO", "FERIADO"]
const nf = new Intl.NumberFormat("es-AR")
const pf = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const today = () => new Date().toISOString().slice(0, 10)
const daysAgo = (days: number) => {
  const value = new Date()
  value.setDate(value.getDate() - days)
  return value.toISOString().slice(0, 10)
}

export default function DashboardTab() {
  const { api } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [dateStart, setDateStart] = useState(daysAgo(30))
  const [dateEnd, setDateEnd] = useState(today())
  const [days, setDays] = useState("30")
  const [groupId, setGroupId] = useState("")
  const [shiftId, setShiftId] = useState("")
  const [terminalId, setTerminalId] = useState("")
  const [status, setStatus] = useState("")
  const [employee, setEmployee] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const response = await api.get("/api/analytics/dashboard", {
        params: {
          date_start: dateStart,
          date_end: dateEnd,
          days: days || undefined,
          group_id: groupId || undefined,
          shift_id: shiftId || undefined,
          terminal_id: terminalId || undefined,
          status: status || undefined,
          employee: employee || undefined,
        },
      })
      setData(response.data)
    } catch {
      setError("No se pudo cargar el dashboard")
    } finally {
      setLoading(false)
    }
  }, [api, dateStart, dateEnd, days, groupId, shiftId, terminalId, status, employee])

  useEffect(() => { void load() }, [load])

  const maxTrend = useMemo(() => Math.max(100, ...(data?.trends.flatMap(item => [item.normal_rate, item.absence_rate, item.incomplete_rate, item.pending_rate]) || [0])), [data])
  const visibleHeatmapDates = useMemo(() => Array.from(new Set((data?.heatmap || []).map(item => item.date))).slice(-14), [data])
  const visibleHeatmapGroups = useMemo(() => Array.from(new Set((data?.heatmap || []).map(item => item.group))).slice(0, 8), [data])

  function navigateTo(tab: string) {
    window.dispatchEvent(new CustomEvent("srtime:navigate-tab", { detail: { tab } }))
  }

  return (
    <div className="dashboard-tab fade-in">
      <div className="tab-header">
        <div>
          <h2>Dashboard</h2>
          <p>Consola de RR. HH. y supervisión. Analytics sólo lee datos ya procesados y movimientos existentes.</p>
        </div>
        <button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Actualizar</button>
      </div>

      <div className="filter-bar dashboard-filter-bar">
        <label>Período:</label>
        <select value={days} onChange={event => setDays(event.target.value)}>
          <option value="7">Últimos 7 días</option>
          <option value="30">Últimos 30 días</option>
          <option value="90">Últimos 90 días</option>
          <option value="">Manual</option>
        </select>
        <label>Desde:</label><input type="date" value={dateStart} onChange={event => { setDays(""); setDateStart(event.target.value) }} />
        <label>Hasta:</label><input type="date" value={dateEnd} onChange={event => { setDays(""); setDateEnd(event.target.value) }} />
        <label>Grupo:</label><select value={groupId} onChange={event => setGroupId(event.target.value)}><option value="">Todos</option>{data?.filter_options.groups.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        <label>Turno:</label><select value={shiftId} onChange={event => setShiftId(event.target.value)}><option value="">Todos</option>{data?.filter_options.shifts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        <label>Terminal:</label><select value={terminalId} onChange={event => setTerminalId(event.target.value)}><option value="">Todas</option>{data?.filter_options.terminals.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        <label>Estado:</label><select value={status} onChange={event => setStatus(event.target.value)}><option value="">Todos</option>{STATUS_ORDER.map(item => <option key={item} value={item}>{item}</option>)}</select>
        <label>Empleado/legajo:</label><div className="dashboard-search"><Search size={13} /><input value={employee} onChange={event => setEmployee(event.target.value)} placeholder="Buscar..." /></div>
      </div>

      {loading && <p className="dashboard-muted">Cargando tablero...</p>}
      {error && <p className="dashboard-error">{error}</p>}
      {!loading && !error && data && <>
        <p className="dashboard-muted dashboard-freshness">
          Período {data.period.date_start} a {data.period.date_end} · Zona {data.period.timezone} · Generado {new Date(data.generated_at).toLocaleString("es-AR")}
        </p>

        <div className="dashboard-kpi-grid">
          {data.overview.cards.map(card => <KpiCard key={card.key} card={card} />)}
        </div>

        <section className="dashboard-panel dashboard-action-panel">
          <h3>Requiere acción</h3>
          <div className="dashboard-action-grid">
            {data.action_items.map(item => (
              <button className={`dashboard-action-card severity-${item.severity}`} key={item.label} onClick={() => navigateTo(item.target_tab)}>
                <span>{item.label}</span>
                <strong>{nf.format(item.count)}</strong>
                <small>Severidad {item.severity} <ArrowRight size={12} /></small>
              </button>
            ))}
          </div>
        </section>

        <div className="dashboard-grid" style={{ marginTop: 14 }}>
          <section className="dashboard-panel">
            <h3>Estado por grupo</h3>
            {data.status_by_group.length === 0 ? <p className="dashboard-muted">Sin jornadas procesadas para el filtro.</p> : (
              <div className="dashboard-group-table">
                {data.status_by_group.map(group => (
                  <div className="dashboard-group-row" key={group.group_name}>
                    <div><strong>{group.group_name}</strong><span>{nf.format(group.expected_count)} jornadas esperadas</span></div>
                    <StackedBar counts={group.status_counts} total={group.expected_count} />
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="dashboard-panel">
            <h3>Calidad de datos</h3>
            <div className="dashboard-time-grid">
              <Metric label="Desconocidos" value={data.data_quality.unknown_events} />
              <Metric label="Duplicados visibles" value={data.data_quality.duplicate_events} />
              <Metric label="Raw pendientes" value={data.data_quality.pending_raw_events} />
              <Metric label="Recibidos tardíos" value={data.data_quality.late_events} />
            </div>
            <p className="dashboard-muted dashboard-note">{data.data_quality.notes[0]}</p>
          </section>
        </div>

        <section className="dashboard-panel" style={{ marginTop: 14 }}>
          <h3>Evolución histórica</h3>
          <p className="dashboard-muted" style={{ marginBottom: 12 }}>Porcentajes diarios sobre jornadas del día. No mezcla cantidades con porcentajes.</p>
          <div className="dashboard-trend-grid">
            {data.trends.map(item => (
              <div className="dashboard-trend-row" key={item.date}>
                <span>{item.date.slice(5)}</span>
                <TrendBar label="OK" value={item.normal_rate} max={maxTrend} className="status-ok" />
                <TrendBar label="Aus." value={item.absence_rate} max={maxTrend} className="status-ausente" />
                <TrendBar label="Inc." value={item.incomplete_rate} max={maxTrend} className="status-incompleto" />
                <TrendBar label="Pend." value={item.pending_rate} max={maxTrend} className="status-pendiente" />
                <small>{item.denominator} jorn.</small>
              </div>
            ))}
            {data.trends.length === 0 && <p className="dashboard-muted">Sin datos históricos en el rango.</p>}
          </div>
        </section>

        <section className="dashboard-panel" style={{ marginTop: 14 }}>
          <h3>Mapa de calor de novedades</h3>
          <p className="dashboard-muted" style={{ marginBottom: 12 }}>Color por porcentaje de jornadas con INCOMPLETO, AUSENTE o PENDIENTE. Muestra hasta 14 fechas recientes.</p>
          {visibleHeatmapGroups.length === 0 ? <p className="dashboard-muted">Sin datos para mapa de calor.</p> : (
            <div className="dashboard-heatmap" style={{ gridTemplateColumns: `minmax(120px, .35fr) repeat(${visibleHeatmapDates.length}, minmax(34px, 1fr))` }}>
              <div />
              {visibleHeatmapDates.map(day => <strong key={day}>{day.slice(5)}</strong>)}
              {visibleHeatmapGroups.map(group => <div className="dashboard-heatmap-row" key={group}>
                <span>{group}</span>
                {visibleHeatmapDates.map(day => {
                  const cell = data.heatmap.find(item => item.group === group && item.date === day)
                  return <div key={`${group}-${day}`} className="dashboard-heat-cell" style={{ opacity: cell ? Math.max(.18, cell.novelty_rate / 100) : .08 }} title={`${group} ${day}: ${cell?.novelty_rate || 0}%`} />
                })}
              </div>)}
            </div>
          )}
        </section>

        <div className="dashboard-grid" style={{ marginTop: 14 }}>
          <section className="dashboard-panel">
            <h3>Actividad reciente</h3>
            <div className="table-wrapper"><table className="data-table"><thead><tr><th>Fecha</th><th>Hora</th><th>Empleado</th><th>Evento</th><th>Terminal</th><th>Estado</th></tr></thead><tbody>
              {data.recent_activity.map((item, index) => <tr key={`${item.date}-${item.time}-${index}`}><td>{item.date}</td><td>{item.time}</td><td>{item.employee}</td><td>{item.event_type}</td><td>{item.terminal || item.source}</td><td>{item.status}</td></tr>)}
              {data.recent_activity.length === 0 && <tr><td colSpan={6} className="table-empty">Sin actividad reciente</td></tr>}
            </tbody></table></div>
          </section>

          <section className="dashboard-panel">
            <h3>Terminales</h3>
            <div className="dashboard-device-list">
              {data.device_health.map(item => (
                <button className={`dashboard-device-card severity-${item.severity}`} key={item.terminal_id} onClick={() => navigateTo("terminals")}>
                  <MonitorSmartphone size={15} />
                  <span>{item.name}</span>
                  <strong>{item.status}</strong>
                  <small>{item.activity_count} movimientos · {item.last_sync ? `sync ${new Date(item.last_sync).toLocaleString("es-AR")}` : "sin sync"}</small>
                </button>
              ))}
              {data.device_health.length === 0 && <p className="dashboard-muted">No hay terminales activas configuradas.</p>}
            </div>
          </section>
        </div>
      </>}
    </div>
  )
}

function KpiCard({ card }: { card: DashboardCard }) {
  const Icon = card.key === "expected" ? CalendarDays : card.key === "terminal_problems" ? MonitorSmartphone : card.key === "employees_without_shift" ? Users : card.severity === "alta" || card.severity === "media" ? AlertTriangle : card.key === "ok" ? Database : card.key === "justified" ? Clock3 : Timer
  return (
    <section className={`dashboard-kpi severity-${card.severity}`}>
      <Icon size={20} />
      <span>{card.label}</span>
      <strong>{nf.format(card.count)}</strong>
      <small>{nf.format(card.count)} de {nf.format(card.denominator)} — {pf.format(card.percentage)}%</small>
      <em>{card.period.date_start} / {card.period.date_end}</em>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><span>{label}</span><strong>{nf.format(value)}</strong></div>
}

function StackedBar({ counts, total }: { counts: Record<string, number>; total: number }) {
  return (
    <div className="dashboard-stacked-bar">
      {STATUS_ORDER.map(status => {
        const width = total ? Math.max(1.5, ((counts[status] || 0) / total) * 100) : 0
        return <span key={status} className={`status-${status.toLowerCase()}`} style={{ width: `${width}%` }} title={`${status}: ${counts[status] || 0}`} />
      })}
    </div>
  )
}

function TrendBar({ label, value, max, className }: { label: string; value: number; max: number; className: string }) {
  return <div className="dashboard-trend-cell"><small>{label}</small><div className="dashboard-bar-track"><div className={`dashboard-bar-fill ${className}`} style={{ width: `${(value / max) * 100}%` }} /></div><strong>{pf.format(value)}%</strong></div>
}
