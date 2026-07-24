# Especificaciones de despliegue de SRTime

> Referencia para la versión **0.9.0-beta.1**. Estas capacidades son una base
> operativa; deben validarse con una prueba de carga representativa antes de
> promover una instalación a producción definitiva.

## Principio de separación

SRTime tiene tres usos que no deben confundirse:

1. **Desarrollo/QA:** se modifica y prueba código; puede usar herramientas de
   desarrollo y datos mock.
2. **Build:** compila el artefacto Linux con Nuitka y el frontend estático.
3. **Runtime:** ejecuta únicamente el binario compilado, PostgreSQL y el proxy
   web. No requiere Git, Node.js, venv ni código fuente Python.

El binario Nuitka es nativo de la plataforma: un artefacto Linux se construye
en Linux x86_64; un `.exe` Windows se construye en Windows. No se usa un build
Windows para ejecutar en Debian.

## Perfiles de hardware

| Perfil | CPU | RAM | Disco SSD | Uso previsto |
|---|---:|---:|---:|---|
| QA local Windows | 4 núcleos | 8 GB | 30 GB libres | Wizard, pruebas web, importación mock y desarrollo local. |
| Build Linux mínimo | 4 vCPU | 12 GB | 60 GB | Compilación Nuitka ocasional y generación del artefacto. |
| Build Linux recomendado | 4–8 vCPU | 16 GB | 80 GB | Builds frecuentes, frontend y tests durante la compilación. |
| Runtime pequeño | 2 vCPU | 4–8 GB | 40 GB | Hasta ~50 empleados, pocas terminales e importaciones manuales. |
| Runtime estándar | 4 vCPU | 8–16 GB | 80 GB | Operación cotidiana, varios usuarios y reprocesos periódicos. |
| Runtime de carga alta | 8 vCPU | 16–32 GB | 150 GB+ | Varias terminales, alto volumen histórico y reportes concurrentes. |

El espacio de disco debe contemplar PostgreSQL, logs, backups y archivos de
importación. Los backups no deben residir únicamente en el mismo disco de la
aplicación.

## VM pseudo-productiva actual

Para el drill de despliegue en Debian 13 se recomienda:

- **4 vCPU**: el build inicial de Nuitka compila numerosos módulos C en
  paralelo; dos vCPU funcionan pero aumentan notablemente el tiempo.
- **16 GB RAM**: 8 GB permite compilar, pero 16 GB deja margen a PostgreSQL,
  Apache, compilación y cachés del sistema.
- **60 GB SSD mínimo**: el staging, el entorno de build y el artefacto ocupan
  espacio temporal. La instalación final ocupa mucho menos.
- PostgreSQL 17 local, escuchando sólo en `localhost` salvo que se decida una
  arquitectura con base remota.
- Apache 2 como proxy inverso para esta VM, ya que forma parte del entorno
  existente. La API Nuitka escucha sólo en `127.0.0.1:8000`.

Al finalizar un build correcto, el directorio temporal de fuente y venv de
compilación se purga. El runtime queda en `/opt/srtime` con el binario Nuitka,
el frontend estático y su configuración privada.

## Software por perfil

| Componente | QA Windows | Build Linux | Runtime Linux |
|---|---|---|---|
| Git | Sí, para desarrollo | Opcional; el drill usa archivo LAN temporal | No |
| Python | Sí, venv de desarrollo | Sí, Python 3.13, headers y Nuitka | No para ejecutar SRTime |
| Node.js / npm | Sí, para la web | Sí, sólo para `npm ci` y `npm run build` | No |
| Compilador C / `patchelf` | No obligatorio | Sí | No |
| PostgreSQL | Opcional o QA local | Opcional para build | Sí, PostgreSQL 17 recomendado |
| Apache / Nginx | No obligatorio | No | Sí, un único proxy inverso |
| systemd | No | No | Sí, servicio `srtime-api` |

### Dependencias del build Linux

En Debian 13 el build requiere, como mínimo:

```text
build-essential  python3  python3-venv  python3-dev  python3-pip
openssl  patchelf  Node.js  npm
```

Además, el entorno virtual de build instala `attendance/requirements-web.txt`
y Nuitka. Estas dependencias no se copian al runtime final.

### Dependencias del runtime Linux

El runtime utiliza:

```text
PostgreSQL 17
Apache 2 con proxy, proxy_http y headers
OpenSSL y bibliotecas base del sistema compatibles con Debian
binario Nuitka + frontend estático de SRTime
```

La cuenta Unix de servicio es `srtime`; la base usa roles separados:

- `srtime_owner`: propietario del esquema, sin login cotidiano.
- `srtime_app`: conexión diaria de la API con privilegios mínimos.

Las claves se generan durante instalación y se guardan únicamente en el
archivo privado de configuración con permisos restrictivos.

## Red y seguridad

- PostgreSQL: `127.0.0.1:5432`; no publicar el puerto en la LAN por defecto.
- API: `127.0.0.1:8000`; sólo Apache expone HTTP/HTTPS.
- HTTP 80 es válido para un drill interno. Producción requiere HTTPS, certificado
  y `COOKIE_SECURE=true`.
- CORS debe contener sólo el dominio/IP final autorizado.
- Nunca incluir `.env`, backups, archivos biométricos reales, claves privadas o
  el repositorio Git en el artefacto distribuible.

## Ajustes de capacidad

La importación y reproceso dependen principalmente de la cantidad de
marcaciones, empleados, períodos históricos y terminales simultáneas. Antes de
subir de perfil se debe medir:

1. Tiempo de importación de un archivo real representativo.
2. Tiempo de procesamiento pendiente e histórico.
3. Uso de CPU/RAM durante reportes e importación simultánea.
4. Tamaño de PostgreSQL, logs y backups durante 30–90 días.
5. Restauración de un backup en una instancia de prueba.

Para operaciones multiusuario o de mayor carga, evaluar persistir el estado de
trabajos y separar PostgreSQL en un servidor dedicado.
