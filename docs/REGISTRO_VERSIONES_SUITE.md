# Registro de versiones de SRTime

Este registro identifica las entregas de la suite completa. Los instaladores Web y Desktop son artefactos de una misma versión de suite; no son líneas de producto versionadas de forma independiente.

## Convenciones de estado

- **En desarrollo**: cambios locales sin aprobación de QA.
- **QA**: build disponible para pruebas; no es una entrega publicada.
- **Operativa beta**: funcionalidad aprobada para pruebas controladas.
- **Release**: tag y artefactos publicados con migración y documentación verificadas.
- **Retirada**: no debe usarse para instalaciones nuevas.

## Historial

| Suite | Commit/tag | Estado | Alcance destacado | Migraciones y compatibilidad |
| --- | --- | --- | --- | --- |
| `v0.9.0-beta.4` | `efaa945` | Operativa beta | Ingesta ZKTeco USB `att.dat`, perfiles de terminal y gestión de addons. | Compatible con las migraciones de terminales y privilegios ya declaradas. Verificar backup antes de actualizar datos existentes. |
| `v0.9.0-beta.3` | tag histórico | Operativa beta anterior | Evolución previa de la suite. | Consultar historial Git antes de actualizar una instalación desde esta versión. |
| `v0.9.0-beta.1` | tag histórico | Operativa beta anterior | Primera línea beta registrada. | No usar como base de una instalación nueva sin ruta de actualización. |

## Builds de QA posteriores al tag vigente

Los siguientes artefactos se generan para QA local y no sustituyen el tag de release hasta completar el proceso de publicación:

| Artefacto | Plataforma | Situación |
| --- | --- | --- |
| `SRTime-Web-Setup.exe` | Windows, Web/FastAPI/PostgreSQL | Build de QA con instalador que detecta instalación, repara o actualiza. |
| `SRTime-Desktop-Setup.exe` | Windows, PySide6/SQLite por defecto | Build de QA `onedir`, con addons Sundial y ZKTeco incluidos. |

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
