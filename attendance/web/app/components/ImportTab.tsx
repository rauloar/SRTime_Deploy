"use client"
import { useState, useEffect } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Upload, RefreshCw, Activity, CheckCircle2 } from "lucide-react"

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
}

interface TerminalInfo {
  id: number
  name: string
  ip: string
  is_active: boolean
}

export default function ImportTab() {
  const { api } = useAuth()
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState("Logs: 0 | Nuevos: 0 | Duplicados: 0")
  const [logs, setLogs] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState("")
  const [parsers, setParsers] = useState<ParserInfo[]>([])
  const [terminals, setTerminals] = useState<TerminalInfo[]>([])
  const [selectedParser, setSelectedParser] = useState("")
  const [selectedTerminal, setSelectedTerminal] = useState<number | "">("")
  const [activeTab, setActiveTab] = useState<"file" | "device">("file")

  useEffect(() => {
    async function init() {
      try {
        const [resParsers, resTerminals] = await Promise.all([
          api.get("/api/import/parsers"),
          api.get("/api/terminals/")
        ])
        
        const list = resParsers.data.parsers || []
        setParsers(list)
        const fileList = list.filter((p: any) => !p.is_driver)
        if (fileList.length > 0) setSelectedParser(fileList[0].name)

        const termList = resTerminals.data.terminals || []
        setTerminals(termList)
        const activeTerms = termList.filter((t: TerminalInfo) => t.is_active)
        if (activeTerms.length > 0) {
          setSelectedTerminal(activeTerms[0].id)
        }
      } catch (e) {
        console.error("Error cargando componentes de importación:", e)
      }
    }
    init()
  }, [api])

  function switchTab(tab: "file" | "device") {
    setActiveTab(tab)
    if (tab === "file") {
      const list = parsers.filter(p => !p.is_driver)
      if (list.length > 0) setSelectedParser(list[0].name)
    } else {
      const activeTerms = terminals.filter(t => t.is_active)
      if (activeTerms.length > 0) setSelectedTerminal(activeTerms[0].id)
    }
  }

  async function runImport() {
    if (activeTab === "device") {
      if (!selectedTerminal) return
      setRunning(true); setError(""); setLogs([])
      try {
        const res = await api.post(`/api/import/device/${selectedTerminal}`)
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

    setRunning(true); setError(""); setLogs([])
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
          Desde Red Física
        </button>
      </div>

      <div className="toolbar" style={{ flexWrap: "wrap", gap: 10 }}>
        {activeTab === "device" ? (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 500 }}>
              Equipo Registrado:
            </span>
            <select 
              value={selectedTerminal} 
              onChange={e => setSelectedTerminal(Number(e.target.value))}
              style={{ padding: "6px 10px", borderRadius: 4, border: "1px solid var(--border-color)", background: "var(--bg-color)", color: "var(--text-color)", fontSize: 13, minWidth: 200 }}
            >
              <option value="" disabled>Seleccionar terminal...</option>
              {terminals.map(t => (
                <option key={t.id} value={t.id}>
                  {t.name} {t.is_active ? `(${t.ip})` : '(Inactiva)'}
                </option>
              ))}
            </select>

            {terminals.length === 0 ? (
               <span style={{ opacity: 0.6, fontSize: 12 }}>⚠️ No hay terminales configuradas. Dirígete a la pestaña "Terminales".</span>
            ) : (
                <div style={{ display: "flex", gap: 5, marginLeft: 10 }}>
                  <button className="btn btn-primary" onClick={runImport} disabled={running || !selectedTerminal}>
                    <RefreshCw size={14} /> {running ? "Conectando..." : "Descargar Memorias"}
                  </button>
                </div>
            )}
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
