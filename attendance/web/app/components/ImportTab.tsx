"use client"
import { useState, useEffect } from "react"
import { useAuth } from "../context/AuthContext"
import axios from "axios"
import { Upload, RefreshCw } from "lucide-react"
import OperationProgress, { OperationJob } from "./OperationProgress"

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
  is_parser: boolean
  ui_features?: {
    file_import?: boolean
    network_import?: boolean
    file_extensions?: string[]
    file_name_patterns?: string[]
    file_format_hint?: string
  }
}

interface TerminalInfo {
  id: number
  name: string
  ip: string
  is_active: boolean
}

export default function ImportTab({ fileImport, networkImport }: { fileImport: boolean; networkImport: boolean }) {
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
  const [activeTab, setActiveTab] = useState<"file" | "device">(fileImport ? "file" : "device")
  const [job, setJob] = useState<OperationJob | null>(null)

  useEffect(() => {
    async function init() {
      try {
        const [resParsers, resTerminals] = await Promise.all([
          api.get("/api/import/parsers"),
          api.get("/api/terminals/")
        ])
        
        const list = resParsers.data.parsers || []
        setParsers(list)
        const fileList = (list as ParserInfo[]).filter(p => p.is_parser && p.ui_features?.file_import)
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

  useEffect(() => {
    setActiveTab(fileImport ? "file" : "device")
  }, [fileImport, networkImport])

  useEffect(() => {
    if (!job || job.state === "completed" || job.state === "failed") return
    const timer = window.setInterval(async () => {
      try {
        const res = await api.get(`/api/import/jobs/${job.id}`)
        const next = res.data as OperationJob
        setJob(next)
        if (next.state === "completed") {
          const result = next.result || {}
          setStatus(`Logs: ${result.total || 0} | Nuevos: ${result.nuevos || 0} | Duplicados: ${result.duplicados || 0}`)
          setLogs(result.logs || [])
          setRunning(false)
        }
        if (next.state === "failed") { setError(next.error || next.message); setRunning(false) }
      } catch { setError("No se pudo consultar el progreso de importación"); setRunning(false) }
    }, 500)
    return () => window.clearInterval(timer)
  }, [api, job])

  function switchTab(tab: "file" | "device") {
    if ((tab === "file" && !fileImport) || (tab === "device" && !networkImport)) return
    setActiveTab(tab)
    if (tab === "file") {
      const list = parsers.filter(p => p.is_parser && p.ui_features?.file_import)
      if (list.length > 0) setSelectedParser(list[0].name)
    } else {
      const activeTerms = terminals.filter(t => t.is_active)
      if (activeTerms.length > 0) setSelectedTerminal(activeTerms[0].id)
    }
  }

  async function testConnection() {
    if (!selectedTerminal) return
    setRunning(true); setError(""); setLogs([])
    try {
      const res = await api.post(`/api/terminals/${selectedTerminal}/test`)
      setStatus("Conexión exitosa")
      setLogs([
        `Modelo: ${res.data.model || "N/D"}`,
        `Firma: ${res.data.firmware || "N/D"}`,
        `Número de Serie: ${res.data.serial_number || "N/D"}`,
        `MAC: ${res.data.mac || "N/D"}`,
        `Hora Reloj: ${res.data.time || "N/D"}`
      ])
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al probar la conexión con el dispositivo"))
    } finally {
      setRunning(false)
    }
  }

  async function syncTime() {
    if (!selectedTerminal) return
    setRunning(true); setError(""); setLogs([])
    try {
      await api.post(`/api/terminals/${selectedTerminal}/sync`)
      setStatus("Hora sincronizada")
      setLogs(["Sincronización completada"])
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al sincronizar la hora del dispositivo"))
    } finally {
      setRunning(false)
    }
  }

  async function runImport() {
    if (activeTab === "device") {
      if (!selectedTerminal) return
      setRunning(true); setError(""); setLogs([])
      try {
        const res = await api.post(`/api/import/terminal/${selectedTerminal}/pull-logs`)
        setStatus(`Logs: ${res.data.total} | Nuevos: ${res.data.nuevos} | Duplicados: ${res.data.duplicados}`)
        setLogs((res.data.logs || []) as string[])
      } catch (e: unknown) {
        setError(getErrorMessage(e, "Error al descargar logs del dispositivo"))
      } finally {
        setRunning(false)
      }
      return
    }

    if (!file) {
      setError("Selecciona un archivo primero")
      return
    }
    const parser = parsers.find(item => item.name === selectedParser)
    const allowedExtensions = parser?.ui_features?.file_extensions || [".txt"]
    const extension = `.${file.name.split(".").pop()?.toLowerCase() || ""}`
    if (!allowedExtensions.includes(extension)) {
      setError(`El formato seleccionado admite: ${allowedExtensions.join(", ")}`)
      return
    }

    setRunning(true); setError(""); setLogs([])
    try {
      const form = new FormData()
      form.append("file", file)
      const query = selectedParser ? `?parser_name=${encodeURIComponent(selectedParser)}` : ""
      const res = await api.post("/api/import/txt/jobs" + query, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setJob(res.data as OperationJob)
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Error al importar"))
      setRunning(false)
    }
  }

  function clearView() {
    setStatus("Logs: 0 | Nuevos: 0 | Duplicados: 0")
    setLogs([])
    setError("")
    setJob(null)
  }

  function selectFile(nextFile: File | null) {
    setFile(nextFile)
    if (!nextFile) return
    const extension = `.${nextFile.name.split(".").pop()?.toLowerCase() || ""}`
    const matchingParser = parsers.find(item =>
      item.is_parser &&
      item.ui_features?.file_import &&
      (item.ui_features.file_extensions || [".txt"]).includes(extension),
    )
    if (matchingParser) setSelectedParser(matchingParser.name)
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 2, marginBottom: 20, background: "var(--bg-color)", padding: 4, borderRadius: 8, width: "fit-content", border: "1px solid var(--border-color)" }}>
        <button 
          onClick={() => switchTab('file')}
          hidden={!fileImport}
          style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: activeTab === 'file' ? "var(--primary-color)" : "transparent", color: activeTab === 'file' ? "#fff" : "var(--text-color)", fontWeight: activeTab === 'file' ? "bold" : "normal", cursor: "pointer" }}
        >
          Desde Archivo
        </button>
        <button 
          onClick={() => switchTab('device')}
          hidden={!networkImport}
          style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: activeTab === 'device' ? "var(--primary-color)" : "transparent", color: activeTab === 'device' ? "#fff" : "var(--text-color)", fontWeight: activeTab === 'device' ? "bold" : "normal", cursor: "pointer" }}
        >
          Desde Red Física
        </button>
      </div>

      <div className="toolbar" style={{ flexWrap: "wrap", gap: 10 }}>
        {activeTab === "device" && networkImport ? (
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
               <span style={{ opacity: 0.6, fontSize: 12 }}>⚠️ No hay terminales configuradas. Dirígete a la pestaña &quot;Terminales&quot;.</span>
            ) : (
                <div style={{ display: "flex", gap: 5, marginLeft: 10 }}>
                  <button className="btn" onClick={testConnection} disabled={running || !selectedTerminal}>
                    Probar Conexión
                  </button>
                  <button className="btn" onClick={syncTime} disabled={running || !selectedTerminal}>
                    Sincronizar Hora
                  </button>
                  <button className="btn btn-primary" onClick={runImport} disabled={running || !selectedTerminal}>
                    <RefreshCw size={14} /> {running ? "Conectando..." : "Descargar Memorias"}
                  </button>
                </div>
            )}
          </div>
        ) : fileImport ? (
          <>
            <select
              value={selectedParser}
              onChange={event => setSelectedParser(event.target.value)}
              aria-label="Formato de archivo"
              style={{ padding: "6px 10px", borderRadius: 4, border: "1px solid var(--border-color)", background: "var(--bg-color)", color: "var(--text-color)", fontSize: 13 }}
            >
              {parsers.filter(item => item.is_parser && item.ui_features?.file_import).map(item => (
                <option key={item.name} value={item.name}>{item.name}</option>
              ))}
            </select>
            <label className="btn" style={{ cursor: "pointer" }}>
              <Upload size={14} /> Buscar Archivo
              <input
                type="file"
                accept={(parsers.find(item => item.name === selectedParser)?.ui_features?.file_extensions || [".txt"]).join(",")}
                style={{ display: "none" }}
                onChange={e => selectFile(e.target.files?.[0] || null)}
              />
            </label>
            <button className="btn btn-primary" onClick={runImport} disabled={running || !file}>
              <Upload size={14} /> {running ? "Importando..." : "Importar archivo"}
            </button>
          </>
        ) : null}
        <button className="btn" onClick={clearView} disabled={running}>
          <RefreshCw size={14} /> Limpiar
        </button>
      </div>

      <div className="filter-bar" style={{ marginBottom: 10 }}>
        <strong>{status}</strong>
        {activeTab === "file" && (
          <span style={{ marginLeft: "auto", opacity: 0.7, fontSize: 12 }}>
            Formato: {parsers.find(item => item.name === selectedParser)?.ui_features?.file_format_hint || "archivo de asistencia"} · Archivo: {file ? file.name : "(no seleccionado)"}
          </span>
        )}
      </div>

      <OperationProgress job={job} />

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
