import type { Metadata } from "next"
import "./globals.css"
import { AuthProvider } from "./context/AuthContext"

export const metadata: Metadata = {
  title: "SRTime",
  description: "Sistema de Control de Asistencias",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/img/sr_logo.png" type="image/png" />
        <link rel="shortcut icon" href="/img/sr_logo.png" type="image/png" />
      </head>
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  )
}
