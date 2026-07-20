# SRTime — Manual Técnico de Despliegue

Documento de referencia para construir, distribuir, instalar y operar SRTime en
un servidor Linux. Cubre dos modos de entrega:

1. **Pseudo-producción** (notebook de pruebas): clonar la fuente y compilar en el
   propio Linux.
2. **Entrega a cliente** (sin código fuente): publicar un artefacto compilado por
   GitHub Releases y descargarlo en el target.

---

## 1. Arquitectura

| Componente | Tecnología | Forma de entrega |
|------------|------------|------------------|
| API/Backend | FastAPI + Uvicorn | Binario **Nuitka `--standalone`** (`api/run_api`) |
| Frontend | Next.js (`output: standalone`) | `node web/server.js` |
| Base de datos | PostgreSQL | Servicio del SO |
| Reverse proxy | nginx | Servicio del SO |
| Orquestación | systemd | `srtime-api`, `srtime-web` |

```
                 ┌────────────── nginx :80 ──────────────┐
   Cliente  ───► │  /api/  → 127.0.0.1:8000 (API binaria) │
                 │  /      → 127.0.0.1:3000 (Next.js)      │
                 └────────────────────────────────────────┘
                         │                     │
                  srtime-api.service    srtime-web.service
                         │
                   PostgreSQL :5432
```

**Por qué se compila en Linux:** Nuitka genera un binario **nativo**; no se puede
cross-compilar desde Windows. El build siempre corre sobre el SO destino.

---

## 2. Estructura del artefacto

`srtime-web-linux-<version>.tar.gz` se extrae como:

```
srtime/
├── api/                 # binario Nuitka (run_api + libs) — SIN .py de la app
├── web/                 # Next.js standalone (server.js, .next/, public/)
├── config/
│   ├── .env.example
│   ├── srtime-api.service
│   ├── srtime-web.service
│   └── srtime-nginx.conf
├── install.sh           # instalador OS-aware
└── BUILD_MANIFEST.txt    # versión, git, toolchain, checksums
```

En runtime **no hay código fuente Python**: solo el binario compilado.

---

## 3. Configuración (sin hardcoding)

Toda la configuración vive en **un único `.env`**: `<APP_DIR>/config/.env`
(generado por el instalador, `chmod 600`). El binario lo localiza por la variable
`SRTIME_ENV_FILE` (la setea el systemd unit) y systemd además lo inyecta como
`EnvironmentFile=`.

| Variable | Descripción |
|----------|-------------|
| `DB_ENGINE` | `postgres` en producción |
| `DB_HOST/PORT/USER/PASS/NAME` | conexión PostgreSQL |
| `SECRET_KEY` | clave JWT (`openssl rand -hex 32`) |
| `API_HOST/PORT/WORKERS` | uvicorn (la API los lee del `.env`) |
| `CORS_ORIGINS` | lista JSON de orígenes permitidos |
| `NEXT_PUBLIC_API_URL` | **build-time**; default `/api` (same-origin) |
| `LOG_LEVEL/FORMAT/DIR` | logging |

> `NEXT_PUBLIC_API_URL` se inlinea al compilar el frontend. Con el default `/api`
> (relativo), el frontend llama al mismo host que lo sirve → el artefacto es
> **agnóstico al servidor** y no requiere recompilar por cliente.

---

## 4. Dependencias

| Etapa | Paquetes |
|-------|----------|
| **Build** | toolchain C (`base-devel`/`build-essential`), Python + `requirements-web.txt` + `nuitka`, Node.js + npm |
| **Runtime/instalación** | `postgresql`, `nginx`, `nodejs` (el binario Nuitka ya incluye Python) |

Los `requirements` están separados: `requirements-base.txt` (común),
`requirements-web.txt` (servidor, **sin** PySide6/pywin32/pyinstaller) y
`requirements-desktop.txt` (Windows).

---

## 5. Build del artefacto

En una máquina Linux con el toolchain y un venv con `requirements-web.txt` + nuitka:

```bash
PYTHON=/ruta/venv/bin/python bash deploy/linux/build.sh
# Variables: VERSION, NEXT_PUBLIC_API_URL (default /api)
```

