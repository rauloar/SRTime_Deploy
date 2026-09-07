"use client"

import { X } from "lucide-react"

export interface AppDialogAction {
  label: string
  onClick: () => void
  variant?: "primary" | "danger" | "default"
  disabled?: boolean
}

export default function AppDialog({
  title,
  children,
  onClose,
  actions = [],
}: {
  title: string
  children: React.ReactNode
  onClose: () => void
  actions?: AppDialogAction[]
}) {
  return (
    <div className="modal-backdrop">
      <div className="modal-box">
        <div className="modal-title">
          <span>{title}</span>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div>{children}</div>
        {actions.length > 0 && (
          <div className="modal-actions" style={{ marginTop: 16 }}>
            {actions.map(action => (
              <button
                key={action.label}
                className={`btn ${action.variant === "primary" ? "btn-primary" : action.variant === "danger" ? "btn-danger" : ""}`}
                disabled={action.disabled}
                onClick={action.onClick}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
