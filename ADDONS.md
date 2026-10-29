# ADDONS.md — Sistema de Importación y Drivers de SRTime

> **Estado 2026-07-21:** el refactor descripto en las secciones históricas de este documento
> está implementado. `SundialParser` es el parser predeterminado, no existe
> `_parse_default_line()`, el registry separa drivers de parsers y cachea el descubrimiento,
> y Web/Windows usan `services.terminals` para operar equipos. Las tareas y snippets del final
> se conservan únicamente como registro de diseño; no representan trabajo pendiente.

> **Principio rector:** La selección del addon es una **decisión de configuración del cliente** según
> la tecnología que tiene. Si el cliente tiene ZKTeco → configura terminales ZKTeco. Si tiene
> Hikvision → configura terminales Hikvision. No hay combo runtime de "elige tu parser".
> El sistema resuelve el addon automáticamente desde `DeviceTerminal.driver_name`.

---

## 1. Arquitectura general

El sistema de importación de asistencia tiene **dos rutas** convergentes:

```
RUTA A — Pull de red (driver de dispositivo)
  Terminal biométrica (IP/red)
        │
        ▼
  BiometricDriver.connect()
  BiometricDriver.get_attendance_logs()   → yields tuplas Python
        │
        ▼
  import_from_driver()  →  _ingest_rows()  →  AttendanceLog (BD)


RUTA B — Importación de archivo
  Archivo TXT (USB / TecknoComm / PySundial / exportación manual)
        │
        ▼
  AttendanceParser.parse_line()           → yields tuplas Python
        │
        ▼
  import_att_logs()  →  _ingest_rows()  →  AttendanceLog (BD)
```

Ambas rutas convergen en `_ingest_rows()` en `importer_service.py`,
que aplica deduplicación y escribe a BD. **Ningún driver de red crea archivos intermedios**
(el driver de Sundial, en preparación, también escribirá directo a BD).

### Tupla normalizada (contrato entre addons y núcleo)

```python
(identifier: str, date: date, time: time, mark_type: int, flags: str)
```

| Campo | Descripción |
|-------|-------------|
| `identifier` | ID del empleado, siempre 15 chars con `zfill(15)` |
| `date` | Fecha del movimiento (`datetime.date`) |
| `time` | Hora del movimiento (`datetime.time`) |
| `mark_type` | `0` = Entrada, `1` = Salida |
| `flags` | 7 chars de estado/modo (ej: `"0100100"`, modo biométrico) |

---

## 2. Formato TM-MR001.Txt — El formato nativo del sistema

El formato base de SRTime es el mismo que genera `TecknoComm.exe` de Sundial ERTeckno.
Es un formato fijo de **33 caracteres por línea** (CRLF):

```
000000000010034010324061400100100
│              ││    ││   ││      │
│[0:15]        ││    ││   ││      └─ flags (7 chars)
│identifier    │└────┘└───┘└─ mark_type (1 char: 0=IN, 1=OUT)
│              │fecha    hora
│              │DDMMYY   HHMM
│              └─ [15:21]
```

**Ejemplo real (`TM-MR001.txt` en raíz del proyecto):**
```
000000000010034010324061400100100   → emp:10034, 01/03/2024 06:14, IN
000000000010034010324161610100100   → emp:10034, 01/03/2024 16:16, OUT
```

### Parser nativo compartido

`services/addons/sundial/parser.py::SundialParser.parse_line()` es la única implementación
del formato. `import_att_logs()` delega el formato nativo a esa clase y no mantiene una copia
hardcodeada.

---

## 3. Addons existentes

### Estructura de un addon (patrón tipo Odoo)

```
services/addons/
└── nombre_addon/
    ├── __manifest__.py   ← metadatos, tipo, campos de conexión
    ├── __init__.py       ← expone las clases
    ├── driver.py         ← implementa BiometricDriver (si es driver de red)
    └── parser.py         ← implementa AttendanceParser (si parsea archivos)
```

El registry en `services/addons/__init__.py` escanea todas las subcarpetas
con `__manifest__.py` y los expone vía `get_available_addons()`.

---

### 3.1 Addon: `zkteco`

