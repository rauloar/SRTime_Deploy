import type { AxiosInstance } from "axios"

export async function downloadFromApi(
  api: AxiosInstance,
  url: string,
  filename: string,
  params?: Record<string, string | number | undefined>,
) {
  const response = await api.get(url, { params, responseType: "blob" })
  const objectUrl = URL.createObjectURL(response.data)
  const anchor = document.createElement("a")
  anchor.href = objectUrl
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}
