# SRTime: servidor DEV desde el código

Para probar cambios de código se levanta la API FastAPI directamente desde el
repositorio, con el frontend estático ya exportado. Hay **un solo** script de
inicio: `deploy\web\start-branch-dev-server.ps1`. Los artefactos compilados
(Nuitka, PyInstaller) se prueban recién con sus instaladores, después de la QA
en DEV.

## Requisitos

| Elemento | Ubicación | Notas |
| --- | --- | --- |
| Entorno Python | `.venv-test` en la raíz del proyecto | Único venv para tests, servidor DEV y builds. No usar `.venv` ni Python global. |
| Configuración | `config\.env` | Ignorado por Git. Plantilla: `config\.env.example`. Incluye la base PostgreSQL de prueba y `SRTIME_ENABLED_ADDONS`. |
| Frontend | `attendance\web\out` | Export estático de Next.js (`next build`). Rearmarlo después de cambiar el frontend. |
| PostgreSQL | El indicado en `config\.env` | Nunca se agregan contraseñas reales a la plantilla, la documentación ni Git. |

Los addons habilitados (por ejemplo `sundial`, `zkteco`) se declaran en
`SRTIME_ENABLED_ADDONS` de `config\.env`; el servidor los lee al arrancar.

## Iniciar y detener

```powershell
.\deploy\web\start-branch-dev-server.ps1
```

Abre la API y la web en `http://127.0.0.1:8000`. Se detiene con `Ctrl+C`. El
script no crea servicios ni arranques automáticos. Si otro proceso ocupa el
puerto 8000 (por ejemplo un SRTime instalado en WSL), detenerlo antes.

Con una base vacía, el asistente de primer uso pide la conexión PostgreSQL y
después la cuenta inicial `admin`.

## Después de cambiar el frontend

```powershell
cd attendance\web
npm run build
```

Luego reiniciar el servidor DEV.
