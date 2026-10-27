# Estado de versión de SRTime

## Gobierno de versiones

SRTime se versiona como una **suite única**: Web/FastAPI/PostgreSQL y Desktop/PySide6/SQLite comparten el tag de la suite, aunque sus builds e instaladores sean distintos. Las personalizaciones de clientes se aíslan como extensiones con compatibilidad declarada; no deben convertirse en forks permanentes del núcleo.

- [Política de versionado de la suite y variantes de cliente](POLITICA_VERSIONADO_SUITE_Y_VARIANTES_CLIENTE.md)
- [Registro de versiones de la suite](REGISTRO_VERSIONES_SUITE.md)
- [Contrato de migración de datos de clientes](PLAN_CONTRATO_MIGRACION_CLIENTES.md)

## Versión actual: Beta operativa 0.9.0-beta.6 (0.9.0-beta.8 en desarrollo)

SRTime se clasifica como **Beta**, no como Alfa ni como versión final 1.0.

## Regla de versionado de suite

Cada tag identifica la **suite SRTime completa**: núcleo compartido, modelos,
migraciones, Web/FastAPI y Desktop/PySide6. Los paquetes Nuitka y PyInstaller
son artefactos de distribución del mismo tag, aunque se validen o generen en
momentos diferentes. No se crean versiones separadas por interfaz.

Las mejoras particulares de un cliente se deben entregar como extensiones
compatibles con un tag base, no como forks persistentes. El plan de migración y
actualización se documenta en `docs/PLAN_CONTRATO_MIGRACION_CLIENTES.md`.

La aplicación ya permite un flujo de uso completo: instalación local con
PostgreSQL, creación del administrador, inicio de sesión, importación
TM-MR001, visualización de marcaciones raw, procesamiento de asistencia,
gestión de usuarios y roles, y exportación.

**Estado operativo validado (2026-07-23):** en pseudo-producción Windows con
PostgreSQL Debian vía TCP se completó la creación limpia de la base, la creación
del administrador, el inicio de sesión, la importación de `TM-MR001.txt` y el
procesamiento de las asistencias. El wizard conserva el nombre propuesto
`srtime_db`, permite cambiarlo explícitamente y deja visible el paso de creación
del administrador después de preparar la base.

## Alcance aprobado para Beta

- Uso interno, QA y pilotos controlados.
- PostgreSQL como base de datos de operación.
- Importaciones manuales, procesamiento pendiente e histórico.
- Monitoreo de progreso para importación y procesamiento en la interfaz web.

## Condiciones antes de 1.0

La promoción a **1.0.0** requiere evidencia aprobada de:

1. Prueba de carga con el volumen real de terminales, empleados y marcaciones.
2. Backup PostgreSQL, restauración comprobada y procedimiento de recuperación.
3. Prueba end-to-end del flujo de instalación, importación, reproceso, roles y
   exportaciones en un entorno equivalente a producción.
4. Revisión de seguridad y operación: contraseñas, permisos del archivo de
   entorno, logs y actualización de dependencias.
5. Decisión de despliegue para trabajos en segundo plano. El monitor de progreso
   actual es local en memoria y está diseñado para la ejecución QA de un solo
   proceso; una instalación multiworker requiere persistencia compartida.

La paridad de código fuente Windows/SQLite ya incorpora formatos de importación,
privilegios de terminal y operaciones ZKTeco. El pendiente es la validación QA
Desktop y el nuevo empaquetado PyInstaller `--onedir` multi-driver, documentado
en `docs/HOJA_TECNICA_PARIDAD_PYSIDE6_WEB.md`.

## Criterio de cambio de versión

- **Alfa**: cambios frecuentes, sin flujo de usuario estable. SRTime ya superó
  esta etapa.
- **Beta operativa 0.9.0-beta.4**: incorpora la integración ZKTeco, privilegios
  de terminal, la importación USB nativa `att.dat` y el build Web Nuitka para
  validación QA. El build Desktop multi-driver queda pendiente de QA fuente.
- **Beta operativa 0.9.0-beta.2**: flujo funcional validado previamente en
  pseudo-producción; fue reemplazada por `0.9.0-beta.4` como referencia actual.
- **1.0.0**: condiciones anteriores cumplidas y aprobadas por QA/operaciones.

## Actualización 2026-10-26 — v0.9.0-beta.7 (QA, sin tag)

Primer uso unificado entre Web y Desktop sobre `services/setup_service.py`.
Desktop: claves por instalación, SQLite y logs junto a `SRTime_Win.exe`, recarga
de pestañas tras importar. FastAPI sale de `services/`. Paquetes renombrados a
`SRTime_Win` y `SRTime_Web`; el instalador Web detecta PostgreSQL o instala
PostgreSQL 18.6 incluido. Sin migraciones nuevas. Pendiente: QA Web y tag.

## Actualización 2026-09-17 — v0.9.0-beta.6

Dashboard Next.js adaptado desde Stitch con datos reales, gráficos y filtros interactivos.
QA visual aprobado por el usuario. Build estático validado; se conserva el despliegue
FastAPI, el venv único .venv-test y la configuración config/.env.
No hay migraciones nuevas ni instaladores Nuitka/PyInstaller generados para este tag.
