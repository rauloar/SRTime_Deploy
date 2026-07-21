#!/bin/bash
set -e

# Deriva APP_DIR desde la ubicación de este script
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
GIT_BRANCH="${GIT_BRANCH:-master}"

echo "=== SRTime Web — Actualización ==="
echo "  Directorio: $APP_DIR"
echo "  Rama      : $GIT_BRANCH"

# Pull últimos cambios
cd $APP_DIR
git pull origin $GIT_BRANCH

# Rebuild backend
echo "[1/4] Actualizando dependencias Python..."
source $APP_DIR/venv/bin/activate
pip install -r attendance/requirements-web.txt

# Rebuild frontend
echo "[2/4] Rebuild del frontend..."
cd $APP_DIR/attendance/web
npm ci --production=false
source $APP_DIR/attendance/.env
NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} npm run build

# Migraciones
echo "[3/4] Ejecutando migraciones de BD..."
cd $APP_DIR
PYTHONPATH=$APP_DIR/attendance alembic upgrade head 2>/dev/null || echo "   (sin migraciones pendientes)"

# Restart
echo "[4/4] Reiniciando servicios..."
sudo systemctl restart srtime-api

echo ""
echo "✅ SRTime Web actualizado"
sudo systemctl status srtime-api --no-pager -l
