# Deploy Linux por USB/LAN — archivos locales y contrato de repo

Fecha: 2026-09-16
Rama operativa: `deploy/pseudoprod-pro`

## Objetivo

Permitir una instalación o build limpio de SRTime Web en Linux transportando sólo los archivos de deploy que no viajan por Git, sin copiar residuos, credenciales, bases locales ni artefactos viejos.

## Regla de oro

El código fuente versionado vive en el repo online. La carpeta `deploy/` es local, está en `.gitignore` y no se sube.

Excepción importante: los archivos de contrato reproducible sí pertenecen al repo cuando no contienen secretos:

- `requirements.txt`
- `config/.env.example`

No se suben:

- `config/.env`
- `.env` reales
- credenciales
- bases de datos
- logs
- venvs
- builds
- instaladores
- `deploy/`

## Kit local preparado

El kit mínimo local quedó en:

```text
C:\Proyectos\SRTime\deploy\flash\srtime-linux-flash-2026-09-16
```

Contenido:

```text
deploy/
├── linux/
│   ├── build.sh
│   ├── install.sh
│   ├── setup.sh
│   ├── start.sh
│   ├── stop.sh
│   ├── srtime-api.service
│   ├── srtime-apache.conf
│   └── srtime-nginx.conf
└── web/
    └── run_api.py
```

El kit fue ajustado para el contrato actual:

- usa `requirements.txt`;
- usa `config/.env.example`;
- incluye paquetes Nuitka para FastAPI, PostgreSQL, Alembic, ORJSON, analytics, Sundial, ZKTeco y `pyzk`.

## Flujo recomendado

### 1. En Linux: obtener código fuente

```bash
git clone --branch deploy/pseudoprod-pro https://github.com/rauloar/SRTime_Deploy.git SRTime
cd SRTime
```

### 2. Copiar kit local sobre la raíz del repo

```bash
cp -a /ruta/usb/srtime-linux-flash-2026-09-16/deploy ./deploy
```

### 3. Crear entorno de build

```bash
python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install nuitka
```

### 4. Compilar

```bash
VERSION=v0.9.0-beta.5-local SOURCE_REVISION="$(git rev-parse --short HEAD)" PYTHON="$PWD/.venv-build/bin/python" bash deploy/linux/build.sh
```

### 5. Instalar

```bash
sudo bash deploy/linux/install.sh --tarball deploy/dist/srtime-web-<version>-linux-x86_64.tar.gz
```

## Limpieza local realizada

Se eliminó residuo regenerable:

- `C:\Proyectos\SRTime\deploy\web\build`
- `C:\Proyectos\SRTime\deploy\web\nuitka-build.log`

Se conservaron por decisión operativa hasta confirmación de QA:

- `C:\Proyectos\SRTime\deploy\web\dist`
- `C:\Proyectos\SRTime\deploy\web\installer`
- `C:\Proyectos\SRTime\deploy\windows\dist`

## Pendiente de limpieza manual confirmada

Antes de entregar o comprimir un paquete Windows histórico, revisar o eliminar:

- `C:\Proyectos\SRTime\deploy\windows\dist\SRTime\.env`
- `C:\Proyectos\SRTime\deploy\windows\dist\SRTime\attendance.db`

Estos archivos están ignorados por Git, pero no deben viajar en ningún paquete de cliente.
