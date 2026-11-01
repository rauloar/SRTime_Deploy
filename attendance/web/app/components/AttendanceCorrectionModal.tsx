"use client"

import { useState } from "react"
import { X } from "lucide-react"
import { getErrorMessage } from "../utils/messages"
import Notice from "./Notice"

export interface AttendanceCorrectionValues {
  firstIn: string
  lastOut: string
  justification: string
}

interface Props {
  title?: string
  context: string
  firstIn: string | null
  lastOut: string | null
  justification?: string | null
  onClose: () => void
  onSave: (values: AttendanceCorrectionValues) => Promise<void>
}

/** Formulario único para corregir una jornada incompleta y justificarla. */
export default function AttendanceCorrectionModal({
  title = "Justificar asistencia", context, firstIn, lastOut, justification, onClose, onSave,
}: Props) {
  const [entry, setEntry] = useState(firstIn ? firstIn.slice(0, 5) : "08:00")
  const [exit, setExit] = useState(lastOut ? lastOut.slice(0, 5) : "17:00")
  const [reason, setReason] = useState(justification || "")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  async function save() {
    if (!reason.trim()) {
      setError("Indicá el motivo de la justificación.")
      return
    }
    setSaving(true)
    setError("")
    try {
      await onSave({ firstIn: entry, lastOut: exit, justification: reason.trim() })
    } catch (saveError: unknown) {
      setError(getErrorMessage(saveError, "No se pudo guardar la justificación."))
    } finally {
      setSaving(false)
    }
  }

  return <div className="modal-backdrop"><div className="modal-box">
    <div className="modal-title"><span>{title}</span><button className="modal-close" onClick={onClose}><X size={16} /></button></div>
    <p className="absence-modal-context">{context}</p>
    <div className="movement-reference" aria-label="Movimientos registrados originalmente">
      <div><span>Entrada registrada</span><strong>{firstIn ? firstIn.slice(0, 5) : "--:--"}</strong></div>
      <div><span>Salida registrada</span><strong>{lastOut ? lastOut.slice(0, 5) : "--:--"}</strong></div>
    </div>
    <div className="form-group"><label>Entrada real / justificada</label><input type="time" value={entry} onChange={event => setEntry(event.target.value)} /></div>
    <div className="form-group"><label>Salida real / justificada</label><input type="time" value={exit} onChange={event => setExit(event.target.value)} /></div>
    <div className="form-group"><label>Razón de justificación (obligatorio)</label><textarea rows={3} value={reason} onChange={event => setReason(event.target.value)} /></div>
    <Notice kind="error">{error}</Notice>
    <div className="modal-actions"><button className="btn btn-primary" onClick={() => void save()} disabled={saving}>{saving ? "Guardando..." : "Guardar justificación"}</button><button className="btn" onClick={onClose}>Cancelar</button></div>
  </div></div>
}
