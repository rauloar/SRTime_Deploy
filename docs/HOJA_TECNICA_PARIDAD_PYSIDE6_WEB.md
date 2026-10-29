# SRTime — Paridad técnica PySide6 / Web

**Fecha:** 26 de agosto de 2026  
**Versión de suite:** `v0.9.0-beta.4`; alineación Desktop pendiente de validación QA.  
**Propósito:** registrar el contrato común de la suite y separar el estado del código fuente del estado de los empaquetados distribuibles.

## 1. Arquitectura común

SRTime es un único producto con dos presentaciones. El tag de la suite cubre
ambas; los empaquetados no reciben una versión funcional independiente:

| Presentación | Interfaz | Motor normal | Motor alternativo | Empaquetador previsto |
|---|---|---|---|---|
| Desktop Windows | PySide6 | SQLite | PostgreSQL | PyInstaller `--onedir` |
| Web | Next.js estático servido por FastAPI | PostgreSQL | SQLite sólo para desarrollo/pruebas | Nuitka para la API Web |

El modelo SQLAlchemy, el motor de asistencia, el importador y los addons son
compartidos bajo `attendance/`. Las interfaces sólo coordinan la presentación.
Los logs raw permanecen en `AttendanceLog`; ni una terminal ni un addon crean
tablas paralelas ni procesan asistencias automáticamente al descargarse.

## 2. Selección manual de motor y drivers

La configuración real de ambas presentaciones se carga desde `config/.env`.
El archivo es local, está en `.gitignore` y el repositorio conserva solamente
`config/.env.example`. Un launcher puede reemplazar la ruta con
`SRTIME_ENV_FILE`.

### Base de datos

```dotenv
# Desktop local
DB_ENGINE=sqlite
SQLITE_DB_PATH=attendance.db

# Web o Desktop conectado a un servidor PostgreSQL
# DB_ENGINE=postgres
# DB_HOST=<host>
# DB_PORT=5432
# DB_NAME=<base>
# DB_USER=<usuario>
# DB_PASS=<contraseña>
```

SQLite usa una base local junto al ejecutable o la ruta absoluta indicada.
PostgreSQL utiliza las mismas variables desde ambas interfaces. En PostgreSQL,
la migración `b8c1d2e3f401_add_employee_terminal_privilege.py` debe estar
aplicada con `alembic upgrade head`; SQLite incorpora ese campo mediante
`core/init_db.py` para bases nuevas y `migrate_sqlite.py` para bases existentes.

### Addons de ingesta

```dotenv
# Una tecnología:
SRTIME_ENABLED_ADDONS=sundial
# o
SRTIME_ENABLED_ADDONS=zkteco

# Ambas tecnologías:
SRTIME_ENABLED_ADDONS=sundial,zkteco
```

Los binarios deben contener los addons que se quieran habilitar. Cambiar el
`.env` sólo activa u oculta un addon que ya fue incluido en el build; no agrega
un driver ausente al ejecutable.

| Addon | Archivo USB | Red | Estado funcional |
|---|---|---|---|
| Sundial ERTeckno | `TM-MR001.txt` (TecknoComm o PySundial) | Pendiente: driver directo vía Tibbo (`protocol.py`) | Activo (archivo) |
| ZKTeco | `att.dat` | pyzk TCP, puerto configurable | Activo |

La IP, el puerto y timeout de una terminal se guardan por terminal en
`DeviceTerminal.connection_params`; no se codifican en el ejecutable ni en el
archivo de ejemplo. Los secretos de conexión se cifran al persistirse.

## 3. Mejoras Desktop/PySide6 incorporadas al código fuente

### Importar

- Lee los formatos desde los manifests de addons, no desde nombres hardcodeados.
- Permite elegir Sundial/TM-MR001 y ZKTeco/`att.dat`; al abrir `.dat` selecciona
  el parser ZKTeco automáticamente.
