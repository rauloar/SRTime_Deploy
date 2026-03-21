"use client"
import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Plus, RefreshCw, Pencil, Trash2, X } from "lucide-react"

interface AuthUser {
  id: number
  username: string
  role: string
  is_active: boolean
  must_change_password: boolean
}

type Role = "root" | "admin" | "supervisor" | "viewer"
const ROLES: Role[] = ["root", "admin", "supervisor", "viewer"]

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop">
      <div className="modal-box">
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

export default function AuthUsersTab() {
  const { api } = useAuth()
  const [items, setItems] = useState<AuthUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [modal, setModal] = useState<"add" | "edit" | null>(null)
  const [current, setCurrent] = useState<Partial<AuthUser> & { password?: string }>({ username: "", role: "viewer", is_active: true })

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const res = await api.get("/api/auth-users/")
      setItems(res.data)
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al cargar usuarios autorizados"))
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  function openAdd() {
    setCurrent({ username: "", role: "viewer", is_active: true, password: "" })
    setModal("add")
    setError("")
  }

  function openEdit(u: AuthUser) {
    setCurrent({ ...u, password: "" })
    setModal("edit")
    setError("")
  }

  async function handleSave() {
    try {
      if (!current.username?.trim()) {
        setError("El usuario es obligatorio")
        return
      }
      if (modal === "add") {
        if (!current.password || current.password.length < 6) {
          setError("La contraseña debe tener al menos 6 caracteres")
          return
        }
        await api.post("/api/auth-users/", {
          username: current.username,
          password: current.password,
          role: current.role,
          is_active: current.is_active,
        })
      } else {
        await api.put(`/api/auth-users/${current.id}`, {
          username: current.username,
          password: current.password || undefined,
          role: current.role,
          is_active: current.is_active,
        })
      }
      setModal(null)
      await load()
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al guardar"))
    }
  }

  async function handleDelete(u: AuthUser) {
    if (!confirm(`¿Eliminar cuenta '${u.username}'?`)) return
    try {
      await api.delete(`/api/auth-users/${u.id}`)
      await load()
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al eliminar"))
    }
  }

  return (
    <div>
      {(modal === "add" || modal === "edit") && (
        <Modal title={modal === "add" ? "Agregar Usuario Autorizado" : "Editar Usuario Autorizado"} onClose={() => setModal(null)}>
          <Field label="Usuario:"><input value={current.username || ""} onChange={e => setCurrent(p => ({ ...p, username: e.target.value }))} /></Field>
          <Field label={modal === "add" ? "Contraseña:" : "Nueva contraseña (opcional):"}>
            <input type="password" value={current.password || ""} onChange={e => setCurrent(p => ({ ...p, password: e.target.value }))} />
          </Field>
          <Field label="Rol:">
            <select value={current.role || "viewer"} onChange={e => setCurrent(p => ({ ...p, role: e.target.value as Role }))}>
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </Field>
          <Field label="Activo:">
            <select value={current.is_active ? "si" : "no"} onChange={e => setCurrent(p => ({ ...p, is_active: e.target.value === "si" }))}>
              <option value="si">Sí</option>
              <option value="no">No</option>
            </select>
          </Field>
          {error && <p style={{ color: "var(--status-error)", fontSize: 13, marginBottom: 10 }}>⚠ {error}</p>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" onClick={handleSave}>Guardar</button>
            <button className="btn" onClick={() => setModal(null)}>Cancelar</button>
          </div>
        </Modal>
      )}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openAdd}><Plus size={15} /> Agregar Cuenta</button>
        <button className="btn" onClick={load}><RefreshCw size={14} /></button>
      </div>

      {error && <p style={{ color: "var(--status-error)", marginBottom: 10 }}>⚠ {error}</p>}
      {loading ? <p style={{ padding: 20, opacity: 0.6 }}>Cargando usuarios autorizados...</p> : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr><th>Usuario</th><th>Rol</th><th>Activo</th><th>Forzar cambio</th><th>Acciones</th></tr>
            </thead>
            <tbody>
              {items.length === 0 && <tr><td colSpan={5} style={{ textAlign: "center", opacity: 0.5, padding: 20 }}>Sin cuentas</td></tr>}
              {items.map(u => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td><code>{u.role}</code></td>
                  <td>{u.is_active ? "Sí" : "No"}</td>
                  <td>{u.must_change_password ? "Sí" : "No"}</td>
                  <td style={{ display: "flex", gap: 6 }}>
                    <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => openEdit(u)}><Pencil size={13} /> Editar</button>
                    <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => handleDelete(u)}><Trash2 size={13} /> Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
