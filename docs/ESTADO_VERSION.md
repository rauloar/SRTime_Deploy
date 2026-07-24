# Estado de versión de SRTime

## Versión actual: Beta operativa 0.9.0-beta.2

SRTime se clasifica como **Beta**, no como Alfa ni como versión final 1.0.

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

Plan de trabajo pendiente para la paridad de escritorio Windows/SQLite:
`docs/PLAN_ALINEACION_WINDOWS_SQLITE.md`.

## Criterio de cambio de versión

- **Alfa**: cambios frecuentes, sin flujo de usuario estable. SRTime ya superó
  esta etapa.
- **Beta operativa 0.9.0-beta.2**: flujo funcional validado en
  pseudo-producción, sujeto aún a las condiciones de promoción a 1.0. Estado
  actual.
- **1.0.0**: condiciones anteriores cumplidas y aprobadas por QA/operaciones.
