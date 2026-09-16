"use client"

import type { CSSProperties } from "react"
import { useCallback, useEffect, useState } from "react"
import { useAuth } from "../context/AuthContext"
import { AlertTriangle, ArrowRight, CalendarDays, Clock3, Database, MonitorSmartphone, RefreshCw, Timer, Users } from "lucide-react"
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

interface Option { id: number; name: string }
interface EmployeeOption { id: number; identifier: string; name: string }
interface DashboardCard {
  key: string
  label: string
  count: number
  value: number
  unit: string
  percentage: number
  denominator: number
  period: { date_start: string; date_end: string }
  data_freshness: string
  severity: string
  description?: string
}
interface ActionItem { label: string; severity: string; count: number; target_tab: string; drilldown: Record<string, string | number | null> }
interface TrendPoint { date: string; denominator: number; compliance_rate: number; normal_rate: number; absence_rate: number; incomplete_rate: number; pending_rate: number; justified_rate: number }
interface DeviceHealth { terminal_id: number; name: string; driver_name: string; status: string; severity: string; last_sync: string | null; activity_count: number; minutes_since_sync: number | null }
interface DashboardData {
  period: { date_start: string; date_end: string; timezone?: string }
  filters: Record<string, string | number | null>
  filter_options: { groups: Option[]; shifts: Option[]; terminals: Option[]; employees: EmployeeOption[]; statuses: string[]; branches: string[]; sectors: string[] }
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
  summary: {
    current_week_hours: number
    current_month_hours: number
    total_hours: number
  }
  action_items: ActionItem[]
  trends: TrendPoint[]
  device_health: DeviceHealth[]
  status_counts: Record<string, number>
}

