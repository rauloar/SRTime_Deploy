import type { AxiosInstance } from "axios"

export type CsvValue = string | number | boolean | null | undefined
export type CsvRow = Record<string, CsvValue>

// Nombre que define el servidor en Content-Disposition (sin rutas: sólo el último segmento).
function serverFilename(header: unknown): string | null {
  if (typeof header !== "string") return null
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header)
  if (!match) return null
  const name = decodeURIComponent(match[1].trim()).split(/[\\/]/).pop()
  return name || null
}

export async function downloadFromApi(
  api: AxiosInstance,
  url: string,
  fallbackFilename: string,
  params?: Record<string, string | number | undefined>,
) {
  const response = await api.get(url, { params, responseType: "blob" })
  const objectUrl = URL.createObjectURL(response.data)
  const anchor = document.createElement("a")
  anchor.href = objectUrl
  anchor.download = serverFilename(response.headers["content-disposition"]) || fallbackFilename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}

export function downloadCsv(headers: string[], rows: CsvRow[], filename: string) {
  const escapeCsv = (value: CsvValue) => `"${String(value ?? "").replaceAll('"', '""')}"`
  const lines = [
    headers.join(","),
    ...rows.map(row => headers.map(header => escapeCsv(row[header])).join(",")),
  ]
  const objectUrl = URL.createObjectURL(new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" }))
  const anchor = document.createElement("a")
  anchor.href = objectUrl
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}
