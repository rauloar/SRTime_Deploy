# SRTime — Hoja de pase del branch a Main

**Fecha:** 2026-09-03  
**Branch:** `codex-analytics-zoneinfo-dashboard`  
**Base funcional previa:** `v0.9.0-beta.4` (`efaa945`)  
**Estado:** branch en validación QA. No pasar a `main` hasta cerrar la checklist final.

## 1. Objetivo del branch

Este branch concentra mejoras funcionales y técnicas posteriores al build Web
Nuitka `v0.9.0-beta.4`, manteniendo el criterio de suite única:

- Web/FastAPI/PostgreSQL como prioridad operativa.
- PySide6/SQLite alineado cuando comparte contrato funcional.
- Sin tablas redundantes para datos derivados.
- Sin hardcoding de drivers, rutas, IPs, puertos ni credenciales.
- Sin build Nuitka nuevo hasta aprobación QA desde código fuente.

## 2. Cambios implementados en el branch

### 2.1 Timezone en el core

Se agregó `attendance/core/timezone.py` para centralizar el reloj de negocio.

- `TIMEZONE` se configura por `.env`.
- Default: `America/Argentina/Buenos_Aires`.
- El sistema sigue guardando movimientos como fecha/hora local, sin cambiar el
  contrato de almacenamiento.
- `zoneinfo` se usa para comparaciones, fechas actuales, validación de futuros y
  cálculos donde el día operativo importa.

### 2.2 Dashboard analítico separado del engine

Se agregó un módulo de analytics de solo lectura:

- `attendance/services/analytics.py`
- `attendance/api/routers/analytics.py`
- `attendance/web/app/components/DashboardTab.tsx`

El dashboard lee `AttendanceLog`, `ProcessedAttendance`, empleados, grupos y
terminales. No persiste métricas derivadas y refleja cambios de RR.HH. en la
siguiente lectura.

Métricas incorporadas:

- empleados activos;
- terminales activas;
- movimientos procesados;
- movimientos pendientes;
- registros que requieren atención;
- horas totales;
- horas de semana actual;
- horas de mes actual;
- tardanzas;
- horas extra;
- estados por período;
- horas por semana;
- horas por mes;
- horas por grupo;
- registros sin grupo.

Refactor 2026-09-04:

- El Dashboard se convirtió en una consola operativa para RR. HH. y supervisores.
- Se mantienen separados Attendance y Analytics: Analytics sólo lee
  `processed_attendance`, `attendance_log`, empleados, grupos, turnos y
  terminales; no modifica registros, no crea métricas persistentes y no participa
  en la ingesta ni en el procesamiento.
- Filtros globales incorporados:
  - período/últimos 7, 30 o 90 días;
  - grupo;
  - turno;
  - terminal, aplicado donde el dato existe;
  - estado;
  - empleado o legajo.
- Sucursal y sector quedan expuestos como capacidad no disponible porque no
  existen campos en el esquema actual; no se inventaron columnas ni hardcoding.
- Nuevas secciones:
  - resumen operativo con cantidad, porcentaje, denominador y período;
  - requiere acción;
  - estado por grupo;
  - evolución histórica por porcentajes;
  - mapa de calor de novedades;
  - actividad reciente;
  - calidad de datos;
  - salud de terminales.
- Endpoints específicos agregados:
  - `GET /api/analytics/overview`;
  - `GET /api/analytics/action-items`;
  - `GET /api/analytics/status-by-group`;
  - `GET /api/analytics/trends`;
  - `GET /api/analytics/recent-activity`;
  - `GET /api/analytics/data-quality`;
  - `GET /api/analytics/device-health`.
- El endpoint existente `GET /api/analytics/dashboard` se conserva para no romper
  la UI ni consumidores existentes.

### 2.3 Grupos de empleados

Se incorporó gestión de grupos para evitar asignación manual empleado por
empleado.

Archivos principales:

- `attendance/models/employee_group.py`
- `attendance/services/employee_groups.py`
- `attendance/api/routers/employee_groups.py`
- `attendance/web/app/components/UsersTab.tsx`
- `alembic/versions/c9d0e1f2a304_add_employee_groups.py`

Cambios de esquema:

- tabla `employee_group`;
- columna `users.group_id`;
- columna `users.shift_assignment_source`;
- constraint `MANUAL` / `GROUP`.

Criterio funcional:

- El engine no cambia: sigue procesando contra `users.shift_id`.
- El grupo es una herramienta de RR.HH. para aplicar turnos de forma masiva.
- La asignación es idempotente.
- Por defecto preserva turnos manuales.
- Sólo pisa turnos manuales si el operador confirma la acción.

### 2.4 Ausencias materializadas desde el procesamiento

Se corrigió el caso donde empleados activos con turno y sin movimientos no
aparecían como ausentes después de procesar.