- Valida que la extensión corresponda al parser elegido antes de importar.
- La descarga desde red usa `services.terminals.pull_logs`, exactamente el
  servicio que usa FastAPI. Incluye progreso, deduplicación y el enriquecimiento
  de perfiles ZKTeco.

### Empleados

- Expone `terminal_privilege`: `USER=0` y `ADMIN=14`.
- El privilegio pertenece a la terminal biométrica; no altera roles de login
  SRTime (`viewer`, `supervisor`, `admin`, `root`).
- El CSV Desktop y Web usa el mismo contrato:

  ```text
  Identificador,Nombre,Apellido,Turno,Privilegio Terminal,Activo
  ```

- Una importación posterior actualiza el empleado existente por identificador;
  los identificadores se normalizan a 15 caracteres.

### Terminales

- La tabla Desktop conserva prueba de conexión y sincronización de hora.
- La ficha inferior de la terminal seleccionada permite listar usuarios del
  reloj y sincronizar perfiles hacia ZKTeco.
- La sincronización actualiza sólo nombre y privilegio; conserva `uid`,
  `user_id`, contraseña, grupo y tarjeta existentes en la terminal.
- Una descarga ZKTeco crea empleados faltantes o completa perfiles vacíos. Si
  SRTime ya posee nombre/apellido, los preserva hasta una sincronización
  explícita administrada.

## 4. Contrato ZKTeco compartido

La dirección se toma de `att.punch`, no de `att.status`:

| `punch` | Movimiento |
|---:|---|
| 0, 3, 4 | Entrada |
| 1, 2, 5 | Salida |

`status` se conserva como metadata dentro de `flags`. La conexión predeterminada
intenta tres veces, con timeout de tres segundos por intento. Ante fallo se
informa falta de conectividad; el detalle técnico queda únicamente en logs.

## 5. Estado de empaquetado Windows

La política técnica para un Desktop con varios drivers es **PyInstaller
`--onedir`**, no `--onefile`. El resultado debe incluir `SRTime.exe`, su carpeta
de runtime y todos los addons habilitables; es más estable con PySide6, pyzk y
manifests dinámicos.

> Estado actual: `deploy/windows/build-pyinstaller-desktop.ps1` sigue siendo un
> perfil histórico `--onefile` que empaqueta sólo Sundial/SQLite. No representa
> todavía el build multi-driver de esta hoja técnica y no debe usarse para
> validar ZKTeco ni PostgreSQL Desktop.

El siguiente build Desktop debe incluir `services.addons.sundial`,
`services.addons.zkteco`, `zk`, sus datos de manifest y un `config/.env.example`
sin secretos. El operador elegirá los addons y SQLite/PostgreSQL desde el `.env`.

## 6. Revisión de documentación Web

La documentación Web cubría correctamente el flujo de terminales, ZKTeco USB,
privilegios y la migración. Se corrigieron estas omisiones de estado:

1. La guía del instalador refería `v0.9.0-beta.3`; corresponde a
   `v0.9.0-beta.4`.
2. La hoja técnica registraba 117 pruebas; el estado actual validado es
   **118 aprobadas, 1 omitida**.
3. La hoja técnica debía indicar que PySide6 ya admite `att.dat` y que su pull
   consume el mismo servicio de perfiles que Web.
4. El template global debe mostrar SQLite como alternativa comentada, para que
   el operador no use el template histórico `attendance/.env.example`.

## 7. Validación antes de empaquetar Desktop

1. Crear SQLite vacía; confirmar creación inicial de administrador.
2. Probar la misma SQLite actualizada desde una versión anterior.
3. Probar PostgreSQL remoto con `DB_ENGINE=postgres`.
4. Importar `TM-MR001.txt` y `att.dat` con cada addon habilitado.
5. Conectar ZKTeco, descargar logs, verificar Entrada/Salida y la preservación
   de nombres gestionados por SRTime.
6. Sincronizar un perfil USER y otro ADMIN sin cambiar UID ni ID de terminal.
7. Ejecutar la suite Python, luego validar el paquete `--onedir` en una PC limpia.