| Campo | Valor |
|-------|-------|
| **Tipo** | `both` (driver de red + parser de archivo) |
| **Estado** | ✅ Commiteado, producción |
| **Driver class** | `ZKTecoDriver` |
| **Parser class** | `ZKTecoParser` |
| **Protocolo** | `pyzk` (UDP/TCP, puerto 4370 por defecto) |

**`connection_fields`:**

| Campo | Label | Default |
|-------|-------|---------|
| `ip` | Dirección IP | Configuración obligatoria |
| `port` | Puerto | `4370` |
| `timeout` | Timeout de conexión | `5` segundos |

**Flujo de red (Pull):**
```
ZKTecoDriver.connect()     → pyzk ZK(ip, port, timeout=5).connect()
                           → conn.disable_device()
ZKTecoDriver.get_attendance_logs()
                           → conn.get_attendance()
                           → mark_type desde att.punch, flags desde att.status
                           → yield (identifier.zfill(15), date, time, mark_type, flags)
ZKTecoDriver.disconnect()  → conn.enable_device() + conn.disconnect()
```
**No crea archivos.** Escribe directo a BD via `_ingest_rows()`.

La prueba de conectividad hace 3 intentos de 5 segundos. Si la terminal no
responde, la API devuelve el mensaje funcional "No hay conectividad con la
terminal" y el log conserva el traceback técnico completo.

**Importante:** en pyzk, `punch` representa la dirección funcional de la marcación
para SRTime (`0/3/4 = Entrada`, `1/2/5 = Salida`). `status` no debe usarse para
Entrada/Salida; se conserva como metadata compacta en `flags`.

Para ZKTeco, el par que pyzk imprime como `(status, punch)` se interpreta así:

| Campo | Valor | Significado |
|-------|------:|-------------|
| `status` | `0` | Face ID |
| `status` | `1` | Huella |
| `status` | `2` | Credencial |
| `status` | `3` | Contraseña |
| `punch` | `0` | Entrada |
| `punch` | `1` | Salida |
| `punch` | `2` | Salida intermedia |
| `punch` | `3` | Entrada intermedia |
| `punch` | `4` | Entrada extra |
| `punch` | `5` | Salida extra |

**Flujo de archivo (USB export):**
```
ZKTecoParser.parse_line(line)
  parts = line.strip().split()
  identifier = parts[0].zfill(15)
  datetime.strptime(f"{parts[1]} {parts[2]}", "%Y-%m-%d %H:%M:%S")
  status = int(parts[3])     → metadata en flags
  punch = int(parts[4])      → dirección de marcación si existe
  mark_type desde punch      → fallback legacy a parts[3] si falta parts[4]
```

Formato ZKTeco USB (distinto al TM-MR001):
```
1           2025-03-15 08:30:00 1   0   1   0
[user_id]   [fecha]    [hora]   [status] [punch] ...
```

El nombre nativo de exportación por USB es **`att.dat`**. La interfaz de
Importar permite seleccionar el formato ZKTeco y acepta `.dat`; al elegir
`att.dat` selecciona ese parser automáticamente. El formato Sundial
`TM-MR001.txt` sigue usando exclusivamente su parser `.txt`.

**Sincronización de usuarios ZKTeco:** SRTime puede sincronizar nombre y privilegio
terminal (`USER=0`, `ADMIN=14`) desde la ficha de Empleados hacia la terminal,
preservando siempre `uid` y `user_id`. Este privilegio pertenece al reloj biométrico
y no se mezcla con roles de login de la aplicación.

Durante una descarga de registros, SRTime consulta el directorio de la terminal en
la misma conexión: crea empleados que no existen y completa perfiles que quedaron
vacíos por una ingesta raw anterior. Un nombre que ya fue cargado en SRTime no se
sobrescribe automáticamente; SRTime pasa a ser su fuente operativa hasta una
sincronización explícita administrada.

---

### 3.2 Addon: `sundial`

| Campo | Valor |
|-------|-------|
| **Tipo** | `parser` (importación de archivo); driver de red pendiente |
| **Estado** | ✅ Parser en producción · 🚧 driver en preparación |
| **Parser class** | `SundialParser` |
| **Protocolo de red** | `protocol.py`: TCP directo al módulo Tibbo del reloj (sin TecknoComm.exe) |