Archivos principales:

- `attendance/services/engine.py`
- `attendance/services/absences.py`
- `attendance/api/routers/absences.py`
- `attendance/web/app/components/AbsencesTab.tsx`
- `attendance/ui/tabs/processed_tab.py`
- `attendance/tests/test_absences.py`

Criterio funcional:

- Si se procesan movimientos en un rango y un empleado activo con turno no tiene
  fichadas en una jornada laboral, se crea `AUSENTE` en `processed_attendance`.
- No se crea tabla nueva de ausencias.
- La operación es idempotente y no duplica ausencias existentes.
- Feriados y fines de semana no generan ausencias.

### 2.5 Justificación de ausencias por selección explícita

Se agregó justificación masiva por checkbox en el tab `Ausencias`.

Criterio funcional:

- El rango de fechas filtra candidatos.
- La acción real se aplica sólo a los registros seleccionados.
- Esto evita justificar por error días donde el empleado entró a trabajar aunque
  estuviera dentro de un período de vacaciones, enfermedad, maternidad u otra
  licencia.
- Root justifica directamente.
- Supervisor/Admin generan solicitud pendiente para aprobación root.
- No se crean movimientos ficticios.

Endpoint agregado:

- `POST /api/absences/bulk-justify`
- `GET /api/absences/export`

Corrección QA posterior: si el frontend devuelve `Method Not Allowed` en esta
acción, revisar que el puerto `8000` no esté tomado por una instancia vieja o por
Python global. El endpoint debe aparecer en `/openapi.json`; si no aparece, el
servidor activo no cargó el código del branch. En la prueba corregida, se liberó
el PID viejo y se levantó el server con `.venv-test`, quedando el endpoint visible
y respondiendo `401` sin sesión en lugar de `405`.

Corrección posterior del flujo UI:

- La gestión de justificaciones queda visualmente concentrada en `Ausencias`.
- `Movimientos Procesados` queda como vista de proceso, lectura y exportación;
  no muestra botón de justificación.
- `Ausencias` exporta CSV desde la vista filtrada en pantalla.
- `Ausencias` exporta Excel desde `GET /api/absences/export`, usando el helper
  común de workbooks.
- Las solicitudes pendientes de ausencias o incompletos se aprueban/rechazan
  desde el tab `Ausencias`, derivando al endpoint correcto según
  `previous_status`.

### 2.6 ZKTeco y Sundial: contrato de ingesta consolidado

Se consolidó el criterio de parsing:

- Sundial/TM-MR001 usa `mark_type`:
  - `0` = Entrada
  - `1` = Salida
- ZKTeco usa `punch` para dirección funcional:
  - `0`, `3`, `4` = Entrada
  - `1`, `2`, `5` = Salida
- ZKTeco usa `status` sólo como método de verificación:
  - `0` = Face ID
  - `1` = Huella
  - `2` = Credencial
  - `3` = Contraseña

El archivo USB nativo ZKTeco queda documentado como `att.dat` y se parsea con
su addon, no con el parser TM-MR001.

### 2.7 Privilegio de terminal en empleados

Se agregó `users.terminal_privilege`, independiente de los roles de login de la
aplicación.

Valores:

- `USER = 0`
- `ADMIN = 14`

Uso:

- sincronización ZKTeco hacia terminal;
- import/export CSV de empleados;
- default `USER` para Sundial porque TM-MR001 no trae privilegios de terminal.

### 2.8 Addons habilitados por configuración

La UI ya no debe mostrar drivers no habilitados.

Variable:

```env
SRTIME_ENABLED_ADDONS=sundial,zkteco
```

Estado actual esperado:

- Sundial habilita importación TM-MR001.
- ZKTeco habilita Terminales y archivo `att.dat`.
- Hikvision y ZKTeco Remote Agent quedan ocultos hasta validación explícita.

### 2.9 Terminales: card y acciones extendidas

Se reforzó el flujo de Terminales:

- tabla superior de terminales;
- selección por row;
- card inferior con detalle de la terminal;
- acciones específicas:
  - conectar/probar;
  - descargar registros;
  - desconectar al terminar;
  - actualizar fecha/hora;
  - consultar usuarios;
  - subir usuarios/perfiles.

La terminal ZKTeco probada por QA respondió correctamente fuera del sandbox y
desde SRTime cuando el server fuente quedó levantado con el venv correcto.

### 2.10 Preflight de esquema para instalador Web

Se agregó validación de estructura PostgreSQL antes de actualizar una instalación
Web.

Archivos principales:

- `attendance/core/schema_preflight.py`
- `attendance/tests/test_schema_preflight.py`
- documentación técnica de instalador.

Criterio:

