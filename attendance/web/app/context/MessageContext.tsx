"use client"

import { createContext, useCallback, useContext, useRef, useState, ReactNode } from "react"
import AppDialog from "../components/AppDialog"
import { MESSAGE_ICONS } from "../components/Notice"
import type { ConfirmOptions, MessageOptions } from "../utils/messages"

interface MessageCtx {
  /** Diálogo informativo con un solo botón "Aceptar". Reemplaza a window.alert. */
  showMessage: (options: MessageOptions) => Promise<void>
  /** Diálogo de confirmación; resuelve true sólo si se elige la acción. Reemplaza a window.confirm. */
  confirmAction: (options: ConfirmOptions) => Promise<boolean>
}

type Pending =
  | { type: "message"; options: MessageOptions; resolve: () => void }
  | { type: "confirm"; options: ConfirmOptions; resolve: (value: boolean) => void }

const MessageContext = createContext<MessageCtx | null>(null)

export function MessageProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<Pending | null>(null)
  const active = useRef<Pending | null>(null)
  const queue = useRef<Pending[]>([])

  const push = useCallback((item: Pending) => {
    if (active.current) {
      queue.current.push(item)
      return
    }
    active.current = item
    setCurrent(item)
  }, [])

  const close = useCallback((accepted: boolean) => {
    const done = active.current
    if (!done) return
    if (done.type === "confirm") done.resolve(accepted)
    else done.resolve()
    active.current = queue.current.shift() || null
    setCurrent(active.current)
  }, [])

  const showMessage = useCallback(
    (options: MessageOptions) => new Promise<void>(resolve => push({ type: "message", options, resolve })),
    [push],
  )
  const confirmAction = useCallback(
    (options: ConfirmOptions) => new Promise<boolean>(resolve => push({ type: "confirm", options, resolve })),
    [push],
  )

  let dialog: ReactNode = null
  if (current) {
    const kind = current.type === "message" ? current.options.kind : current.options.danger ? "warning" : "info"
    const Icon = MESSAGE_ICONS[kind]
    const details = current.type === "message" ? current.options.details || [] : []
    const actions = current.type === "message"
      ? [{ label: "Aceptar", variant: "primary" as const, onClick: () => close(true) }]
      : [
          { label: "Cancelar", onClick: () => close(false) },
          {
            label: current.options.confirmLabel || "Aceptar",
            variant: current.options.danger ? "danger" as const : "primary" as const,
            onClick: () => close(true),
          },
        ]
    dialog = (
      <AppDialog title={current.options.title} onClose={() => close(false)} actions={actions}>
        <div className={`message-dialog message-dialog-${kind}`}>
          <Icon size={22} aria-hidden="true" />
          <div>
            <p className="message-dialog-text">{current.options.text}</p>
            {details.length > 0 && (
              <ul className="message-dialog-details">
                {details.map((line, index) => <li key={index}>{line}</li>)}
              </ul>
            )}
          </div>
        </div>
      </AppDialog>
    )
  }

  return (
    <MessageContext.Provider value={{ showMessage, confirmAction }}>
      {children}
      {dialog}
    </MessageContext.Provider>
  )
}

export function useMessages() {
  const ctx = useContext(MessageContext)
  if (!ctx) throw new Error("useMessages debe usarse dentro de MessageProvider")
  return ctx
}
