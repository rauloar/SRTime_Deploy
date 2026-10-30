# SRTime — Estándar de build y plan multiplataforma

Estado: propuesta de implementación para beta.6 y releases posteriores  
Rama inicial: `deploy/pseudoprod-pro`

## 1. Objetivo

Definir un proceso reproducible para generar, probar y distribuir SRTime en:

- Linux: Debian Stable con soporte LTS, servidor `x86_64` y perfil headless.
- Windows: Windows x64, con API empaquetada y frontend estático.

El build debe producir un artefacto cerrado, sin código fuente Python en el
runtime. La base de datos PostgreSQL, el esquema y el primer administrador se
crean desde el wizard web de SRTime. El instalador no debe crear manualmente
`srtime_db`, tablas ni usuarios de aplicación.

## 2. Plataforma Linux estándar

### 2.1 Build canónico

La compilación oficial Linux se hará en una VM o contenedor limpio de Debian
Stable/LTS:

- arquitectura `x86_64`;
- perfil headless, sin GNOME, KDE ni otro escritorio;
- Python 3.12 obligatorio;
- Node.js y npm según la versión validada por el proyecto;
- toolchain C/C++, `patchelf`, PostgreSQL cliente y utilidades de empaquetado;
- locale UTF-8 y zona horaria definida por el operador.

El perfil headless es suficiente: SRTime expone HTTP y la interfaz se usa desde
un navegador remoto o local. No se instala navegador ni servidor gráfico en el
host de producción.

### 2.2 Artefacto

El pipeline Linux debe:

1. validar Python 3.12 y dependencias con `pip check`;
2. compilar la API con Nuitka `--standalone`;
3. compilar el frontend Next.js como export estático;
4. usar Webpack explícitamente para el build del frontend si Turbopack no está
   disponible en el entorno de compilación;
5. ensamblar API, frontend, configuración de ejemplo y unidad systemd;
6. generar `BUILD_MANIFEST`, checksum SHA-256 y registro de compilación;
7. validar que el tarball no incluya `.env`, secretos, base de datos, logs,
   `node_modules` ni código fuente Python.

Nombre esperado:

```text
srtime-web-linux-<version>.tar.gz
srtime-web-linux-<version>.tar.gz.sha256
```

### 2.3 Runtime Debian

El runtime debe ejecutarse como servicio systemd, con:

- usuario de servicio sin login;
- API en `127.0.0.1:8000`;
- frontend servido por la API o por un reverse proxy;
- PostgreSQL como servicio independiente;
- configuración local en `/opt/srtime/config/.env`, modo `600`;
- logs en `/var/log/srtime/`;
- Apache o nginx sólo si el despliegue requiere proxy, TLS o acceso LAN.

El flujo inicial es:

1. instalar PostgreSQL y arrancarlo;
2. instalar el artefacto SRTime;
3. completar las credenciales PostgreSQL en `.env` o en el wizard;
4. abrir SRTime en el navegador;
5. dejar que `/api/setup/database` cree la base y el esquema;
6. dejar que `/api/setup/admin` cree el administrador;
7. validar login, dashboard, imports y terminales.

El instalador no debe generar credenciales silenciosamente ni decidir valores
de base de datos que el operador no haya confirmado.

## 3. Compatibilidad Linux

Garantía inicial:

- Debian Stable/LTS x86_64.
- Ubuntu LTS x86_64, validado con el mismo tarball cuando la versión de
  `glibc` sea compatible.

Compatibilidad best-effort:

- Arch, CachyOS, Fedora y derivados glibc.

Fuera de alcance inicial:

- Alpine/musl sin un build específico.
- ARM64 sin pipeline y pruebas dedicadas.
- distribuciones con `glibc` más antigua que la usada en el builder.

Para ampliar compatibilidad, el builder debe ser la plataforma glibc más
antigua que se quiera soportar, o debe existir un build por familia.

## 4. Plan de implementación Debian

### Fase D1 — Builder reproducible

- Crear VM/container Debian Stable/LTS headless.
- Fijar Python 3.12 y validar `requirements.txt`.
- Documentar versiones de Python, Nuitka, Node, npm, GCC y `patchelf`.
- Ejecutar `build.sh` con versión y revisión de fuente explícitas.

### Fase D2 — Runtime limpio

- Probar el tarball en otra instalación Debian limpia.
- Instalar PostgreSQL sin crear `srtime_db` manualmente.
- Ejecutar `install.sh` del tarball (asistente en pantallas; `--unattended` para automatizar): deja activo `srtime-web.service`.
- Completar el wizard y comprobar creación de base, esquema y admin.

### Fase D3 — QA

- `systemctl status srtime-web`.
- `curl /api/health`.
- login y logout;
- dashboard y movimientos;
- importación TM-MR001 y ZKTeco;
- grupos, ausencias y movimientos procesados;
- prueba de reinicio del servicio;
- verificación de checksum y ausencia de secretos en el tarball.

### Fase D4 — Publicación

- Registrar versión, revisión, builder y SHA-256.
- Publicar el tarball y checksum en el canal de releases definido.
- Conservar logs de QA, sin credenciales.

## 5. Plan de implementación Windows

### Fase W1 — Builder Windows

- Definir builder Windows x64 limpio.
- Fijar Python 3.12, dependencias, Nuitka y compilador MSVC o toolchain
  soportado por el proyecto.
- Compilar la API con Nuitka en modo standalone.
- Compilar el mismo frontend estático con Node/npm.

### Fase W2 — Runtime Windows

- Crear paquete con ejecutable API, frontend, `.env.example` y scripts de
  servicio.
- Elegir mecanismo de servicio: Windows Service, NSSM o tarea programada,
  según la política de soporte.
- Mantener PostgreSQL como dependencia externa o instalarlo de forma
  explícita; el runtime no debe crear la base fuera del wizard SRTime.
- Definir firewall, puerto local, acceso LAN y carpeta de logs.

### Fase W3 — QA Windows

- Arranque limpio del servicio.
- `/api/health` y carga del frontend.
- wizard PostgreSQL, creación de base/esquema y admin.
- imports y terminales.
- actualización conservando `.env` y datos.
- desinstalación sin borrar backups ni la base salvo autorización explícita.

### Fase W4 — Publicación Windows

- Generar manifiesto y SHA-256.
- Firmar binarios si el proceso de distribución lo requiere.
- Publicar instalador/zip y guía de rollback.

## 6. Criterios de aceptación

Un release no se considera listo si falta cualquiera de estos puntos:

- build reproducible con Python 3.12;
- tarball o paquete Windows verificable;
- API y frontend funcionales;
- PostgreSQL arrancado y accesible;
- creación de base y esquema desde el wizard;
- creación del administrador desde la interfaz;
- checksum y manifiesto;
- ningún secreto dentro del repositorio o artefacto publicado.

## 7. Orden recomendado

1. Cerrar y validar el build Nuitka Linux.
2. Crear el builder Debian Stable/LTS headless.
3. Validar instalación y wizard en Debian limpio.
4. Validar el mismo artefacto en Ubuntu LTS.
5. Automatizar manifest/checksum/QA.
6. Implementar el builder y runtime Windows.
7. Publicar releases multiplataforma.
