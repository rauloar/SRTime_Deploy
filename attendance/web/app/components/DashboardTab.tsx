"use client"

import { useEffect, useRef, useState } from "react"
import { Activity, ArrowRight, CheckCircle2, Clock3, RefreshCw, RotateCcw } from "lucide-react"
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { useAuth } from "../context/AuthContext"
import "./dashboard.css"

interface Card { key: string; label: string; value: number; unit: string; count: number; denominator: number; description?: string; severity: string }
interface Trend { date: string; denominator: number; compliance_rate: number; absence_rate: number; incomplete_rate: number; pending_rate: number; justified_rate: number; counts: Record<string, number> }
interface HeatCell { group: string; date: string; expected_count: number; novelty_count: number; novelty_rate: number }
interface Group { group_id: number | null; group_name: string; status_counts: Record<string, number> }
interface DashboardData {
  period: { date_start: string; date_end: string; timezone: string }
  generated_at: string
  filter_options: { groups: { id: number; name: string }[]; employees: { id: number; identifier: string; name: string }[]; shifts: { id: number; name: string }[] }
  overview: { cards: Card[]; total_hours: number; active_employees: number; raw_pending: number }
  trends: Trend[]
  status_counts: Record<string, number>
  status_by_group: Group[]
  heatmap: HeatCell[]
  action_items: { label: string; severity: string; count: number; target_tab: string }[]
  device_health: { terminal_id: number; name: string; status: string; severity: string; last_sync: string | null }[]
}
const statuses = [
  { key: "OK", label: "Correctos", color: "var(--dash-green)" },
  { key: "AUSENTE", label: "Ausencias", color: "var(--dash-rose)" },
  { key: "INCOMPLETO", label: "Incompletos", color: "var(--dash-amber)" },
  { key: "PENDIENTE", label: "Pendientes", color: "var(--dash-blue)" },
  { key: "JUSTIFICADO", label: "Justificados", color: "var(--dash-purple)" },
  { key: "FERIADO", label: "Feriados", color: "var(--text-muted)" },
]
const primaryKeys = ["compliance_rate", "unjustified_absence_rate", "incomplete_rate", "avg_tardiness_per_employee"]
const number = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 })
const dateLabel = (value: string) => new Date(`${value}T12:00:00`).toLocaleDateString("es-AR", { day: "2-digit", month: "short" })
function localDate(offset = 0) {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
}
function navigate(tab: string) { window.dispatchEvent(new CustomEvent("srtime:navigate-tab", { detail: { tab } })) }
const tooltipStyle = { background: "var(--dash-card)", border: "1px solid var(--border-color)", borderRadius: 8, color: "var(--text-main)" }

