# Manual de Soporte Técnico y Desarrollo: Ingesta de Asistencia SRTime

Este manual detalla la arquitectura, base de datos y endpoints relacionados con la ingesta y comunicación con terminales biométricas.

---

## 1. Arquitectura de Ingesta Unificada

El sistema cuenta con un pipeline desacoplado que normaliza cualquier fuente de datos (archivos TXT o conexiones directas) en una sola función central de ingesta llamada `_ingest_rows()`.

```
 [TXT File Upload] ────► [Parsers (Addons)] ──┐
                                             ├──► _ingest_rows() ──► [PostgreSQL]
 [Network Pull]    ────► [Drivers (Addons)] ──┘
```

Cada driver o parser es responsable de generar registros bajo una estructura de tupla estándar en Python:
`Tuple[str, datetime.date, datetime.time, int, str]`
*(identificador, fecha, hora, tipo de marca, banderas)*

---

## 2. Estructura de Tablas SQL

### Tabla: `device_terminal`
Almacena los datos de configuración física de los relojes.
* `id` (PK): Clave primaria.
* `name`: Nombre descriptivo.
* `driver_name`: Nombre del addon correspondiente (ej: `"ZKTeco"`, `"Hikvision (ISAPI)"`).
* `ip`: Dirección IP asignada.
* `port`: Puerto (ZK usa `4370`, Hikvision usa `80` o puerto HTTP alternativo).
* `connection_params`: JSON con los campos declarados por el manifest del addon. Los secretos
  se cifran antes de persistirse y nunca se incluyen en respuestas API.
* `password`: Campo legacy; se migra a `connection_params` al editar la terminal.
* `serial_number`: Código único del equipo (se auto-completa en la primera prueba).
* `is_active`: Estado lógico del equipo.
* `last_sync`: Fecha/hora del último pull exitoso.

### Tabla: `att_logs`
Contiene los registros de fichadas unificados.
* `employee_id` (FK): Asociación al ID del empleado.
* `raw_identifier`: String de 15 caracteres con ceros a la izquierda (ej: `"000000000099999"`).
* `date`: Fecha de la marca.
* `time`: Hora de la marca.
* `mark_type`: Tipo de marca (0 = Entrada, 1 = Salida).
* `flags`: Cadena de metadatos estandarizada (ej: `"0100100"` para coincidir con el USB).
* `source_file`: Nombre del archivo de texto cargado o del driver que realizó la descarga.

---

## 3. Endpoints de la API REST (FastAPI)

Todos los endpoints requieren autenticación. La Web usa una cookie JWT HttpOnly y las
integraciones pueden usar `Authorization: Bearer <TOKEN_JWT>`.

* **Listado de Addons** (`GET /api/import/parsers`): Lista los módulos de importación y de hardware válidos y sus campos de configuración requeridos.
* **Importar Archivo** (`POST /api/import/txt`): Recibe un archivo plano y un parámetro opcional `parser_name`.
* **Prueba de Conexión** (`POST /api/terminals/{id}/test`): Ejecuta el test de red contra la terminal y recupera el número de serie, MAC y firmware.
* **Sincronizar Reloj** (`POST /api/terminals/{id}/sync-time`): Actualiza la hora local del dispositivo con la del servidor central.
* **Descarga Pull Manual** (`POST /api/terminals/{id}/pull`): Realiza la descarga on-demand y actualiza `last_sync` solamente si fue exitosa.

La aplicación productiva es un único servicio FastAPI: sirve `/api/*` y el export estático de
Next.js desde `attendance/web/out` (o `SRTIME_WEB_DIR`). No requiere Node ni un puerto 3000.

---

## 4. Requerimientos de Red (Firewall y Puertos)

Para garantizar la comunicación directa del servidor con los relojes físicos:
1. **Modelos ZKTeco**: Se requiere habilitar el puerto **`4370` UDP** y **`4370` TCP** en la red local o WAN.
2. **Modelos Hikvision**: Se requiere habilitar el puerto HTTP del equipo (por defecto, **`80` TCP**).

En despliegues en la nube, se requiere configurar Port Forwarding en los routers de cada sucursal física o interconectar mediante túneles VPN.

---

## 5. Guía: Agregar un Nuevo Driver de Reloj

El sistema utiliza escaneo dinámico de addons estilo Odoo. Para soportar una nueva marca:
1. Cree un subdirectorio en `services/addons/<nombre_marca>/`.
2. Cree el archivo `__manifest__.py` indicando:
   - `"name"`: Nombre visual
   - `"type"`: `"driver"`
   - `"driver_class"`: Nombre de la clase del driver
   - `"connection_fields"`: Lista de inputs requeridos (IP, puerto, etc.)
3. Implemente la clase heredando de `BiometricDriver` en un módulo de Python expuesto por `__init__.py`:
   - `connect(self, params)`
   - `test_connection(self, params) -> dict`
   - `sync_time(self, params) -> bool`
   - `get_attendance_logs(self) -> Iterator[Tuple[str, date, time, int, str]]`
   - `disconnect(self)`
4. El sistema lo detectará automáticamente al iniciar.