- base vacía: permitida;
- base SRTime completa sin metadata Alembic: reconocible;
- revisión Alembic conocida: migración normal;
- esquema parcial o desconocido: bloquea actualización;
- no se marca `head` si la estructura no cumple.

### 2.11 Paridad PySide6 / SQLite

Se avanzó la alineación Desktop con Web:

- importación por manifests de addons;
- soporte Sundial/TM-MR001;
- soporte ZKTeco/att.dat;
- privilegio terminal en empleados;
- migración SQLite para campos nuevos;
- uso compartido de `services.terminals`.

El build Desktop final queda pendiente hasta aprobación del branch y QA
específica de PySide6.

## 3. Validaciones realizadas en el branch

Validaciones ya ejecutadas durante el trabajo:

- QA funcional desde UI confirmado por QA:
  - Dashboard;
  - Importar TM-MR001;
  - Importar ZKTeco `att.dat`;
  - Terminal ZKTeco real;
  - Movimientos crudos;
  - Movimientos Procesados;
  - Ausencias con checkbox;
  - Grupos de Empleados.
- Datos cotejados por QA.
- `pytest` completo previo de grupos/analytics: `126 passed, 1 skipped`.
- Preflight PostgreSQL sobre `srtime_db_test`: OK en revisión
  `c9d0e1f2a304`.
- Build estático Next.js: OK.
- Tests ZKTeco/Sundial parser: OK.
- Tests de ausencias actualizados: OK.
- Validación técnica final previa a pase:
  - compile Python `attendance/api`, `attendance/core`, `attendance/models`,
    `attendance/services` y `attendance/ui`: OK.
  - `pytest attendance\tests -q`: `142 passed, 1 skipped`.
  - `npm.cmd run lint`: OK.
  - `npm.cmd run build`: OK.
- Última validación puntual:
  - compile Python `attendance/services` y `attendance/api`: OK.
  - `attendance/tests/test_absences.py`: `9 passed`.
  - `npm run build` en `attendance/web`: OK.
- Validación posterior a export CSV/Excel en Ausencias:
  - compile Python `attendance/api` y `attendance/services`: OK.
  - `attendance/tests/test_absences.py`: `9 passed`.
  - `pytest attendance\tests -q` con `DB_ENGINE=sqlite`: `143 passed, 1 skipped`.
  - `npm.cmd run lint`: OK.
  - `npm.cmd run build`: OK.
- Validación posterior a refactor Dashboard/Analytics:
  - compile Python `attendance/api`, `attendance/core`, `attendance/models`,
    `attendance/services` y `attendance/ui`: OK.
  - `attendance/tests/test_timezone_and_analytics.py`: `5 passed`.
  - `pytest attendance\tests -q` con `DB_ENGINE=sqlite`: `146 passed, 1 skipped`.
  - `npm.cmd run lint`: OK.
  - `npm.cmd run build`: OK.
  - `git diff --check` sobre archivos del cambio: OK.
- Server fuente levantado contra `config/.env`: health OK en
  `http://127.0.0.1:8000/api/health`.

## 4. Lista pendiente antes de pasar a Main

### 4.1 QA funcional desde UI

- ✅ Dashboard con datos reales/mock cargados.
- ✅ Importar con Sundial/TM-MR001.
- ✅ Importar con ZKTeco/att.dat.
- ✅ Terminales con ZKTeco real:
  - probar conexión;
  - traer número de serie;
  - descargar logs;
  - consultar usuarios;
  - subir usuarios;
  - actualizar fecha/hora si aplica.
- ✅ Movimientos crudos.
- ✅ Movimientos Procesados.
- ✅ Ausencias:
  - reprocesar ausencias;
  - materialización automática al procesar movimientos;
  - justificar ausencia individual;
  - justificar ausencias seleccionadas por checkbox;
  - solicitar como supervisor/admin;
  - aprobar/rechazar como root.
- ✅ Grupos de Empleados:
  - crear grupo;
  - asignar empleados;
  - aplicar turno sin pisar manuales;
  - aplicar turno pisando manuales sólo con confirmación.

### 4.2 QA de datos

- ✅ Confirmar raw vs procesados con `srtime_db_test`.
- ✅ Confirmar que no se duplican registros al reimportar.
- ✅ Confirmar que el reproceso histórico es idempotente.
- ✅ Confirmar que empleados activos con turno y sin movimientos generan
  `AUSENTE`.
- ✅ Confirmar que vacaciones/enfermedad por selección no justifican días con
  movimientos reales.

### 4.3 QA de seguridad/configuración