const PRIMARY_CARD_KEYS = ["compliance_rate", "unjustified_absence_rate", "incomplete_rate", "avg_tardiness_per_employee"]
const HOURS_OPTIONS = [
  { value: "period", label: "Período filtrado" },
  { value: "week", label: "Semana actual" },
  { value: "month", label: "Mes actual" },
] as const
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
  const [employee, setEmployee] = useState("")
  const [hoursScope, setHoursScope] = useState<(typeof HOURS_OPTIONS)[number]["value"]>("period")

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
          employee: employee || undefined,
        },
      })
      setData(response.data)
    } catch {
      setError("No se pudo cargar el dashboard")
    } finally {
      setLoading(false)
    }
  }, [api, dateStart, dateEnd, days, groupId, employee])

  useEffect(() => { void load() }, [load])

  function navigateTo(tab: string) {
    window.dispatchEvent(new CustomEvent("srtime:navigate-tab", { detail: { tab } }))
  }

  const primaryCards = data?.overview.cards.filter(card => PRIMARY_CARD_KEYS.includes(card.key)) || []
  const actionItems = data?.action_items.filter(item => item.count > 0).slice(0, 4) || []
  const terminalIssues = data?.device_health.filter(item => item.severity !== "info").slice(0, 4) || []
  const healthyTerminals = data?.device_health.filter(item => item.severity === "info").length || 0
  const selectedGroupName = groupId ? data?.filter_options.groups.find(item => String(item.id) === groupId)?.name || "Grupo seleccionado" : "Todos los grupos"
  const selectedEmployee = employee.trim() || "Todas las personas"
  const selectedHours = data ? (
    hoursScope === "week" ? data.summary.current_week_hours :
    hoursScope === "month" ? data.summary.current_month_hours :
    data.overview.total_hours
  ) : 0

  return (
    <div className="dashboard-tab fade-in">
      <div className="tab-header">
        <div>
          <h2>Dashboard</h2>
          <p>Resumen ejecutivo de asistencia: pocas señales, lectura rápida y acceso directo a lo que requiere acción.</p>
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
        <label>Persona:</label><select value={employee} onChange={event => setEmployee(event.target.value)}><option value="">Todas</option>{data?.filter_options.employees.map(item => <option key={item.id} value={item.identifier}>{item.name} · {item.identifier}</option>)}</select>
      </div>

      {loading && <p className="dashboard-muted">Cargando tablero...</p>}
      {error && <p className="dashboard-error">{error}</p>}
      {!loading && !error && data && <>
        <p className="dashboard-muted dashboard-freshness">
          Período {data.period.date_start} a {data.period.date_end} · Zona {data.period.timezone} · Generado {new Date(data.generated_at).toLocaleString("es-AR")}
        </p>

        <div className="dashboard-kpi-grid">
          {primaryCards.map(card => <KpiCard key={card.key} card={card} />)}
        </div>

        <section className="dashboard-panel dashboard-hours-panel">
          <div className="dashboard-panel-title-row">
            <div>
              <h3>Horas trabajadas</h3>
              <p className="dashboard-muted">Filtrado por {selectedGroupName} · {selectedEmployee}</p>
            </div>
            <select value={hoursScope} onChange={event => setHoursScope(event.target.value as typeof hoursScope)}>
              {HOURS_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </div>
          <div className="dashboard-hours-grid">
            <div className="dashboard-hours-main">
              <span>{HOURS_OPTIONS.find(item => item.value === hoursScope)?.label}</span>
              <strong>{pf.format(selectedHours)} h</strong>
            </div>
            <Metric label="Empleados activos" value={data.overview.active_employees} />
            <Metric label="Terminales activas" value={data.overview.active_terminals} />
            <Metric label="Movimientos pendientes" value={data.overview.raw_pending} />
          </div>
        </section>

        <div className="dashboard-grid" style={{ marginTop: 14 }}>
          <section className="dashboard-panel dashboard-action-panel">
            <h3>Requiere acción</h3>
            {actionItems.length === 0 ? <p className="dashboard-muted">Sin novedades críticas para el filtro actual.</p> : (
              <div className="dashboard-action-grid">
                {actionItems.map(item => (
                  <button className={`dashboard-action-card severity-${item.severity}`} key={item.label} onClick={() => navigateTo(item.target_tab)}>
                    <span>{item.label}</span>
                    <strong>{nf.format(item.count)}</strong>
                    <small>Ver detalle <ArrowRight size={12} /></small>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="dashboard-panel">
            <h3>Terminales</h3>
            <p className="dashboard-muted dashboard-note">
              {nf.format(healthyTerminals)} OK · {nf.format(terminalIssues.length)} requieren revisión
            </p>
            <div className="dashboard-device-list">
              {terminalIssues.map(item => (
                <button className={`dashboard-device-card severity-${item.severity}`} key={item.terminal_id} onClick={() => navigateTo("terminals")}>
                  <MonitorSmartphone size={15} />
                  <span>{item.name}</span>
                  <strong>{item.status}</strong>
                  <small>{item.last_sync ? `sync ${new Date(item.last_sync).toLocaleString("es-AR")}` : "sin sync"}</small>
                </button>
              ))}
              {data.device_health.length === 0 && <p className="dashboard-muted">No hay terminales activas configuradas.</p>}
              {data.device_health.length > 0 && terminalIssues.length === 0 && <p className="dashboard-muted">Todas las terminales activas están sin alertas.</p>}
            </div>
          </section>
        </div>

        <section className="dashboard-panel" style={{ marginTop: 14 }}>
          <h3>Evolución histórica</h3>
          <p className="dashboard-muted" style={{ marginBottom: 12 }}>Tasas diarias sobre jornadas del día. El gráfico muestra señales de cumplimiento, ausentismo, incompletos y pendientes.</p>
          {data.trends.length === 0 ? <p className="dashboard-muted">Sin datos históricos en el rango.</p> : <AttendanceTrendChart data={data.trends} />}
        </section>
      </>}
    </div>
  )
}

function KpiCard({ card }: { card: DashboardCard }) {
  const Icon = card.key === "compliance_rate" ? CalendarDays : card.key === "terminal_problems" ? MonitorSmartphone : card.key === "employees_without_shift" ? Users : card.severity === "alta" || card.severity === "media" ? AlertTriangle : card.key === "justified_rate" ? Clock3 : card.key === "unjustified_absence_rate" ? Database : Timer
  const value = card.unit === "%" ? `${pf.format(card.value)}%` : card.unit ? `${pf.format(card.value)} ${card.unit}` : nf.format(card.value)
  const rawProgress = card.unit === "%" ? card.value : card.key === "avg_tardiness_per_employee" ? (Number(card.value || 0) / 30) * 100 : card.percentage
  const progress = Math.max(0, Math.min(100, Number.isFinite(rawProgress) ? rawProgress : 0))
  return (
    <section className={`dashboard-kpi severity-${card.severity}`}>
      <div className="dashboard-kpi-copy">
        <Icon size={20} />
        <span>{card.label}</span>
        <strong>{value}</strong>
        <small>{nf.format(card.count)} de {nf.format(card.denominator)}{card.unit === "%" ? ` — ${pf.format(card.percentage)}%` : ""}</small>
        {card.description && <em>{card.description}</em>}
      </div>
      <div className="dashboard-donut" style={{ "--progress": `${progress}%` } as CSSProperties}>
        <div><strong>{card.unit === "%" ? pf.format(card.value) : pf.format(progress)}</strong><small>{card.unit === "%" ? "%" : "ref"}</small></div>
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><span>{label}</span><strong>{nf.format(value)}</strong></div>
}

function AttendanceTrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <div className="dashboard-chart">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 18, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(value: string) => value.slice(5)} />
          <YAxis domain={[0, 100]} tickFormatter={(value: number) => `${value}%`} />
          <Tooltip
            formatter={(value, name) => [`${pf.format(Number(value ?? 0))}%`, String(name)]}
            labelFormatter={(label: string) => `Fecha ${label}`}
          />
          <Legend />
          <Line type="monotone" dataKey="compliance_rate" name="Cumplimiento" stroke="#107C10" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="absence_rate" name="Ausentismo" stroke="#D13438" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="incomplete_rate" name="Incompletos" stroke="#F7630C" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="pending_rate" name="Pendientes" stroke="#0A64AD" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
