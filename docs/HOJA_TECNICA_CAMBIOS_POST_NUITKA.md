# SRTime — Hoja técnica de cambios posteriores al build Nuitka

**Fecha:** 26 de agosto de 2026
**Estado:** build Web Nuitka generado para validación QA.
**Alcance:** versión Web/FastAPI con PostgreSQL como motor operativo y compatibilidad SQLite para Desktop.

## 1. Objetivo de la fase

Esta fase corrige y completa la integración de terminales ZKTeco sin alterar el
pipeline de asistencia existente:

```
Terminal / archivo → addon normalizador → AttendanceLog (raw) → motor de asistencia
```

No se agregó una tabla paralela para terminales, ni se procesa asistencia en forma
automática al descargar registros.

## 2. Cambios funcionales

### 2.1 Addons habilitados por configuración

- La selección de addons se controla por `SRTIME_ENABLED_ADDONS` en `config/.env`.
- En el perfil actual están habilitados solamente `sundial,zkteco`.
- Sundial conserva la importación de archivos `TM-MR001.txt`.
- ZKTeco expone gestión de terminal y descarga de red; su importación USB queda
  deshabilitada en la interfaz para no duplicar el flujo Sundial.
- Hikvision y ZKTeco Remote Agent no se muestran mientras no sean habilitados
  explícitamente por configuración y validados por QA.

### 2.2 Descarga ZKTeco y clasificación de marcaciones

- Se usa `att.punch` para determinar la dirección del movimiento:
  - `0`, `3`, `4` → Entrada.
  - `1`, `2`, `5` → Salida.
- `att.status` se conserva como metadata en `flags`; no determina Entrada/Salida.
- El parser de exportaciones USB usa el mismo criterio y conserva compatibilidad
  con archivos históricos que no incluyen la columna `punch`.
- La descarga continúa ingresando por el importador común y mantiene la
  deduplicación de SRTime.
- El export nativo USB ZKTeco se denomina **`att.dat`** y usa filas tabuladas:
  `ID, fecha ISO, hora, status, punch, ...`. La pestaña Importar permite elegir
  el parser ZKTeco, acepta `.dat` y lo selecciona automáticamente al elegir ese
  archivo. `TM-MR001.txt` continúa asociado a Sundial.

### 2.3 Conectividad de terminales

- El driver usa pyzk sobre TCP, con IP y puerto configurados en la terminal.
- Timeout predeterminado: **3 segundos**.
- Reintentos predeterminados: **3**.
- Ante falla, la interfaz recibe: **“No hay conectividad con la terminal”**.
- El log FastAPI conserva excepción y traceback para diagnóstico; las credenciales
  de conexión no se devuelven a la UI ni a la API pública.

### 2.4 Directorio de empleados y nombres

En una descarga ZKTeco, SRTime lee el directorio de usuarios del reloj usando la
misma conexión que descarga las marcaciones.

| Estado del empleado en SRTime | Resultado durante la descarga |
|---|---|
| No existe | Se crea con identificador, nombre disponible y privilegio de terminal. |
| Existe sin nombre/apellido | Se completa desde el reloj una única vez. |
| Ya posee nombre en SRTime | Se preserva; una descarga normal no lo sobrescribe. |

El campo `name` de ZKTeco no está separado. Si llega como `Apellido, Nombre`,
SRTime lo separa; en cualquier otro formato se conserva completo como nombre,
sin intentar inferencias riesgosas.

El principio operativo es que SRTime pasa a ser la fuente de nombre una vez que
el perfil fue administrado allí. La actualización inversa desde el reloj debe
ser una sincronización explícita y controlada, nunca el efecto colateral de una
descarga automática.

### 2.5 Privilegios de terminal

Se incorporó `users.terminal_privilege`, independiente de los roles de login de
SRTime.

| Valor | Significado |
|---:|---|
| `0` | USER: puede marcar en la terminal. |
| `14` | ADMIN: puede administrar la terminal biométrica. |

- Los roles de aplicación (`viewer`, `supervisor`, `admin`, `root`) no cambian.
- Sundial/TM-MR001 asigna `USER` por defecto, ya que el formato no trae ese dato.
- La ficha de empleados permite editar, exportar e importar el privilegio.
- El CSV admite la columna opcional `Privilegio Terminal`; archivos legacy sin
  ella continúan importándose como `USER`.