- Revisar que no haya credenciales reales en archivos versionados.
- Confirmar que `config/.env` no está trackeado.
- Confirmar que sólo queda `config/.env.example`.
- Revisar `SRTIME_ENABLED_ADDONS`.
- Revisar `CORS_ORIGINS`, host/puerto y reglas LAN sin hardcoding.
- Confirmar que secrets de terminal no se devuelven por API.
- Confirmar RBAC:
  - viewer sólo lectura;
  - supervisor/admin operaciones y solicitudes;
  - root aprobación, reproceso total y acciones críticas.

### 4.4 QA técnico antes del merge

Estado: ✅ ejecutado correctamente.

#### Entorno Python canónico del branch

El entorno Python válido para validar este branch es:

```powershell
C:\Proyectos\SRTime\.venv-test\Scripts\python.exe
```

No usar `.venv`, Python global ni entornos heredados para pytest, arranque manual
del servidor fuente o build Nuitka. Si `.venv-test` no existe o queda
inconsistente, debe reconstruirse desde `requirements.txt` dentro de
`C:\Proyectos\SRTime` y volver a validarse antes de mergear.

Validación esperada:

```powershell
C:\Proyectos\SRTime\.venv-test\Scripts\python.exe -c "import sys, zk; print(sys.executable); print(zk.__file__)"
```

Debe mostrar `C:\Proyectos\SRTime\.venv-test\Scripts\python.exe` y `zk` dentro de
`C:\Proyectos\SRTime\.venv-test\Lib\site-packages`.

El venv no se commitea ni se mergea como carpeta. Lo que se lleva al merge es el
contrato reproducible: `requirements.txt`, scripts/documentación que apuntan al
venv correcto y la validación previa. Después del merge se reconstruye o reutiliza
`.venv-test`, se repiten pytest/build frontend y recién ahí se ejecuta el
pre-build Nuitka.

Ejecutado desde `C:\Proyectos\SRTime`:

```powershell
C:\Proyectos\SRTime\.venv-test\Scripts\python.exe -m compileall -q attendance\api attendance\core attendance\models attendance\services attendance\ui
C:\Proyectos\SRTime\.venv-test\Scripts\python.exe -m pytest attendance\tests -q
```

Resultado:

```text
146 passed, 1 skipped
```

Ejecutado desde `C:\Proyectos\SRTime\attendance\web`:

```powershell
npm.cmd run lint
npm.cmd run build
```

Resultado:

```text
ESLint OK
Next.js static build OK
```

Validar migraciones:

```powershell
alembic heads
alembic current
alembic upgrade head
```

Si se prepara release:

```powershell
git diff --check
git status --short
```

### 4.5 Documentación pendiente de cierre

- Actualizar `docs/REGISTRO_VERSIONES_SUITE.md` con la próxima versión.
- Definir el tag de suite posterior a QA.
- Actualizar manual técnico si cambia el workflow final de ausencias/grupos.
- Actualizar manual de usuario con:
  - Dashboard;
  - Grupos de Empleados;
  - Ausencias por selección;
  - Exportación CSV/Excel de Ausencias;
  - Terminales ZKTeco;
  - importación `att.dat`.
- Próximo paso funcional no incluido todavía en este ajuste:
  - exportación PDF de Ausencias;
  - logo configurable de empresa para reportes/exportaciones.

### 4.6 Build pendiente

QA funcional y validación técnica local están OK. Antes de construir artefactos
finales, cerrar revisión de seguridad/configuración y migraciones.

Orden recomendado:

1. ✅ QA desde código fuente.
2. Revisión de seguridad/configuración.
3. Validación Alembic/head.
4. Commit del branch.
5. Merge controlado a `main` o branch estable acordado.
6. Tag de suite.
7. Build Web Nuitka.
8. Prueba de instalador Web.
9. Build Desktop PyInstaller onedir.
10. Prueba PySide6/SQLite.

## 5. Riesgos a revisar antes del merge

- El branch contiene cambios amplios acumulados; conviene hacer revisión por
  bloques antes de mergear.
- Hay migración nueva de grupos: validar PostgreSQL y SQLite.
- El instalador Web debe comprobar estructura de BD antes de actualizar una
  instalación existente.
- La paridad PySide6 existe en código, pero requiere QA visual/funcional antes
  de considerarla release cerrada.
- Los addons no probados con hardware real deben permanecer ocultos por `.env`.
- No taggear una versión nueva hasta tener QA OK, porque el tag representa la
  suite completa.

## 6. Criterio de aceptación para pasar a Main

El branch puede pasar a `main` cuando se cumpla todo:

- ✅ QA confirma flujo Web completo.
- PostgreSQL `srtime_db_test` queda alineada con Alembic `head`.
- ✅ Tests Python completos pasan.
- ✅ Build Next.js pasa.
- No hay `.env`, bases, dumps, logs, builds ni deploys trackeados.
- Documentación de usuario/técnica actualizada.
- Se define versión/tag de suite.
- Se hace commit limpio con mensaje de release o feature consolidada.