export default function DashboardTab() {
  const { api } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [period, setPeriod] = useState("30")
  const [start, setStart] = useState(() => localDate(-29))
  const [end, setEnd] = useState(() => localDate())
  const [group, setGroup] = useState("")
  const [employee, setEmployee] = useState("")
  const [shift, setShift] = useState("")
  const [refresh, setRefresh] = useState(0)
  const [chartMode, setChartMode] = useState("counts")
  const request = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    const id = ++request.current
    if (!start || !end || start > end) {
      setError("Elegí un rango válido: la fecha inicial debe ser anterior o igual a la final.")
      setLoading(false)
      return () => controller.abort()
    }
    setLoading(true)
    setError("")
    api.get<DashboardData>("/api/analytics/dashboard", { signal: controller.signal, params: {
      date_start: start, date_end: end, group_id: group || undefined, employee: employee || undefined, shift_id: shift || undefined,
    } }).then(response => { if (id === request.current && !controller.signal.aborted) setData(response.data) })
      .catch(() => { if (!controller.signal.aborted && id === request.current) setError("No se pudo cargar el panel. Volvé a intentar con Actualizar.") })
      .finally(() => { if (!controller.signal.aborted && id === request.current) setLoading(false) })
    return () => controller.abort()
  }, [api, start, end, group, employee, shift, refresh])

  function choosePeriod(value: string) {
    setPeriod(value)
    if (value !== "custom") { setEnd(localDate()); setStart(localDate(1 - Number(value))) }
  }
  function reset() { choosePeriod("30"); setGroup(""); setEmployee(""); setShift("") }
  const distribution = Object.entries(data?.status_counts || {}).filter(([, count]) => count > 0).map(([key, count]) => ({
    key, count, name: statuses.find(item => item.key === key)?.label || key, color: statuses.find(item => item.key === key)?.color || "var(--text-muted)",
  }))
  const total = distribution.reduce((sum, item) => sum + item.count, 0)
  const actions = data?.action_items.filter(item => item.count > 0) || []
  const dates = [...new Set(data?.heatmap.map(item => item.date) || [])].sort()
  const groups = [...new Set(data?.heatmap.map(item => item.group) || [])]
  const heatCells = new Map(data?.heatmap.map(item => [`${item.group}|${item.date}`, item]))
  const filters = [group, employee, shift].filter(Boolean).length

  return <div className="analytics-dashboard fade-in" aria-busy={loading}>
    <header className="dash-heading">
      <div><span className="dash-eyebrow"><Activity size={14} /> SRTIME · ASISTENCIA Y HORARIOS</span><h2>Panel analítico</h2><p>Una mirada a la asistencia. Un punto de partida para actuar.</p></div>
      <button className="btn" onClick={() => setRefresh(value => value + 1)} disabled={loading}><RefreshCw size={15} /> Actualizar</button>
    </header>
    <div className="dash-toolbar">
      <div className="dash-segments" aria-label="Vista del panel"><button aria-pressed={period === "1"} onClick={() => choosePeriod("1")}>Vista de hoy</button><button aria-pressed={period !== "1"} onClick={() => choosePeriod("30")}>Análisis histórico</button></div>
      {data && !loading && !error && <span className="dash-updated"><Clock3 size={13} /> Actualizado {new Date(data.generated_at).toLocaleString("es-AR")} · {data.period.timezone}</span>}
    </div>
    <section className="dash-filters" aria-label="Filtros del dashboard">
      <label>Período<select value={period} onChange={event => choosePeriod(event.target.value)}><option value="1">Hoy</option><option value="7">Últimos 7 días</option><option value="30">Últimos 30 días</option><option value="90">Últimos 90 días</option><option value="custom">Personalizado</option></select></label>
      <label>Desde<input type="date" value={start} max={end} onChange={event => { setPeriod("custom"); setStart(event.target.value) }} /></label>
      <label>Hasta<input type="date" value={end} min={start} onChange={event => { setPeriod("custom"); setEnd(event.target.value) }} /></label>
      <label>Grupo<select value={group} onChange={event => setGroup(event.target.value)}><option value="">Todos los grupos</option>{data?.filter_options.groups.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Turno<select value={shift} onChange={event => setShift(event.target.value)}><option value="">Todos los turnos</option>{data?.filter_options.shifts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Persona<select value={employee} onChange={event => setEmployee(event.target.value)}><option value="">Todas las personas</option>{data?.filter_options.employees.map(item => <option key={item.id} value={item.identifier}>{item.name}</option>)}</select></label>
      <div className="dash-filter-footer"><span>{filters ? `${filters} filtros adicionales activos` : "Todos los grupos y personas"}</span><button onClick={reset}><RotateCcw size={13} /> Restablecer filtros</button></div>
    </section>
    {loading && <div className="dash-empty" role="status"><RefreshCw size={20} /> Cargando información de asistencia…</div>}
    {error && <div className="dash-error" role="alert">{error}</div>}
    {!loading && !error && data && <>
      <div className="dash-kpis">{primaryKeys.map(key => data.overview.cards.find(card => card.key === key)).filter((card): card is Card => Boolean(card)).map(card => {
        const trendKey = card.key === "compliance_rate" ? "compliance_rate" : card.key === "unjustified_absence_rate" ? "absence_rate" : card.key === "incomplete_rate" ? "incomplete_rate" : null
        return <section className={`dash-kpi severity-${card.severity}`} key={card.key}><span>{card.label}</span><strong>{card.denominator ? `${number.format(card.value)}${card.unit === "%" ? "%" : card.unit ? ` ${card.unit}` : ""}` : "—"}</strong><small>{card.denominator ? (card.unit === "%" ? `${number.format(card.count)} de ${number.format(card.denominator)} jornadas` : `${number.format(card.denominator)} empleados activos`) : "Sin jornadas para calcular"}</small>
          {trendKey && data.trends.length > 1 ? <div className="dash-spark" aria-label={`Tendencia diaria: ${card.label}`}><ResponsiveContainer width="100%" height={44}><AreaChart data={data.trends}><Area type="linear" dataKey={trendKey} stroke="currentColor" fill="currentColor" fillOpacity={0.12} strokeWidth={2} isAnimationActive={false} /></AreaChart></ResponsiveContainer></div> : <p>{card.description || "Indicador del período seleccionado"}</p>}
        </section>
      })}</div>
      <div className="dash-main-grid">
        <section className="dash-panel"><div className="dash-panel-heading"><div><h3>Evolución de la asistencia</h3><p>{dateLabel(data.period.date_start)} — {dateLabel(data.period.date_end)} · jornadas procesadas por día</p></div><select aria-label="Unidad del gráfico" value={chartMode} onChange={event => setChartMode(event.target.value)}><option value="counts">Jornadas</option><option value="rates">Porcentajes</option></select></div>
          {!data.trends.length ? <Empty /> : <div className="dash-chart"><ResponsiveContainer width="100%" height={310}><BarChart data={data.trends} margin={{ top: 16, right: 8, left: -18, bottom: 4 }}><CartesianGrid vertical={false} stroke="var(--border-color)" strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={dateLabel} tick={{ fill: "var(--text-secondary)", fontSize: 11 }} minTickGap={28} /><YAxis domain={chartMode === "rates" ? [0, 100] : [0, "auto"]} tick={{ fill: "var(--text-secondary)", fontSize: 11 }} tickFormatter={value => `${value}${chartMode === "rates" ? "%" : ""}`} /><Tooltip contentStyle={tooltipStyle} labelFormatter={label => dateLabel(String(label))} formatter={(value, name) => [`${number.format(Number(value))}${chartMode === "rates" ? "%" : " jornadas"}`, name]} /><Legend />{statuses.filter(item => item.key !== "FERIADO").map(item => <Bar key={item.key} dataKey={chartMode === "counts" ? `counts.${item.key}` : item.key === "OK" ? "compliance_rate" : item.key === "AUSENTE" ? "absence_rate" : item.key === "INCOMPLETO" ? "incomplete_rate" : item.key === "JUSTIFICADO" ? "justified_rate" : "pending_rate"} name={item.label} stackId="attendance" fill={item.color} maxBarSize={40} />)}</BarChart></ResponsiveContainer></div>}
          <div className="dash-panel-foot"><span><strong>{number.format(data.overview.total_hours)} h</strong> trabajadas en el período</span><span>{number.format(data.overview.active_employees)} empleados activos</span></div>
        </section>
        <section className="dash-panel"><h3>Distribución por estado</h3><p>Registros procesados del período; no representa presencia en tiempo real.</p>{!total ? <Empty /> : <><div className="dash-ring"><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={distribution} dataKey="count" nameKey="name" innerRadius={66} outerRadius={88} paddingAngle={2} stroke="none">{distribution.map(item => <Cell key={item.key} fill={item.color} />)}</Pie><Tooltip contentStyle={tooltipStyle} /></PieChart></ResponsiveContainer><div className="dash-ring-label"><strong>{number.format(total)}</strong><span>registros</span></div></div><ul className="dash-legend">{distribution.map(item => <li key={item.key}><span><i style={{ background: item.color }} />{item.name}</span><strong>{number.format(item.count)} <small>({number.format(item.count / total * 100)}%)</small></strong></li>)}</ul></>}<button className="dash-link" onClick={() => navigate("processed")}>Abrir movimientos procesados <ArrowRight size={15} /></button></section>
      </div>
      <div className="dash-equal-grid">
        <section className="dash-panel"><h3>Comparación por grupo</h3><p>Distribución de jornadas. Seleccioná un grupo para filtrar el panel.</p><div className="dash-group-list">{data.status_by_group.length ? data.status_by_group.map(item => {
          const count = Object.values(item.status_counts).reduce((sum, value) => sum + value, 0)
          return <button className="dash-group" key={item.group_id ?? "none"} disabled={item.group_id === null} onClick={() => setGroup(String(item.group_id))}><span><strong>{item.group_name}</strong><small>{number.format(count)} jornadas</small></span><span className="dash-stack">{statuses.map(status => <i key={status.key} title={`${status.label}: ${item.status_counts[status.key] || 0}`} style={{ width: `${count ? (item.status_counts[status.key] || 0) / count * 100 : 0}%`, background: status.color }} />)}</span></button>
        }) : <Empty />}</div><div className="dash-inline-legend">{statuses.map(item => <span key={item.key}><i style={{ background: item.color }} />{item.label}</span>)}</div></section>
        <section className="dash-panel"><h3>Mapa de incidencias</h3><p>Ausencias, incompletos y pendientes por grupo y fecha. Seleccioná una celda para explorar ese día.</p>{!dates.length ? <Empty /> : <div className="dash-heat-scroll" tabIndex={0} aria-label="Mapa desplazable por fechas"><table className="dash-heat"><thead><tr><th>Grupo</th>{dates.map(day => <th key={day}>{dateLabel(day)}</th>)}</tr></thead><tbody>{groups.map(name => <tr key={name}><th>{name}</th>{dates.map(day => {
          const cell = heatCells.get(`${name}|${day}`)
          return <td key={day}>{cell ? <button className={`dash-heat-cell level-${cell.novelty_rate === 0 ? "zero" : cell.novelty_rate < 25 ? "low" : cell.novelty_rate < 50 ? "mid" : "high"}`} title={`${name}, ${dateLabel(day)}: ${cell.novelty_count} incidencias de ${cell.expected_count} jornadas (${number.format(cell.novelty_rate)}%)`} aria-label={`${name}, ${dateLabel(day)}: ${cell.novelty_count} incidencias de ${cell.expected_count} jornadas. Filtrar día.`} onClick={() => { setPeriod("custom"); setStart(day); setEnd(day); const selected = data.filter_options.groups.find(item => item.name === name); if (selected) setGroup(String(selected.id)) }}>{cell.novelty_count}<small>{number.format(cell.novelty_rate)}%</small></button> : <span title="Sin jornadas">—</span>}</td>
        })}</tr>)}</tbody></table></div>}<div className="dash-inline-legend">Intensidad por proporción: <span>0%</span><span>Menos de 25%</span><span>25–49%</span><span>50% o más</span></div></section>
      </div>
      <div className="dash-main-grid">
        <section className="dash-panel"><h3>Requiere atención</h3><p>Accesos a las secciones donde podés revisar las incidencias.</p><div className="dash-actions">{actions.length ? actions.map(item => <button key={item.label} className={`dash-action severity-${item.severity}`} onClick={() => navigate(item.target_tab)}><span className="dash-action-count">{number.format(item.count)}</span><span>{item.label}</span><ArrowRight size={16} /></button>) : <div className="dash-empty"><CheckCircle2 size={22} /> Sin incidencias para este filtro.</div>}</div>{data.overview.raw_pending > 0 && <p>{number.format(data.overview.raw_pending)} movimientos pendientes de procesamiento.</p>}</section>
        <section className="dash-panel"><h3>Estado de terminales</h3><p>Estado informado por la última lectura del sistema.</p><div className="dash-devices">{data.device_health.length ? data.device_health.map(device => <div className="dash-device" key={device.terminal_id}><span className={`dash-device-dot severity-${device.severity}`} /><div><strong>{device.name}</strong><span>{device.status}</span><small>{device.last_sync ? `Última sincronización: ${new Date(device.last_sync).toLocaleString("es-AR")}` : "Sin sincronización registrada"}</small></div></div>) : <Empty text="No hay terminales activas configuradas." />}</div></section>
      </div>
    </>}
  </div>
}
function Empty({ text = "Sin jornadas procesadas para los filtros seleccionados." }: { text?: string }) { return <div className="dash-empty">{text}</div> }