Genera en `deploy/dist/linux/`:
- `srtime-web-linux-<version>.tar.gz` + `.sha256`
- `BUILD_MANIFEST-<version>.txt`
- Registra la compilación en `deploy/build-registry.md` (historial persistente).

---

## 6. Modo A — Pseudo-producción (clonar + compilar + instalar)

Un solo comando en la notebook (clona vía deploy key SSH, compila e instala los
binarios; opcionalmente borra la fuente):

```bash
PURGE_SOURCE=1 SERVER_NAME=192.168.1.44 bash deploy/linux/setup.sh
```

Variables: `REPO_SSH`, `BRANCH`, `STAGING_DIR`, `PURGE_SOURCE`, más todas las de
`install.sh`. Conexión a la notebook por **paramiko** desde Windows (el `ssh`
interactivo cuelga el prompt de password).

---

## 7. Modo B — Entrega a cliente (sin fuente, GitHub Releases)

```bash
# 1) En tu máquina de build (Linux):
bash deploy/linux/build.sh
DIST_REPO=rauloar/SRTime_Dist VERSION=v1.0.0 bash deploy/linux/release.sh

# 2) En el servidor del cliente (solo baja el binario, no clona fuente):
sudo -E GH_TOKEN=<token> DIST_REPO=rauloar/SRTime_Dist VERSION=v1.0.0 \
     SERVER_NAME=mi.dominio.com bash deploy/linux/srtime-fetch.sh
```

`release.sh` sube el tar.gz + checksum + manifest a un Release de un **repo privado
de distribución** (separado del repo de fuente). `srtime-fetch.sh` descarga el
asset con token, **verifica el SHA256** y ejecuta el instalador embebido.

---

## 8. Instalación (install.sh)

OS-aware (detecta `pacman`/`apt`). Pasos: instala dependencias → configura
PostgreSQL (init del cluster en Arch si hace falta) → crea rol+DB con password
aleatorio → extrae binarios en `APP_DIR` → genera `.env` (600) con secretos →
**bootstrap de la DB** (`RUN_DB_BOOTSTRAP=1`: `create_all` + admin seed) →
instala units systemd → configura nginx → `enable --now`.

Variables principales: `APP_USER`, `APP_DIR` (default `/opt/srtime`), `TARBALL`
(requerido), `SERVER_NAME`, `DB_NAME`, `DB_USER`, `DB_PASS`, `ADMIN_PASS`.
**Nada está hardcodeado al equipo**: todo se deriva o se pasa por variable.

### Bootstrap de la base
La API expone un modo one-shot: con `RUN_DB_BOOTSTRAP=1`, el binario crea el
esquema (`create_all`), siembra el admin (`SRTIME_ADMIN_PASSWORD`) y hace
`alembic stamp head` (best-effort) y sale. Para una instalación fresca,
`create_all` deja el esquema en su estado actual — no se aplican migraciones
incrementales en el cliente.

---

## 9. Operación

```bash
systemctl status srtime-api srtime-web nginx
journalctl -u srtime-api -f
curl -fsS http://localhost/api/health        # → 200
```

Actualizar a una versión nueva: instalar el nuevo artefacto sobre `APP_DIR`
(reemplaza binarios) y reiniciar los servicios. La DB se conserva.

### Backup
```bash
pg_dump -U srtime srtime_attendance > backup_$(date +%F).sql
```
Respaldar también `<APP_DIR>/config/.env`.

---

## 10. Troubleshooting

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| API no levanta, error SECRET_KEY | `.env` no encontrado | revisar `SRTIME_ENV_FILE` en el unit y permisos 600 |
| `no such table` al primer login | bootstrap no corrió | re-ejecutar `RUN_DB_BOOTSTRAP=1 api/run_api` |
| 502 en `/` | `srtime-web` caído | `journalctl -u srtime-web`; verificar node |
| CORS bloquea el front | `CORS_ORIGINS` no incluye el origen | editar `.env` y reiniciar `srtime-api` |
| nginx no arranca | `nginx -t` falla | revisar `srtime-nginx.conf` renderizado |

---

## 11. Verificación de "sin fuente" en el target

```bash
find <APP_DIR>/api -name '*.py' | grep -v '/_' | head    # no debe listar fuente de la app
```
El objetivo se cumple cuando en runtime solo hay binarios (`api/run_api` + libs).
