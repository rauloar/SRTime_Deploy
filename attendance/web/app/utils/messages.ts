import axios from "axios"

/**
 * Formato único de mensajes de la UI (paridad con ui/messages.py de Desktop).
 *
 * - kind: info | success | warning | error (el ícono indica el tipo; el título no dice "Error").
 * - title: la acción o sección, en minúscula salvo la inicial ("Probar conexión", "Eliminar turno").
 * - text: una o dos oraciones terminadas en punto, sin emojis.
 * - details: líneas opcionales "Etiqueta: valor" o el detalle técnico del servidor.
 */
export type MessageKind = "info" | "success" | "warning" | "error"

export interface MessageOptions {
  kind: MessageKind
  title: string
  text: string
  details?: string[]
}

/** Mensaje dentro de la pantalla cuando una misma zona muestra resultados y errores. */
export type Feedback = { kind: MessageKind; text: string } | null

export interface ConfirmOptions {
  title: string
  text: string
  confirmLabel?: string
  danger?: boolean
}

/** Texto de error de una respuesta de la API (FastAPI `detail`) o el texto por defecto. */
export function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === "string" && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const items = detail
        .map(item => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : ""))
        .filter(Boolean)
      if (items.length) return items.join(" ")
    }
    if (!error.response) return "No hay respuesta del servidor SRTime. Verificá la conexión."
  }
  return fallback
}