**Archivos del addon:**

| Archivo | Rol |
|---|---|
| `parser.py` | `SundialParser`: formato TM-MR001.Txt. Lo usa el importador como formato base. |
| `protocol.py` | Protocolo del reloj (tramas, checksum, estado, hora, descarga, puntero). Sin dependencias externas. Tests: `tests/test_sundial_protocol.py`. |
| `__manifest__.py` | Sólo parser; sin `driver_class` ni `connection_fields` hasta implementar el driver. |

**Driver anterior eliminado (2026-10-27):** `SundialDriver` ejecutaba `TecknoComm.exe` por
`subprocess` y leía el `TM-MR001.Txt` resultante. Nunca estuvo en uso ni fue funcional y
dependía de TecknoComm instalado. Se reemplaza por comunicación directa.

**Protocolo (resumen, detalle en el docstring de `protocol.py`):**
```
PC → reloj : 'UUU' 7F 7F 01 <dir:3> 02 <cuerpo> 03 <ck>      ck = 0x33 XOR cuerpo
Comandos   : ^0 conectar · I4 estado · I5 leer bloque · I3 confirmar lectura
             I2DDMMYYYY puntero · H0DDMMYYHHMMSS fecha/hora · H2 sin horario de verano
Transporte : TCP al módulo Tibbo (servidor transparente, puerto 3000) → RS-232 del reloj
```
Verificado contra un reloj real de laboratorio (módulo Tibbo, dirección 001) y contra sesiones
grabadas de TecknoComm. Herramienta standalone equivalente: PySundial (fuera del repo).

**Driver pendiente (al estilo `zkteco`):**
- `driver.py` con `SundialDriver(BiometricDriver)` sobre `protocol.SundialClient`.
- `connection_fields`: `ip`, `port` (3000), `address` (`001`), `timeout`.
- `test_connection` → estado (hora del reloj, pendientes) · `sync_time` → `H0` ·
  `get_attendance_log_count` → pendientes del estado · `get_attendance_logs` → `I5`… y
  confirmar `I3` sólo tras ingesta exitosa · puntero como acción propia.
- Manifest: `type: both`, `driver_class`, `ui_features` con `terminal_management` y
  `network_import`. Sin archivo intermedio: las marcas van directo a `_ingest_rows()`.
- Paridad Desktop (PySide6) + Web (FastAPI) y bump de versión de suite.

**Flujo de archivo (vigente):**
Un `TM-MR001.Txt` generado por TecknoComm o por PySundial se importa con `SundialParser`.

**Formato parseado (TM-MR001.Txt):**
```python
identifier = raw[0:15]      # 15 chars numéricos
fecha_raw  = raw[15:21]     # DDMMYY
hora_raw   = raw[21:25]     # HHMM
mark_type  = int(raw[25])   # 0=IN, 1=OUT
flags      = raw[26:33]     # 7 chars
```

SRTime no interpreta las `flags` Sundial como método de verificación ni como
subtipo de movimiento. Para este driver, el único estado funcional del punch es
`mark_type`: `0` Entrada y `1` Salida. Las `flags` se conservan únicamente para
trazabilidad del dato crudo.

---

### 3.3 Addon: `hikvision`

| Campo | Valor |
|-------|-------|
| **Tipo** | `driver` (solo red, sin parser de archivo) |
| **Estado** | ⚠️ **Implementado pero SIN COMMITEAR** (untracked al 2026-07-20) |
| **Driver class** | `HikvisionDriver` |
| **Protocolo** | HTTP REST ISAPI con HTTP Digest Auth (`requests`) |

**`connection_fields`:**

| Campo | Label | Default |
|-------|-------|---------|
| `ip` | Dirección IP | Configuración obligatoria |
| `port` | Puerto HTTP | `80` |
| `username` | Usuario | `admin` |
| `password` | Contraseña | *(vacío)* |

