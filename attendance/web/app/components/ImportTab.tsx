"use client"
import { useState, useEffect } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Upload, RefreshCw } from "lucide-react"

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}

interface ParserInfo {
  name: string
  is_driver: boolean
  connection_fields: any[]
}

export default function ImportTab() {
  const { api } = useAuth()
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState("Logs: 0 | Nuevos: 0 | Duplicados: 0")
  const [logs, setLogs] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState("")
  const [parsers, setParsers] = useState<ParserInfo[]>([])
  const [selectedParser, setSelectedParser] = useState("")
  const [driverParams, setDriverParams] = useState<Record<string, string>>({})
  const [activeTab, setActiveTab] = useState<"file" | "device">("file")
  const [testing, setTesting] = useState(false)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    api.get("/api/import/parsers").then(res => {
      const list = res.data.parsers || []
      setParsers(list)
      const fileList = list.filter((p: any) => !p.is_driver)
      if (fileList.length > 0) setSelectedParser(fileList[0].name)
    }).catch(e => console.error("Error cargando parsers:", e))
  }, [api])

  function switchTab(tab: "file" | "device") {
    setActiveTab(tab)
    const list = tab === "file" ? parsers.filter(p => !p.is_driver) : parsers.filter(p => p.is_driver)
    if (list.length > 0) setSelectedParser(list[0].name)
  }

  const selectedInfo = parsers.find(p => p.name === selectedParser)

  async function testConnection() {
    setTesting(true)
    setError("")
    setLogs([])
    try {
      const payloadParams = { ...driverParams }
      selectedInfo?.connection_fields?.forEach((f: any) => {
        if (payloadParams[f.name] === undefined) payloadParams[f.name] = f.default
      })
      const res = await api.post("/api/import/device/test", { parser_name: selectedParser, params: payloadParams })
      setStatus(`Conexión exitosa. MAC: ${res.data.mac}`)
      setLogs([`Dispositivo: ${res.data.name}`, `Hora local: ${res.data.time}`])
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al probar conexión"))
    } finally {
      setTesting(false)
    }
  }

  async function syncTime() {
    setSyncing(true)
    setError("")
    setLogs([])
    try {
      const payloadParams = { ...driverParams }
      selectedInfo?.connection_fields?.forEach((f: any) => {
        if (payloadParams[f.name] === undefined) payloadParams[f.name] = f.default
      })
      await api.post("/api/import/device/sync", { parser_name: selectedParser, params: payloadParams })
      setStatus(`Sincronización de hora completada.`)
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al sincronizar hora"))
    } finally {
      setSyncing(false)
    }
  }

  async function runImport() {
    if (activeTab === "device") {
      setRunning(true)
      setError("")
      setLogs([])
      try {
        const payloadParams = { ...driverParams }
        selectedInfo?.connection_fields?.forEach((f: any) => {
          if (payloadParams[f.name] === undefined) payloadParams[f.name] = f.default
        })
        const res = await api.post("/api/import/device", { parser_name: selectedParser, params: payloadParams })
        setStatus(`Logs: ${res.data.total} | Nuevos: ${res.data.nuevos} | Duplicados: ${res.data.duplicados}`)
        setLogs((res.data.logs || []) as string[])
      } catch (e: unknown) {
        setError(getErrorMessage(e, "Error conectando al dispositivo"))
      } finally {
        setRunning(false)
      }
      return
    }

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
      const query = selectedParser ? `?parser_name=${encodeURIComponent(selectedParser)}` : ""
      const res = await api.post("/api/import/txt" + query, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setStatus(`Logs: ${res.data.total} | Nuevos: ${res.data.nuevos} | Duplicados: ${res.data.duplicados}`)
      setLogs((res.data.logs || []) as string[])
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al importar"))
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
      <div style={{ display: "flex", gap: 2, marginBottom: 20, background: "var(--bg-color)", padding: 4, borderRadius: 8, width: "fit-content", border: "1px solid var(--border-color)" }}>
        <button 
          onClick={() => switchTab('file')}
          style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: activeTab === 'file' ? "var(--primary-color)" : "transparent", color: activeTab === 'file' ? "#fff" : "var(--text-color)", fontWeight: activeTab === 'file' ? "bold" : "normal", cursor: "pointer" }}
        >
          Desde Archivo
        </button>
        <button 
          onClick={() => switchTab('device')}
          style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: activeTab === 'device' ? "var(--primary-color)" : "transparent", color: activeTab === 'device' ? "#fff" : "var(--text-color)", fontWeight: activeTab === 'device' ? "bold" : "normal", cursor: "pointer" }}
        >
          Desde Terminal
        </button>
      </div>

      <div className="toolbar" style={{ flexWrap: "wrap", gap: 10 }}>
        {activeTab === "device" && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 500 }}>
              Controlador Biométrico:
            </span>
            <select 
              value={selectedParser} 
              onChange={e => setSelectedParser(e.target.value)}
              style={{ padding: "6px 10px", borderRadius: 4, border: "1px solid var(--border-color)", background: "var(--bg-color)", color: "var(--text-color)", fontSize: 13 }}
            >
              {parsers.filter(p => p.is_driver).map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
            </select>
          </div>
        )}
        
        {activeTab === "device" ? (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
             {selectedInfo?.connection_fields?.map((f: any) => (
               <div key={f.name} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                 <label style={{ fontSize: 13 }}>{f.label}:</label>
                 <input 
                   type={f.type === "number" ? "number" : "text"} 
                   defaultValue={f.default ?? ""}
                   onChange={e => setDriverParams(prev => ({...prev, [f.name]: e.target.value}))}
                   style={{ padding: "6px 8px", width: 140, borderRadius: 4, border: "1px solid var(--border-color)", background: "var(--bg-color)", color: "var(--text-color)", fontSize: 13 }}
                 />
               </div>
             ))}
             <div style={{ display: "flex", gap: 5, width: "100%", marginTop: 5 }}>
               <button className="btn" onClick={testConnection} disabled={testing || running || syncing}>
                 {testing ? "Probando..." : "Probar Conexión"}
               </button>
               <button className="btn" onClick={syncTime} disabled={testing || running || syncing}>
                 {syncing ? "Sincronizando..." : "Sincronizar Hora"}
               </button>
               <button className="btn btn-primary" onClick={runImport} disabled={testing || running || syncing}>
                 <RefreshCw size={14} /> {running ? "Conectando..." : "Descargar e Importar Logs"}
               </button>
             </div>
          </div>
        ) : (
          <>
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
          </>
        )}
        <button className="btn" onClick={clearView} disabled={running}>
          <RefreshCw size={14} /> Limpiar
        </button>
      </div>

      <div className="filter-bar" style={{ marginBottom: 10 }}>
        <strong>{status}</strong>
        {activeTab === "file" && (
          <span style={{ marginLeft: "auto", opacity: 0.7, fontSize: 12 }}>
            Archivo: {file ? file.name : "(no seleccionado)"}
          </span>
        )}
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
