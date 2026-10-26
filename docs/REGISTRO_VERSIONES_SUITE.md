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
| `v0.9.0-beta.7` | sin tag (en QA) | QA | Primer uso unificado Web/Desktop (`services/setup_service.py`), claves por instalación y datos junto al ejecutable en Desktop, FastAPI fuera de `services/`, refresco de pestañas Desktop tras importar, next 16.4.3 y axios 1.20.0. Instaladores `SRTime_Win` y `SRTime_Web` (este último con PostgreSQL 18.6 incluido). | Sin migraciones nuevas; head c9d0e1f2a304. |
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
