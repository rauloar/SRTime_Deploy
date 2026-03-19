import React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface Props {
  total: number
  page: number
  pageSize: number
  onPageChange: (p: number) => void
  onPageSizeChange: (size: number) => void
  sizes?: number[]
}

export default function Pagination({ total, page, pageSize, onPageChange, onPageSizeChange, sizes = [20, 50, 100] }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, padding: "10px 0", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
      <span>{total === 0 ? "Sin registros" : `${from}–${to} de ${total}`}</span>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {/* Rows per page */}
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontWeight: "var(--font-weight-normal)" }}>
          Filas:
          <select
            value={pageSize}
            onChange={e => { onPageSizeChange(Number(e.target.value)); onPageChange(1) }}
            style={{ width: "auto", padding: "3px 8px", fontSize: 12 }}
          >
            {sizes.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>

        {/* Page controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <button
            className="btn"
            style={{ padding: "4px 8px" }}
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            title="Anterior"
          >
            <ChevronLeft size={14} />
          </button>
          <span style={{ padding: "0 8px", fontWeight: 600, color: "var(--text-main)" }}>
            {page} / {totalPages}
          </span>
          <button
            className="btn"
            style={{ padding: "4px 8px" }}
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            title="Siguiente"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
