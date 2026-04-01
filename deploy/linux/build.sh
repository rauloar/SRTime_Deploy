#!/bin/bash
# ==============================================================================
# SRTime Web — Build Wrapper para Producción Linux (Nuitka + Next.js Standalone)
# ==============================================================================
set -e

PROJ_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$PROJ_DIR/deploy/dist/linux"
BUILD_DIR="$PROJ_DIR/deploy/build/linux"

echo "=========================================="
echo "  🚀 INICIANDO BUILD WEB PROD PARA LINUX"
echo "=========================================="

# 1. Instalar Nuitka (requiere gcc/g++ en el sistema base)
echo "→ [1/4] Verificando dependencias Python..."
cd $PROJ_DIR
# Asumimos que el venv está activado, en caso contrario instalar dependencias.
pip install nuitka

# 2. Compilar con Nuitka
echo "→ [2/4] Compilando Backend API con Nuitka..."
mkdir -p "$BUILD_DIR"
cd "$PROJ_DIR"

python -m nuitka \
    --standalone \
    --output-dir="$BUILD_DIR" \
    --include-package=api \
    --include-package=core \
    --include-package=models \
    --include-package=services \
    --include-package=uvicorn \
    --include-package=fastapi \
    --include-package=sqlalchemy \
    --include-package=passlib \
    --include-package=jose \
    --include-package=dotenv \
    --include-package=alembic \
    --include-package=bcrypt \
    "$PROJ_DIR/deploy/run_api.py"

# 3. Empaquetar el Frontend Next.js Standalone
echo "→ [3/4] Construyendo Frontend Next.js..."
cd "$PROJ_DIR/attendance/web"
npm run build

# 4. Crear el artefacto final (tar.gz)
echo "→ [4/4] Empaquetando para producción..."
mkdir -p "$DIST_DIR/srtime/api"
mkdir -p "$DIST_DIR/srtime/web"
mkdir -p "$DIST_DIR/srtime/config"

# Copiar Binario del API
cp -r "$BUILD_DIR/run_api.dist/"* "$DIST_DIR/srtime/api/"

# Copiar Standalone Frontend Web
cd "$PROJ_DIR/attendance/web"
cp -r .next/standalone/* "$DIST_DIR/srtime/web/"
mkdir -p "$DIST_DIR/srtime/web/.next"
cp -r .next/static "$DIST_DIR/srtime/web/.next/static"
cp -r public "$DIST_DIR/srtime/web/public" 2>/dev/null || true

# Copiar herramientas de config / deploy
cp "$PROJ_DIR/deploy/.env.production.example" "$DIST_DIR/srtime/config/.env.example"
cp "$PROJ_DIR/deploy/linux/srtime-api.service" "$DIST_DIR/srtime/config/"
cp "$PROJ_DIR/deploy/linux/srtime-web.service" "$DIST_DIR/srtime/config/"
cp "$PROJ_DIR/deploy/linux/srtime-apache.conf" "$DIST_DIR/srtime/config/"
cp "$PROJ_DIR/deploy/linux/setup.sh" "$DIST_DIR/srtime/"
cp "$PROJ_DIR/deploy/linux/start.sh" "$DIST_DIR/srtime/"
cp "$PROJ_DIR/deploy/linux/stop.sh" "$DIST_DIR/srtime/"
cp "$PROJ_DIR/attendance/migrate_sqlite.py" "$DIST_DIR/srtime/"

cd "$DIST_DIR"
tar -czf srtime-web-linux.tar.gz srtime/
rm -rf srtime/

echo "✅ BUILD COMPLETADO:"
echo "El paquete listo para subir al servidor Debian se encuentra en:"
echo "📁 $DIST_DIR/srtime-web-linux.tar.gz"
echo "Solo debes copiar ese .tar.gz al servidor y ejecutar setup.sh"
