#!/bin/bash
set -e
APP_DIR="/home/raul/proyectos/SRTime"

echo "=== SRTime Web — Actualización ==="

# Pull últimos cambios
cd $APP_DIR
git pull origin main

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
sudo systemctl restart srtime-api srtime-web

echo ""
echo "✅ SRTime Web actualizado"
sudo systemctl status srtime-api srtime-web --no-pager -l