- Al sincronizar hacia ZKTeco se actualizan nombre y privilegio, preservando
  `uid`, `user_id`, contraseña, grupo y tarjeta del dispositivo.

### 2.6 Gestión de terminales Web

- Se mantiene la tabla de terminales y la tarjeta de detalle debajo de ella.
- La primera terminal declarada queda seleccionada por defecto.
- Se dispone de prueba de conexión, conexión/desconexión lógica, sincronización
  de hora, descarga de registros y sincronización de perfiles.
- La descarga muestra progreso y cantidad de movimientos a través del flujo de
  progreso existente.

## 3. Cambios de persistencia y migración

### PostgreSQL

Nueva migración Alembic:

```text
b8c1d2e3f401_add_employee_terminal_privilege.py
```

Aplica la columna `users.terminal_privilege`, default `0`, y una restricción que
sólo acepta `0` o `14`.

En una instalación PostgreSQL existente ejecutar:

```powershell
alembic upgrade head
```

### SQLite

La compatibilidad Desktop incorpora `terminal_privilege` en:

- `core/init_db.py` para bases nuevas.
- `migrate_sqlite.py` para bases existentes.

No hay cambio de formato en `AttendanceLog` ni migración destructiva de datos raw.

## 4. Archivos principales involucrados

| Área | Archivos |
|---|---|
| Modelo y migración | `attendance/models/employee.py`, `alembic/versions/b8c1d2e3f401_add_employee_terminal_privilege.py` |
| Terminales compartidas | `attendance/services/terminals.py`, `attendance/services/importer_service.py` |
| Addon ZKTeco | `attendance/services/addons/zkteco/driver.py`, `parser.py`, `__manifest__.py` |
| API | `attendance/api/routers/terminals.py`, `users.py`, `attendance/api/schemas.py` |
| Web | `attendance/web/app/components/TerminalsTab.tsx`, `UsersTab.tsx`, `ImportTab.tsx` |
| SQLite | `attendance/core/init_db.py`, `attendance/migrate_sqlite.py` |

## 5. Configuración requerida

La configuración local permanece fuera de Git en `config/.env`; el repositorio
conserva `config/.env.example` sin secretos.

Variables relevantes:

```dotenv
SRTIME_ENABLED_ADDONS=sundial,zkteco
DB_ENGINE=postgres
DB_HOST=<host>
DB_PORT=5432
DB_NAME=<base>
DB_USER=<usuario>
DB_PASS=<contraseña>
```

La IP, puerto y timeout de cada reloj se almacenan en `DeviceTerminal` y se
ingresan desde la UI. No se deja hardcodeada una IP de dispositivo en el código.

## 6. Validación realizada

| Verificación | Resultado |
|---|---|
| Compilación Python de servicios modificados | Correcta |
| Pruebas ZKTeco específicas | 10 aprobadas |
| Suite Python completa en SQLite aislado | 117 aprobadas, 1 omitida |
| Conexión real pyzk a iFace800/ID | Validada manualmente por QA y desde el driver SRTime fuera del sandbox |
| Servidor fuente actual | Activo en `0.0.0.0:8000` |
| Build Web Nuitka | Generado para `v0.9.0-beta.4` en `deploy/web/dist/SRTime-Web/` |

Las advertencias actuales de la suite son deprecaciones de `TestClient` y del
método legacy `Query.get()`; no son fallos funcionales de esta fase.

## 7. Criterio para siguiente build Nuitka

Antes de distribuir el build, QA debe validar desde código fuente y luego desde
el paquete compilado:

1. Conexión de la terminal declarada.
2. Descarga real de registros y conteo esperado.
3. Visualización correcta de Entrada/Salida en Movimientos.
4. Creación/completado de empleados desde el directorio ZKTeco.
5. Preservación de un nombre ya editado en SRTime tras una nueva descarga.
6. Sincronización SRTime → terminal de nombre y privilegio.
7. Flujo Sundial/TM-MR001 sin regresiones.

Con aprobación QA: revisión pre-build, pruebas, compilación Nuitka Web y creación
del instalador. La versión Desktop PySide6 continuará empaquetándose con
PyInstaller, no con Nuitka.
