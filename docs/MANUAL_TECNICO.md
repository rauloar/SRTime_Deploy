# Manual técnico de SRTime

> Estado de versión: **Beta 0.9.0-beta.1**. Consultar `docs/ESTADO_VERSION.md` antes
> de promover una instalación a producción.

## 1. Arquitectura

SRTime es un sistema de asistencia con dos interfaces: escritorio Windows y web.
La lógica de negocio se comparte en `attendance/services/`. En modo web, FastAPI
sirve la API `/api/*` y el frontend estático generado en `attendance/web/out`;
no hay un servidor Node.js en ejecución.

```text
Terminal / archivo TXT → addons → AttendanceLog → motor de asistencia → reportes
                                PostgreSQL                         Web / Windows
```

La lógica de cálculo transforma marcaciones crudas en asistencia procesada,
con soporte para turnos nocturnos, tardanzas, horas extra, incompletos y
justificaciones.

## 2. Cuentas y permisos

No confundir las cuentas de PostgreSQL con las cuentas de SRTime.

| Cuenta | Finalidad | Dónde se administra |
|---|---|---|
| `postgres` | Administración del servidor PostgreSQL. Sólo instalación/recuperación. | PostgreSQL / pgAdmin |
| `srtime_owner` | Dueño del esquema y migraciones en producción. No debe iniciar sesión. | PostgreSQL |
| `srtime_app` | Cuenta de conexión de la API. Debe tener privilegios mínimos sobre la BD de SRTime. | `.env` protegido |
| `admin` | Primera cuenta de SRTime, rol `root`. | Tabla `auth_user` / interfaz Usuarios Autorizados |

Roles de SRTime:

- `root`: administra cuentas, borrados, reproceso total y aprobaciones.
- `supervisor`: operaciones cotidianas de empleados, turnos, terminales,
  importación y procesamiento.
- `admin`: rol legado equivalente a `supervisor`.
- `viewer`: lectura y exportación.

Las contraseñas de SRTime se almacenan hasheadas. Las claves PostgreSQL y JWT
nunca se versionan ni se documentan en texto plano.

## 3. Instalación local QA

Requisitos previos: PostgreSQL, Python y Node.js LTS instalados.

1. Ejecutar `Iniciar-SRTime-QA.cmd` una vez. Crea `.venv`, instala dependencias
   y genera el frontend.
2. Abrir `http://127.0.0.1:8000/`.
3. Completar el wizard en dos pasos: crear/conectar la base con PostgreSQL y,
   cuando se habilite, crear la cuenta inicial `admin`.
4. Para reinicios posteriores ejecutar:

   ```powershell
   .\deploy\start-local-qa-server.ps1
   ```

La configuración local se guarda en `attendance/.env.qa`, ignorado por Git.
La plantilla segura es `attendance/.env.qa.example`.

## 4. Flujo recomendado de PostgreSQL

En QA, el wizard guarda la conexión PostgreSQL indicada en `.env.qa` y separa
la creación de la base de la creación del primer usuario de SRTime. Para
producción se recomienda:

1. Usar una credencial administrativa temporal sólo durante la instalación.
2. Crear la base `srtime_attendance`.
3. Crear `srtime_owner` como dueño de base/esquema y sin uso cotidiano.
4. Crear `srtime_app` con `LOGIN`, contraseña propia y permisos sólo sobre
   `srtime_attendance`.
5. Configurar la API con `srtime_app`; nunca con `postgres`. El primer
   bootstrap otorga `CREATE` en el esquema a esa cuenta para que SRTime pueda
   inicializarlo y aplicar sus migraciones; en una operación madura, las
   migraciones pueden ejecutarse separadamente con una cuenta de despliegue.
6. Guardar `.env` con permisos restringidos y hacer copias de seguridad.

La cuenta de aplicación no debe recibir permisos `CREATEDB`, `CREATEROLE` ni
permisos sobre otras bases.

## 5. Base de datos y migraciones

Tablas principales:

- `auth_user`: cuentas de acceso a SRTime.
- `users`: empleados.
- `shifts`: turnos y tolerancias.
- `attendance_log`: marcaciones crudas inmutables.
- `processed_attendance`: cálculo de asistencia.
- `device_terminal`: terminales y parámetros de conexión.
- `holidays`: feriados.

En bases existentes, aplicar migraciones desde la raíz del proyecto:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

En una base nueva, el instalador crea el esquema y registra Alembic en `head`.
No ejecutar `downgrade` en una base con datos sin un backup probado.

## 6. Operación y diagnóstico

- Salud de API: `GET /api/health`.
- Documentación API: `/docs`.
- Logs: configurar `LOG_DIR`, `LOG_FORMAT` y `LOG_LEVEL` en el entorno.
- El frontend debe reconstruirse con `npm run build` después de cambios web.
- Pruebas: `python -m pytest tests -v` desde `attendance/`.

Antes de una actualización: backup PostgreSQL, prueba de restauración, migración
en staging y validación de login, importación y reportes.
