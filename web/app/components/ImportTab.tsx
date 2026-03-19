"use client"
import { useState } from "react"
import { useAuth } from "../context/AuthContext"
import { Upload, RefreshCw } from "lucide-react"

export default function ImportTab() {
  const { api } = useAuth()
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState("Logs: 0 | Nuevos: 0 | Duplicados: 0")
  const [logs, setLogs] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState("")

  async function runImport() {
    if (!file) {
      setError("Selecciona un archivo primero")
      return
    }
    const ext = file.name.toLowerCase()
    if (!ext.endsWith(".txt")) {
      setError("Solo se admite importación de archivos .txt en la web")
      return
    }

    setRunning(true)
    setError("")
    setLogs([])

    try {
      const form = new FormData()
      form.append("file", file)
      const res = await api.post("/api/import/txt", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setStatus(`Logs: ${res.data.total} | Nuevos: ${res.data.nuevos} | Duplicados: ${res.data.duplicados}`)
      setLogs((res.data.logs || []) as string[])
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Error al importar")
    } finally {
      setRunning(false)
    }
  }

  function clearView() {
    setStatus("Logs: 0 | Nuevos: 0 | Duplicados: 0")
    setLogs([])
    setError("")
  }

  return (
    <div>
      <div className="toolbar">
        <label className="btn" style={{ cursor: "pointer" }}>
          <Upload size={14} /> Buscar Archivo
          <input
            type="file"
            accept=".txt"
            style={{ display: "none" }}
            onChange={e => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <button className="btn btn-primary" onClick={runImport} disabled={running || !file}>
          <Upload size={14} /> {running ? "Importando..." : "Importar TXT"}
        </button>
        <button className="btn" onClick={clearView} disabled={running}>
          <RefreshCw size={14} /> Limpiar
        </button>
      </div>

      <div className="filter-bar" style={{ marginBottom: 10 }}>
        <strong>{status}</strong>
        <span style={{ marginLeft: "auto", opacity: 0.7, fontSize: 12 }}>
          Archivo: {file ? file.name : "(no seleccionado)"}
        </span>
      </div>

      {error && <p style={{ color: "var(--status-error)", marginBottom: 10 }}>⚠ {error}</p>}

      <div className="table-wrapper" style={{ maxHeight: 300, overflowY: "auto", padding: 10 }}>
        {logs.length === 0 ? (
          <p style={{ opacity: 0.6, padding: 10 }}>Sin mensajes de importación.</p>
        ) : (
          <pre style={{ margin: 0, fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
            {logs.join("\n")}
          </pre>
        )}
      </div>
    </div>
  )
}