**Flujo de red (Pull ISAPI):**
```
HikvisionDriver.connect()
  → requests.Session() con HTTPDigestAuth(username, password)
  → GET /ISAPI/System/deviceInfo  (verifica conectividad)

HikvisionDriver.get_attendance_logs()
  → POST /ISAPI/AccessControl/AcsEvent/Search (paginado, 30 registros por página)
  → Parsea XML ISAPI namespace http://www.hikvision.com/ver20/XMLSchema
  → yield (employeeNoString.zfill(15), date, time, mark_type=0, verify_mode[:7])

HikvisionDriver.disconnect()
  → session.close()
```

**No crea archivos.** Escribe directo a BD via `_ingest_rows()`.

**⚠️ Problema conocido: `mark_type` siempre 0**

```python
mark_type = 0  # Hikvision ISAPI básico no distingue entrada/salida en AcsEvent
```

Todos los punches llegan como IN. El `_match_punch_pairs()` del engine
cae al fallback alternado `(daily_logs[0], daily_logs[-1])`, que funciona
en turnos simples pero falla en múltiples IN/OUT por día.

**Opciones de solución:**
1. Usar `minor` code del evento para inferir dirección (5/75 = entrada, 5/76 = salida en algunos modelos)
2. Configurar el dispositivo con "Anti-passback" para que registre dirección
3. Aceptar la limitación y documentarla — Hikvision básico no tiene dirección en ISAPI

---

## 4. Núcleo compartido: `importer_service.py`

### `_ingest_rows(rows, session, source_label, progress_signal)`

Núcleo de ingesta. Recibe cualquier iterator de tuplas normalizadas.

**Algoritmo de deduplicación:**
```python
# Pre-carga el último log conocido por identifier (O(N) una sola vez)
last_log: dict[identifier → (date, time)]

# Por cada row:
if (date, time) > last_log[identifier]:
    INSERT AttendanceLog
    last_log[identifier] = (date, time)   # actualiza el watermark
else:
    duplicados += 1
```

**⚠️ Problema de performance: commits en loop**
```python
# Por cada auto-creación de usuario:
session.commit()   # ← commit individual

# Por cada log nuevo:
session.commit()   # ← commit individual
```
Con archivos grandes (12.000+ líneas como el TM-MR001.txt del proyecto)
esto genera miles de commits. Debería ser `session.flush()` por registro
y un solo `session.commit()` al final del lote.

### `import_att_logs(path, session, progress_signal, parser)`

Importa desde archivo TXT. Si `parser=None` usa `_parse_default_line()` (formato TM-MR001).

### `import_from_driver(driver_instance, connection_params, session, progress_signal)`

Importa desde dispositivo de red. Llama `driver.connect()` → `_ingest_rows()` → `driver.disconnect()`.

---

## 5. Modelo `DeviceTerminal`

```python
class DeviceTerminal(Base):
    id            = Column(Integer, primary_key=True)
    name          = Column(String(100))          # "Recepción", "Planta"
    driver_name   = Column(String(100))          # "ZKTeco", "Hikvision (ISAPI)"
    ip            = Column(String(45))           # IPv4/IPv6
    port          = Column(Integer, default=4370)
    password      = Column(String(50))           # Com password (ZKTeco)
    serial_number = Column(String(100))          # se llena en primer test
    is_active     = Column(Boolean, default=True)
    last_sync     = Column(DateTime)
    created_at    = Column(DateTime, default=func.now())
```

**Configuración genérica vigente**

`ip`, `port`, `password` son los campos de ZKTeco. Hikvision necesita `username`.
Sundial no usa IP — usa rutas de archivo. Cualquier addon futuro que no encaje
en este esquema no tiene donde guardar sus credenciales.

`connection_params = Column(JSON, nullable=True)` es la fuente genérica. Los campos
legacy permanecen como fallback; los secretos nuevos se cifran y nunca se exponen por API.

---

## 6. Problema en `deps.py` y `import_tab.py`: params hardcodeados

### API (`deps.py`)
```python
def get_connection_params(terminal) -> dict:
    return {
        "ip": terminal.ip,
        "port": str(terminal.port),
        "password": terminal.password,   # ← solo sirve para ZKTeco
    }
```

### UI Desktop (`import_tab.py`) — duplicado en 3 lugares
```python
params = {"ip": terminal.ip, "port": str(terminal.port), "password": terminal.password}
```

