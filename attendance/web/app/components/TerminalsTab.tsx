"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Plus, RefreshCw, Pencil, Trash2, X, Fingerprint, Activity } from "lucide-react"
import Pagination from "./Pagination"

interface Terminal {
  id: number;
  name: string;
  driver_name: string;
  ip: string;
  port: number;
  connection_params: Record<string, string | number | boolean>;
  has_password?: boolean;
  serial_number?: string;
  is_active: boolean;
  last_sync?: string;
}

interface ParserInfo {
  name: string
  is_driver: boolean
  connection_fields: ConnectionField[]
}

interface ConnectionField {
  name: string
  label: string
  type: "text" | "number" | "password"
  default?: string
}

interface TerminalForm {
  id?: number
  name: string
  driver_name: string
  connection_params: Record<string, string | number | boolean>
  is_active: boolean
}

const EMPTY_TERMINAL: TerminalForm = { name: "", driver_name: "", connection_params: {}, is_active: true }

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop">
      <div className="modal-box" style={{ maxWidth: 450 }}>
        <div className="modal-title"><span>{title}</span><button className="modal-close" onClick={onClose}><X size={16} /></button></div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="form-group"><label>{label}</label>{children}</div>
}

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}

export default function TerminalsTab() {
  const { api } = useAuth()
  const [terminals, setTerminals] = useState<Terminal[]>([])
  const [parsers, setParsers]     = useState<ParserInfo[]>([])
  const [loading, setLoading]   = useState(true)
  const [modal, setModal]       = useState<"add" | "edit" | null>(null)
  const [current, setCurrent]   = useState<TerminalForm>(EMPTY_TERMINAL)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState("")
  const [page, setPage]         = useState(1)
  const [pageSize, setPageSize] = useState(20)
  
  const [testingId, setTestingId] = useState<number | null>(null)
  const [syncingId, setSyncingId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [termRes, parserRes] = await Promise.all([
        api.get("/api/terminals/"),
        api.get("/api/import/parsers")
      ])
      setTerminals(termRes.data.terminals || [])
      
      const pList = parserRes.data.parsers || []
      setParsers((pList as ParserInfo[]).filter(p => p.is_driver))
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  const paginated = terminals.slice((page - 1) * pageSize, page * pageSize)

  function openAdd() { 
    const selected = parsers[0]
    const defaults = Object.fromEntries(
      (selected?.connection_fields || []).map(field => [field.name, field.default || ""])
    )
    setCurrent({ ...EMPTY_TERMINAL, driver_name: selected?.name || "", connection_params: defaults })
    setError(""); setModal("add") 
  }
  function openEdit(t: Terminal) {
    setCurrent({
      id: t.id,
      name: t.name,
      driver_name: t.driver_name,
      connection_params: { ...(t.connection_params || {}) },
      is_active: t.is_active,
    })
    setError(""); setModal("edit")
  }

  async function handleSave() {
    if (!current.name?.trim()) { setError("El nombre de la terminal es obligatorio."); return }
    setSaving(true); setError("")
    try {
      const payload = { 
        name: current.name, 
        driver_name: current.driver_name,
        ip: String(current.connection_params.ip || "") || null,
        port: current.connection_params.port ? Number(current.connection_params.port) : null,
        connection_params: current.connection_params,
        is_active: current.is_active
      }
      
      if (modal === "add") {
        await api.post("/api/terminals/", payload)
      } else {
        await api.put(`/api/terminals/${current.id}`, payload)
      }
      setModal(null); load()
    } catch (e: unknown) { 
      setError(getErrorMessage(e, "Error al guardar el equipo."))
    } finally { 
      setSaving(false) 
    }
  }

  async function handleDelete(t: Terminal) {
    if (!confirm(`¿Eliminar la terminal '${t.name}' definitivamente?`)) return
    try {
      await api.delete(`/api/terminals/${t.id}`)
      load()
    } catch (e) {
      alert(getErrorMessage(e, "Error al eliminar la terminal."))
    }
  }

  async function testConnection(id: number) {
    setTestingId(id)
    try {
      const res = await api.post(`/api/terminals/${id}/test`)
      alert(`✅ Conexión exitosa. MAC: ${res.data.mac} | SN: ${res.data.serial_number}`)
      load() // recargar para mostrar el serial number en la tabla
    } catch (e) {
      alert(getErrorMessage(e, "Error al conectar."))
    } finally {
      setTestingId(null)
    }
  }

  async function syncTime(id: number) {
    setSyncingId(id)
    try {
      await api.post(`/api/terminals/${id}/sync`)
      alert("✅ Sincronización completada.")
    } catch (e) {
      alert(getErrorMessage(e, "Error al sincronizar reloj."))
    } finally {
      setSyncingId(null)
    }
  }

  return (
    <div>
      {(modal === "add" || modal === "edit") && (
        <Modal title={modal === "add" ? "Registrar Terminal" : "Editar Terminal"} onClose={() => setModal(null)}>
          <Field label="Ubicación / Nombre:">
            <input placeholder="Ej: Puerta Principal" value={current.name} onChange={e => setCurrent(p => ({ ...p, name: e.target.value }))} />
          </Field>
          
          {modal === "add" && (
            <Field label="Tecnología (Driver):">
              <select value={current.driver_name} onChange={e => {
                const selected = parsers.find(parser => parser.name === e.target.value)
                setCurrent(p => ({
                  ...p,
                  driver_name: e.target.value,
                  connection_params: Object.fromEntries(
                    (selected?.connection_fields || []).map(field => [field.name, field.default || ""])
                  ),
                }))
              }}>
                <option value="" disabled>Seleccione marca</option>
                {parsers.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
              </select>
            </Field>
          )}

          {(parsers.find(parser => parser.name === current.driver_name)?.connection_fields || []).map(field => (
            <Field key={field.name} label={field.label}>
              <input
                type={field.type}
                placeholder={field.type === "password" && modal === "edit" ? "Dejar vacío para conservar" : undefined}
                value={String(current.connection_params[field.name] ?? "")}
                onChange={e => setCurrent(p => ({
                  ...p,
                  connection_params: { ...p.connection_params, [field.name]: e.target.value },
                }))}
              />
            </Field>
          ))}
          
          <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: 10, marginTop: 10 }}>
            <input 
              type="checkbox" 
              id="is_active" 
              checked={current.is_active} 
              onChange={e => setCurrent(p => ({ ...p, is_active: e.target.checked }))}
              style={{ width: "auto" }}
            />
            <label htmlFor="is_active" style={{ margin: 0, cursor: "pointer" }}>Terminal Activa</label>
          </div>

          {error && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {error}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 15 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? "Guardando..." : "Guardar Equipo"}</button>
            <button className="btn" onClick={() => setModal(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openAdd}><Plus size={15} /> Registrar Terminal</button>
        <button className="btn" onClick={load} disabled={loading}><RefreshCw size={14} /></button>
      </div>

      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando terminales...</p> : (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Estado</th>
                  <th>Ubicación</th>
                  <th>Tecnología</th>
                  <th>Red (IP:Port)</th>
                  <th>Número Serie DB</th>
                  <th>Última Sincronización</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {paginated.length === 0 && <tr><td colSpan={7} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>No hay terminales conectadas. Registra tu equipo biométrico arriba.</td></tr>}
                {paginated.map(t => (
                  <tr key={t.id} style={{ opacity: t.is_active ? 1 : 0.5 }}>
                    <td style={{ textAlign: "center" }}>
                      <Activity size={18} color={t.is_active ? "var(--status-active)" : "var(--status-error)"} />
                    </td>
                    <td><strong>{t.name}</strong></td>
                    <td style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      <Fingerprint size={14} opacity={0.6}/> {t.driver_name}
                    </td>
                    <td>{String(t.connection_params?.ip || t.ip || "—")}:{String(t.connection_params?.port || t.port || "—")}</td>
                    <td style={{ fontFamily: "monospace", opacity: 0.8 }}>{t.serial_number || "—"}</td>
                    <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                      {t.last_sync ? new Date(t.last_sync).toLocaleString() : "Nunca"}
                    </td>
                    <td style={{ display: "flex", gap: 6, flexWrap: "wrap", maxWidth: 280 }}>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => testConnection(t.id)} disabled={testingId === t.id || syncingId === t.id || !t.is_active}>
                        <Activity size={13} /> {testingId === t.id ? "..." : "Píng"}
                      </button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => syncTime(t.id)} disabled={testingId === t.id || syncingId === t.id || !t.is_active}>
                        <RefreshCw size={13} /> {syncingId === t.id ? "..." : "Reloj"}
                      </button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => openEdit(t)}>
                        <Pencil size={13} /> Editar
                      </button>
                      <button className="btn btn-danger" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => handleDelete(t)}>
                        <Trash2 size={13} /> Borrar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={terminals.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
        </>
      )}
    </div>
  )
}
