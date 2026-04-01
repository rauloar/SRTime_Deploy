#!/bin/bash
set -e

APP_DIR="/home/raul/proyectos/SRTime"
REPO_URL="https://github.com/rauloar/SRTime_Deploy.git"

echo "=========================================="
echo "  SRTime Web — Setup en Debian 13"
echo "=========================================="

# 1. Instalar Node.js 20.x si no está
if ! command -v node &> /dev/null; then
    echo "[1/7] Instalando Node.js 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
    sudo apt install -y nodejs
else
    echo "[1/7] Node.js ya instalado: $(node -v)"
fi

# 2. Extraer el paquete pre-compilado
echo "[2/5] Extrayendo archivos binarios en $APP_DIR..."
mkdir -p "$APP_DIR"
cd "$(dirname "$APP_DIR")"

# Asumimos que el .tar.gz (srtime-web-linux.tar.gz) ya fue subido a la carpeta junto al script
if [ -f "srtime-web-linux.tar.gz" ]; then
    tar -xzf srtime-web-linux.tar.gz -C "$APP_DIR" --strip-components=1
else
    echo "❌ ERROR: No se encontró srtime-web-linux.tar.gz en $(pwd)"
    exit 1
fi

# Hacer ejecutables los binarios
chmod +x "$APP_DIR/api/run_api"
chmod +x "$APP_DIR/migrate_sqlite.py" 2>/dev/null || true


# 3. Copiar template de .env si no existe
echo "[3/5] Configuración..."
if [ ! -f "$APP_DIR/config/.env" ]; then
    cp "$APP_DIR/config/.env.example" "$APP_DIR/config/.env"
    echo ""
    echo "⚠️  EDITA $APP_DIR/config/.env con tus valores reales:"
    echo "   nano $APP_DIR/config/.env"
fi

# 4. Crear directorio de logs e instalar servicios
echo "[4/5] Instalando servicios..."
sudo mkdir -p /var/log/srtime
sudo chown raul:raul /var/log/srtime

# Instalar servicios systemd
sudo cp "$APP_DIR/config/srtime-api.service" /etc/systemd/system/
sudo cp "$APP_DIR/config/srtime-web.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable srtime-api srtime-web

# Habilitar módulos de Apache necesarios
sudo a2enmod proxy proxy_http proxy_wstunnel rewrite headers
sudo cp "$APP_DIR/config/srtime-apache.conf" /etc/apache2/sites-available/srtime.conf
sudo a2ensite srtime
sudo systemctl reload apache2

echo ""
echo "=========================================="
echo "  ✅ Setup completado"
echo "=========================================="
echo ""
echo "  Próximos pasos:"
echo "  1. Editar $APP_DIR/config/.env con credenciales"
echo "  2. Crear BD en PostgreSQL:"
echo "     sudo -u postgres createuser raul"
echo "     sudo -u postgres createdb -O raul srtime_attendance"
echo "  3. Abrir puerto 80 en UFW:"
echo "     sudo ufw allow 80/tcp"
echo "  4. Iniciar servicios:"
echo "     sudo systemctl start srtime-api srtime-web"
echo "  5. Verificar:"
echo "     curl http://localhost/api/health"
echo ""