**Hikvision falla** con estos params porque le falta `username`.
**Sundial fallaba** porque necesitaba `tecknocomm_exe`, `output_file`, etc. (driver eliminado 2026-10-27).

---

## 7. Plan de implementación

### Tarea 1 — Commitear Hikvision (urgente, 0 código nuevo)

```bash
git add services/addons/hikvision/
git commit -m "feat: add Hikvision ISAPI driver addon"
```

Riesgo: bajo. El código ya existe y funciona. Solo falta el commit.

---

### Tarea 2 — Eliminar `_parse_default_line()` (refactor, sin cambio funcional)

**Problema:** `_parse_default_line()` en `importer_service.py` duplica `SundialParser.parse_line()`.

**Cambio en `importer_service.py`:**
```python
# ANTES:
def import_att_logs(path, session, progress_signal=None, parser=None):
    def _row_generator():
        with open(path, "r") as f:
            for line in f:
                if parser is not None:
                    yield parser.parse_line(line)
                else:
                    yield _parse_default_line(line)    # ← hardcoded

# DESPUÉS:
def import_att_logs(path, session, progress_signal=None, parser=None):
    from services.addons.sundial.parser import SundialParser
    _parser = parser or SundialParser()               # ← usa el addon

    def _row_generator():
        with open(path, "r", encoding="latin-1") as f:
            for line in f:
                yield _parser.parse_line(line)
```

Backward compatible. Todo código que llama `import_att_logs(path, session)` sin parser
sigue funcionando igual.

---

### Tarea 3 — `connection_params` genérico en `DeviceTerminal`

**`models/terminal.py`:**
```python
from sqlalchemy import JSON

class DeviceTerminal(Base):
    # ... campos existentes se mantienen ...
    connection_params = Column(JSON, nullable=True)
    # Almacena los valores de los connection_fields del manifest
    # Ej Hikvision: {"ip": "192.0.2.20", "port": "80", "username": "<usuario>", "password": "<secreto>"}
    # Ej Sundial:   {"ip": "192.0.2.30", "port": "3000", "address": "001"}  (driver pendiente)
    # Ej ZKTeco:    {"ip": "192.0.2.21", "port": "4370", "password": "<secreto-opcional>"}
```

**Migración Alembic:**
```bash
alembic revision --autogenerate -m "add_connection_params_to_device_terminal"
alembic upgrade head
```

**`api/deps.py` — `get_connection_params()`:**
```python
def get_connection_params(terminal) -> dict:
    # Fuente de verdad: JSON genérico del addon
    if terminal.connection_params:
        return terminal.connection_params
    # Fallback: campos legacy para terminales ZKTeco pre-migración
    return {
        "ip": terminal.ip,
        "port": str(terminal.port),
        "password": terminal.password,
    }
```

**`ui/tabs/import_tab.py`** — reemplazar las 3 copias del dict hardcoded:
```python
# ANTES (3 veces):
params = {"ip": terminal.ip, "port": str(terminal.port), "password": terminal.password}

# DESPUÉS (1 helper):
def _get_terminal_params(terminal) -> dict:
    if terminal.connection_params:
        return terminal.connection_params
    return {"ip": terminal.ip, "port": str(terminal.port), "password": terminal.password}
```

---

### Tarea 4 — Fix `importer_service._ingest_rows()`: batch commits

**Problema:** commit individual por cada log → miles de commits con archivos grandes.

```python
# ANTES:
try:
    session.commit()
    nuevos += 1
except IntegrityError:
    session.rollback()
    duplicados += 1

# DESPUÉS:
BATCH_SIZE = 200

try:
    session.flush()   # valida constraints sin commit
    nuevos += 1
    if nuevos % BATCH_SIZE == 0:
        session.commit()
except IntegrityError:
    session.rollback()
    duplicados += 1

# Al final del loop:
session.commit()   # commit final del lote restante
```

**Impacto:** importar el TM-MR001.txt de 12.795 registros pasa de ~12.800 commits
a ~65 commits. Mejora de performance significativa.

---

### Tarea 5 — Investigar `mark_type` en Hikvision

