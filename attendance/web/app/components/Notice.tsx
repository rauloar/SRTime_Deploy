"use client"

import { AlertCircle, AlertTriangle, CheckCircle2, Info } from "lucide-react"
import type { MessageKind } from "../utils/messages"

export const MESSAGE_ICONS = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: AlertCircle,
} as const

/** Mensaje dentro de la pantalla (formulario, pestaña). Mismo formato en toda la Web. */
export default function Notice({ kind = "info", children }: { kind?: MessageKind; children: React.ReactNode }) {
  if (children === null || children === undefined || children === "" || children === false) return null
  const Icon = MESSAGE_ICONS[kind]
  return (
    <div className={`notice notice-${kind}`} role={kind === "error" || kind === "warning" ? "alert" : "status"}>
      <Icon size={14} aria-hidden="true" />
      <span>{children}</span>
    </div>
  )
}
