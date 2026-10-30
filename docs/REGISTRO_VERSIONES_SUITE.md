# Registro de versiones de SRTime

Este registro identifica las entregas de la suite completa. Los instaladores Web y Desktop son artefactos de una misma versión de suite; no son líneas de producto versionadas de forma independiente.

## Convenciones de estado

- **En desarrollo**: cambios locales sin aprobación de QA.
- **QA**: build disponible para pruebas; no es una entrega publicada.
- **Operativa beta**: funcionalidad aprobada para pruebas controladas.
- **Release**: tag y artefactos publicados con migración y documentación verificadas.
- **Retirada**: no debe usarse para instalaciones nuevas.

## Convención de entorno para branches de la suite

- El venv operativo del branch `codex-analytics-zoneinfo-dashboard` es `.venv-test`.
- No usar `.venv` ni Python global para validar, iniciar servidor fuente o preparar Nuitka.
- El venv no forma parte del versionado Git; se versionan `requirements.txt`, documentación y scripts.
- Antes de mergear a la línea principal: reconstruir/verificar `.venv-test`, correr pytest completo, build frontend y recién después iniciar el flujo pre-build Nuitka.

## Historial

| Suite | Commit/tag | Estado | Alcance destacado | Migraciones y compatibilidad |
| --- | --- | --- | --- | --- |
| `v0.9.0-beta.10` | sin tag | QA | Addon **Sundial ERTeckno** pasa a `both`: driver de red propio (`services/addons/sundial/driver.py` sobre `protocol.SundialClient`, módulo Tibbo TCP 3000) con el mismo flujo de terminal que ZKTeco: probar conexión (hora, desvío, pendientes), poner en hora, bajar registros y agenda. Se habilita por `SRTIME_ENABLED_ADDONS`. Contrato de drivers: hook opcional `acknowledge_attendance_logs()` llamado después del commit de la ingesta (Sundial confirma el puntero `I3` recién ahí; si falla antes, la próxima descarga repite y se detectan duplicados). Manifests declaran `connection_details` (qué informa `test_connection` y con qué etiqueta); Web y Desktop muestran esa lista en vez de MAC/SN fijos. Capability `attendance_pointer` + `POST /api/terminals/{id}/pointer`: "Volver a bajar registros desde…" en la tarjeta Web y la ficha Desktop (Sundial `I2`). Ficha Desktop muestra usuarios/puntero sólo si el driver los declara. El scheduler de terminales no corre antes del asistente de primer uso (antes llenaba el log con ERROR). `SundialError` hereda de `RuntimeError` (el router responde 400, no 500). | Sin migraciones nuevas; head c9d0e1f2a304. Rearmar Web (Nuitka) y Desktop. |
| `v0.9.0-beta.9` | tag anotado | QA | Paridad Web/Desktop: pestañas Web **Feriados** (alta, edición con cambio de fecha, baja; mismos roles que la API) y **Reportes** (mensual con exportación XLSX/PDF; columnas desde `services/reports.MONTHLY_REPORT_COLUMNS`, fuente única para Desktop, exportación y Web); `ui.ini` también en Web vía `GET /api/ui/settings` (mismo archivo y reglas que Desktop). API: validación del nombre de feriado y del año del reporte, `Content-Disposition` expuesto por CORS. Addon Sundial sólo-parser con `protocol.py` nativo (driver directo pendiente). Base del deploy Linux headless. | Sin migraciones nuevas; head c9d0e1f2a304. Rearmar Web (Nuitka) y Desktop. |
| `v0.9.0-beta.8` | sin tag | Reemplazada por beta.9 | Desktop: `ui.ini` junto al ejecutable oculta pestañas opcionales del menú principal (Dashboard, Terminales, Ausencias, Feriados, Reportes, Usuarios Autorizados) sin quitar funciones; Importar, Empleados, Turnos Horarios, Movimientos y Movimientos Procesados son fijas. Instalador `SRTime_Win` con modo Actualizar/Desinstalar y backup de `attendance.db` en `backups\` antes de actualizar. Incluye lo pendiente de beta.7. | Sin migraciones nuevas; head c9d0e1f2a304. Web sin cambios funcionales (sólo número de versión). |
| `v0.9.0-beta.7` | sin tag (QA no cerrado) | Reemplazada por beta.8 | Primer uso unificado Web/Desktop (`services/setup_service.py`), claves por instalación y datos junto al ejecutable en Desktop, FastAPI fuera de `services/`, refresco de pestañas Desktop tras importar, next 16.4.3 y axios 1.20.0. Instaladores `SRTime_Win` y `SRTime_Web` (este último con PostgreSQL 18.6 incluido). | Sin migraciones nuevas; head c9d0e1f2a304. |
| `v0.9.0-beta.6` | tag anotado | Operativa beta | Dashboard Next.js visual e interactivo con datos reales. QA aprobado el 2026-09-17. | Sin migraciones nuevas; head c9d0e1f2a304. Export estático local, sin nuevos instaladores. |
| `v0.9.0-beta.5` | `c00b440` | Operativa beta anterior | Integración de analytics, grupos y validación de terminales. | Incluye c9d0e1f2a304; consultar contrato de migración. |
| `v0.9.0-beta.4` | `efaa945` | Operativa beta | Ingesta ZKTeco USB `att.dat`, perfiles de terminal y gestión de addons. | Compatible con las migraciones de terminales y privilegios ya declaradas. Verificar backup antes de actualizar datos existentes. |
| `v0.9.0-beta.3` | tag histórico | Operativa beta anterior | Evolución previa de la suite. | Consultar historial Git antes de actualizar una instalación desde esta versión. |
| `v0.9.0-beta.1` | tag histórico | Operativa beta anterior | Primera línea beta registrada. | No usar como base de una instalación nueva sin ruta de actualización. |

## Builds de QA posteriores al tag vigente

Los siguientes artefactos se generan para QA local y no sustituyen el tag de release hasta completar el proceso de publicación:

| Artefacto | Plataforma | Situación |
| --- | --- | --- |
| `SRTime_Web-Setup.exe` | Windows, Web/FastAPI/PostgreSQL | Build de QA `0.9.0-beta.7`: detecta PostgreSQL (14+) o instala PostgreSQL 18.6 incluido; repara o actualiza instalaciones existentes. |
| `SRTime_Win-Setup.exe` | Windows, PySide6/SQLite por defecto | Build de QA `0.9.0-beta.7` `onedir`, Sundial y ZKTeco; claves generadas por instalación. QA de instalación aprobado el 2026-10-26. |

Antes de convertir cualquiera de estos builds en una entrega se debe: confirmar pruebas de QA, asociarlo a un commit limpio, actualizar este registro, crear el tag de suite y guardar su SHA-256.

## Registro obligatorio por entrega

Para cada nueva versión se agrega una fila con:

| Campo | Contenido requerido |
| --- | --- |
| Versión de suite | Tag SemVer oficial. |
| Commit | SHA completo del commit etiquetado. |
| Estado | Desarrollo, QA, beta o release. |
| Plataformas verificadas | Web/PostgreSQL, Desktop/SQLite y las que correspondan. |
| Addons | Addons incluidos y configuración por defecto. |
| Base de datos | Revisiones/migraciones aplicables y compatibilidad. |
| Artefactos | Nombre, ruta de distribución y SHA-256. |
| QA | Fecha, responsable, pruebas ejecutadas y resultado. |
| Notas de actualización | Backup, pasos especiales y reversión. |
| Variantes de cliente | Identificadores de extensión compatibles, si existen. |

La política completa se encuentra en [POLITICA_VERSIONADO_SUITE_Y_VARIANTES_CLIENTE.md](POLITICA_VERSIONADO_SUITE_Y_VARIANTES_CLIENTE.md).