El driver ISAPI hardcodea `mark_type = 0` para todos los eventos.
Antes de usar Hikvision en producción, confirmar si el modelo del cliente
soporta los minor codes de evento para dirección (IN=75, OUT=76).

```python
# hikvision/driver.py — investigar:
minor_code = _xml_text(event, "minor")   # ← verificar si el dispositivo lo devuelve
if minor_code == "75":
    mark_type = 0   # Entrada
elif minor_code == "76":
    mark_type = 1   # Salida
else:
    mark_type = 0   # fallback
```

---

## 8. Prioridad de ejecución

| # | Tarea | Esfuerzo | Riesgo | Prioridad |
|---|-------|----------|--------|-----------|
| 1 | Commitear Hikvision | Mínimo (git) | Bajo | 🔴 Inmediato |
| 2 | Eliminar `_parse_default_line()` | Bajo (5 líneas) | Bajo | 🟠 Alta |
| 3 | `connection_params` en `DeviceTerminal` | Medio (modelo + migración + 2 archivos) | Medio | 🟠 Alta |
| 4 | Batch commits en `_ingest_rows()` | Bajo (10 líneas) | Bajo | 🟡 Media |
| 5 | Investigar `mark_type` Hikvision | Investigación | Bajo | 🟡 Media |

---

## 9. Reglas para agregar un nuevo addon

1. Crear carpeta `services/addons/nombre_addon/`
2. Crear `__manifest__.py` con `name`, `type`, `description`, `connection_fields`, y nombre de clase
3. Si es **driver de red**: heredar `BiometricDriver`, implementar `connect()`, `get_attendance_logs()`, `disconnect()`
4. Si es **parser de archivo**: heredar `AttendanceParser`, implementar `parse_line()`
5. La tupla que retorna `get_attendance_logs()` o `parse_line()` debe ser `(identifier_15chars, date, time, mark_type_0or1, flags_7chars)`
6. El registry lo detecta automáticamente — no hay que registrar nada en ningún otro archivo
7. Los `connection_params` del cliente se guardan en `DeviceTerminal.connection_params` (JSON)

---

## 10. Historial de sesiones

### Sesión 2026-07-20 — Auditoría del sistema de addons

- Revisión completa de los 3 addons existentes (ZKTeco, Sundial, Hikvision)
- Confirmado: ZKTeco y Hikvision escriben **directo a BD sin archivo intermedio**
- Confirmado: Sundial requiere archivo `TM-MR001.Txt` por limitación de `TecknoComm.exe`
- Identificado: `_parse_default_line()` y `SundialParser` son código duplicado del mismo formato
- Identificado: `connection_params` hardcoded para ZKTeco rompe Hikvision y Sundial
- Identificado: commits individuales en `_ingest_rows()` son ineficientes con archivos grandes
- Identificado: Hikvision `mark_type` siempre 0 → fallback alternado del engine
- Plan de 5 tareas definido con prioridades

### Sesión 2026-08-26 — Paridad PySide6 con ZKTeco y Sundial

- PySide6 descubre extensiones y parsers desde los manifests: acepta
  `TM-MR001.txt` mediante Sundial y `att.dat` mediante ZKTeco.
- La descarga Desktop delega en `services.terminals.pull_logs`; incorpora por
  ello la misma actualización de perfiles de terminal que FastAPI.
- La ficha de Terminales permite consultar usuarios y sincronizar nombre y
  privilegio `USER`/`ADMIN` hacia ZKTeco, preservando `uid` y `user_id`.

### Sesión 2026-10-27 — Sundial: protocolo propio y limpieza del driver TecknoComm

- Decodificado el protocolo del reloj desde `WinSock.Log` de TecknoComm y verificado
  contra reloj real vía Tibbo: `services/addons/sundial/protocol.py` + tests.
- Eliminado `SundialDriver` (ejecutaba `TecknoComm.exe`; nunca usado ni funcional).
  El addon queda como `parser` (TM-MR001.Txt) hasta implementar el driver directo.
- `parser.py` (formato TM-MR001) sin cambios: sigue siendo el formato base del importador.
- Pendiente: driver Sundial al estilo ZKTeco (ver §3.2), paridad Desktop/Web y bump.
