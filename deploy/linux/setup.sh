#!/usr/bin/env bash
# ==============================================================================
# SRTime — Orquestador pseudo-producción local (transferir + compilar + instalar)
# ==============================================================================
# Flujo para una VM de pruebas (simula "cliente nuevo" pero compilando en
# el propio Linux, porque Nuitka NO cross-compila Win→Linux):
#   1. Recibe un archivo fuente temporal transferido por la red local.
#   2. Crea venv + instala requirements-web.txt + nuitka, compila con build.sh.
#   3. Instala SOLO los binarios resultantes con install.sh (sin fuente en runtime).
#   4. (Opcional) borra el staging → el servicio no expone código fuente.
#
# El staging se borra al terminar; el runtime final contiene sólo el binario.
#
# Variables:
#   SOURCE_ARCHIVE archivo .tar.gz temporal con la fuente (REQUERIDO)
#   VERSION      versión que se grabará en el artefacto (REQUERIDO)
#   STAGING_DIR  dir de clonado/compilado   (default: $HOME/srtime-build)
#   PURGE_SOURCE borrar staging al terminar (default: 0)
#   + cualquier variable de install.sh (APP_DIR, SERVER_NAME, DB_NAME, ...)
# ==============================================================================
set -euo pipefail

SOURCE_ARCHIVE="${SOURCE_ARCHIVE:-}"
VERSION="${VERSION:-}"
STAGING_DIR="${STAGING_DIR:-/var/tmp/srtime-build}"
PURGE_SOURCE="${PURGE_SOURCE:-1}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

[ -n "$SOURCE_ARCHIVE" ] || { echo "✗ Falta SOURCE_ARCHIVE=/ruta/srtime-source.tar.gz"; exit 1; }
[ -f "$SOURCE_ARCHIVE" ] || { echo "✗ No existe SOURCE_ARCHIVE: $SOURCE_ARCHIVE"; exit 1; }
[ -n "$VERSION" ] || { echo "✗ Falta VERSION=vX.Y.Z"; exit 1; }

echo "=================================================="
echo "  SRTime — SETUP pseudo-producción"
echo "  Fuente : $SOURCE_ARCHIVE (transferencia local)"
echo "  Staging: $STAGING_DIR"
echo "=================================================="

# ── 1. Dependencias de build (OS-aware) ───────────────────────────────────────
# patchelf es requerido por Nuitka --standalone en Linux. OJO: la versión 0.18.0
# tiene un bug y Nuitka la rechaza; si aparece, se hace downgrade a 0.17.2.
echo "→ [1/4] Instalando toolchain de compilación..."
if command -v pacman >/dev/null 2>&1; then
    BUILD_PACKAGES=(base-devel python python-pip openssl patchelf)
    command -v node >/dev/null 2>&1 || BUILD_PACKAGES+=(nodejs)
    command -v npm >/dev/null 2>&1 || BUILD_PACKAGES+=(npm)
    pacman -Sy --noconfirm --needed "${BUILD_PACKAGES[@]}" >/dev/null
elif command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    BUILD_PACKAGES=(build-essential python3 python3-venv python3-pip openssl patchelf)
    command -v node >/dev/null 2>&1 || BUILD_PACKAGES+=(nodejs)
    command -v npm >/dev/null 2>&1 || BUILD_PACKAGES+=(npm)
    apt-get update -qq
    apt-get install -y -qq "${BUILD_PACKAGES[@]}" >/dev/null
else
    echo "✗ Gestor de paquetes no soportado (pacman/apt)"; exit 1
fi

# Guard: patchelf 0.18.0 es buggy para Nuitka → downgrade a 0.17.2.
if patchelf --version 2>/dev/null | grep -q '0\.18\.0'; then
    echo "→ patchelf 0.18.0 detectado (incompatible con Nuitka) — bajando a 0.17.2..."
    if command -v pacman >/dev/null 2>&1; then
        curl -fsSL -o /tmp/patchelf-0.17.2.pkg.tar.zst \
            "https://archive.archlinux.org/packages/p/patchelf/patchelf-0.17.2-1-x86_64.pkg.tar.zst"
        sudo pacman -U --noconfirm /tmp/patchelf-0.17.2.pkg.tar.zst >/dev/null
    else
        echo "⚠ Instalá manualmente patchelf != 0.18.0 (0.17.2 o >= 0.18.2)."
    fi
fi

# ── 2. Extraer fuente temporal transferida por LAN ────────────────────────────
echo "→ [2/4] Extrayendo fuente temporal..."
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
tar -xzf "$SOURCE_ARCHIVE" -C "$STAGING_DIR" --strip-components=1

# ── 3. Compilar el artefacto ──────────────────────────────────────────────────
echo "→ [3/4] Compilando artefacto (Nuitka + Next.js)..."
python3 -m venv "$STAGING_DIR/.venv-build"
# shellcheck disable=SC1091
source "$STAGING_DIR/.venv-build/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$STAGING_DIR/attendance/requirements-web.txt"
pip install --quiet nuitka
VERSION="$VERSION" SOURCE_REVISION="local-lan-transfer" \
    PYTHON="$STAGING_DIR/.venv-build/bin/python" bash "$STAGING_DIR/deploy/linux/build.sh"
deactivate

TARBALL="$(ls -t "$STAGING_DIR"/deploy/dist/linux/srtime-web-linux-*.tar.gz | head -1)"
[ -f "$TARBALL" ] || { echo "✗ No se generó el tarball"; exit 1; }

# ── 4. Instalar solo binarios (sin fuente en runtime) ─────────────────────────
echo "→ [4/4] Instalando binarios con install.sh..."
sudo -E TARBALL="$TARBALL" bash "$STAGING_DIR/deploy/linux/install.sh"

if [ "$PURGE_SOURCE" = "1" ]; then
    echo "→ Borrando staging (código fuente) por PURGE_SOURCE=1..."
    rm -rf "$STAGING_DIR"
fi

echo "✅ SETUP pseudo-producción completado."
