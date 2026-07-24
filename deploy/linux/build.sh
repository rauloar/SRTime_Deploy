#!/usr/bin/env bash
# ==============================================================================
# SRTime — Pipeline de build Linux (Nuitka API + Next.js static export)
# ==============================================================================
# Produce un artefacto distribuible SIN código fuente Python:
#   deploy/dist/linux/srtime-web-linux-<version>.tar.gz
# y un BUILD_MANIFEST + registro de compilación persistente.
#
# Requiere (en la máquina de build, Linux):
#   - toolchain C (gcc/g++) + Python con requirements-web.txt + nuitka
#   - Node.js + npm
#
# Variables:
#   PYTHON   intérprete Python con deps        (default: python3)
#   VERSION  versión del release                (default: git describe / fecha)
#   NEXT_PUBLIC_API_URL  URL de la API en build (default: /api — same-origin)
# ==============================================================================
set -euo pipefail

PROJ_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$PROJ_DIR/deploy/dist/linux"
BUILD_DIR="$PROJ_DIR/deploy/build/linux"
STAGE="$DIST_DIR/srtime"
PYTHON="${PYTHON:-python3}"
NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL-}"

# El build no depende de Git. VERSION y SOURCE_REVISION son metadatos aportados
# por el pipeline o por el operador que construye una copia local del código.
VERSION="${VERSION:-$(date -u +%Y%m%d%H%M)}"
SOURCE_REVISION="${SOURCE_REVISION:-local-transfer}"
BUILD_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TARBALL="srtime-web-linux-${VERSION}.tar.gz"

echo "=================================================="
echo "  SRTime — BUILD $VERSION  ($SOURCE_REVISION)"
echo "=================================================="

# ── 1. Compilar la API con Nuitka ─────────────────────────────────────────────
echo "→ [1/5] Compilando API con Nuitka..."
command -v "$PYTHON" >/dev/null || { echo "✗ $PYTHON no encontrado"; exit 1; }
"$PYTHON" -m nuitka --version >/dev/null 2>&1 || { echo "✗ nuitka no instalado en $PYTHON"; exit 1; }

rm -rf "$BUILD_DIR" "$STAGE"
mkdir -p "$BUILD_DIR"
cd "$PROJ_DIR/attendance"
"$PYTHON" -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --output-dir="$BUILD_DIR" \
    --include-package=api \
    --include-package=core \
    --include-package=models \
    --include-package=services \
    --include-package=uvicorn \
    --include-package=fastapi \
    --include-package=sqlalchemy \
    --include-package=passlib \
    --include-package=jwt \
    --include-package=cryptography \
    --include-package=dotenv \
    --include-package=alembic \
    --include-package=bcrypt \
    --include-package-data=limits \
    "$PROJ_DIR/deploy/run_api.py"

# Nuitka usa el sufijo .bin en este entorno Debian. El runtime e instalador
# exponen un nombre estable, independiente de ese detalle del compilador.
if [ -f "$BUILD_DIR/run_api.dist/run_api.bin" ]; then
    mv "$BUILD_DIR/run_api.dist/run_api.bin" "$BUILD_DIR/run_api.dist/run_api"
fi
[ -x "$BUILD_DIR/run_api.dist/run_api" ] || {
    echo "✗ Nuitka no generó el ejecutable esperado run_api" >&2
    exit 1
}

# ── 2. Compilar el frontend Next.js (export estático) ─────────────────────────
echo "→ [2/5] Compilando frontend Next.js (NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL)..."
cd "$PROJ_DIR/attendance/web"
# Instalar dependencias de Node (reproducible si hay lockfile)
if [ -f package-lock.json ]; then
    npm ci
else
    npm install
fi
NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" npm run build

# ── 3. Ensamblar el staging (solo binarios + config) ──────────────────────────
echo "→ [3/5] Ensamblando artefacto..."
mkdir -p "$STAGE/api" "$STAGE/web" "$STAGE/config"

cp -r "$BUILD_DIR/run_api.dist/." "$STAGE/api/"
cp -r out/. "$STAGE/web/"

# Config + instalador (sin fuente)
cp "$PROJ_DIR/deploy/.env.production.example"      "$STAGE/config/.env.example"
cp "$PROJ_DIR/deploy/linux/srtime-api.service"     "$STAGE/config/"
cp "$PROJ_DIR/deploy/linux/srtime-apache.conf"      "$STAGE/config/"
cp "$PROJ_DIR/deploy/linux/srtime-nginx.conf"      "$STAGE/config/"
cp "$PROJ_DIR/deploy/linux/install.sh"             "$STAGE/install.sh"
chmod +x "$STAGE/install.sh"

# ── 4. Manifiesto de compilación (dentro y fuera del tarball) ─────────────────
echo "→ [4/5] Generando BUILD_MANIFEST..."
API_SHA="$(sha256sum "$STAGE/api/run_api" | awk '{print $1}')"
MANIFEST="$STAGE/BUILD_MANIFEST.txt"
cat > "$MANIFEST" <<EOF
SRTime — Build Manifest
=======================
Version       : $VERSION
Built (UTC)    : $BUILD_UTC
Source revision: $SOURCE_REVISION
Builder host   : $(uname -srm)
Python         : $($PYTHON --version 2>&1)
Nuitka         : $($PYTHON -m nuitka --version 2>&1 | head -1)
Node           : $(node -v 2>&1)
npm            : $(npm -v 2>&1)
NEXT_PUBLIC_API_URL (build-time): $NEXT_PUBLIC_API_URL

SHA256
  api/run_api  : $API_SHA
EOF

# ── 5. Empaquetar + checksum + registro persistente ───────────────────────────
echo "→ [5/5] Empaquetando $TARBALL..."
cd "$DIST_DIR"
tar -czf "$TARBALL" srtime/
TAR_SHA="$(sha256sum "$TARBALL" | awk '{print $1}')"
echo "$TAR_SHA  $TARBALL" > "$TARBALL.sha256"
cp "$MANIFEST" "$DIST_DIR/BUILD_MANIFEST-${VERSION}.txt"
rm -rf "$STAGE"

# Registro de compilación persistente (commiteable)
REGISTRY="$PROJ_DIR/deploy/build-registry.md"
if [ ! -f "$REGISTRY" ]; then
    cat > "$REGISTRY" <<'EOF'
# SRTime — Registro de Compilaciones

Historial de artefactos de producción generados con `deploy/linux/build.sh`.

| Fecha (UTC) | Versión | Fuente | Artefacto | SHA256 (tar.gz) |
|-------------|---------|-----|-----------|-----------------|
EOF
fi
echo "| $BUILD_UTC | $VERSION | $SOURCE_REVISION | $TARBALL | \`$TAR_SHA\` |" >> "$REGISTRY"

echo "=================================================="
echo "✅ BUILD OK"
echo "  Artefacto : $DIST_DIR/$TARBALL"
echo "  SHA256    : $TAR_SHA"
echo "  Manifest  : $DIST_DIR/BUILD_MANIFEST-${VERSION}.txt"
echo "  Registro  : $REGISTRY"
echo "=================================================="
