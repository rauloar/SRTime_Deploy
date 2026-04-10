#!/bin/bash
set -e

# ==============================================================================
# SRTime Web — Setup Integrado para Debian (Validación, Clonado e Instalación)
# Ubicación Final: /home/raul/proyectos/SRTime
# ==============================================================================

APP_DIR="/home/raul/proyectos/SRTime"
REPO_URL="https://github.com/rauloar/SRTime_Deploy.git"
APP_USER="raul"

echo "================================================="
echo "  🚀 INICIANDO SETUP DE SRTIME WEB EN DEBIAN"
echo "================================================="

# Variables globales para control de instalación
MISSING_PKGS=""

# Función para verificar dependencias
check_pkg() {
    if ! dpkg -l | grep -qw "$1"; then
        MISSING_PKGS="$MISSING_PKGS $1"
        echo "❌ Faltante: $1"
    else
        echo "✅ Instalado: $1"
    fi
}

echo -e "\n[1/6] 🔍 CHEQUEANDO DEPENDENCIAS DE SISTEMA..."
sudo apt-get update -qq

# Verificamos Apache y módulos core
check_pkg "apache2"
check_pkg "postgresql"
check_pkg "libpq5" 
check_pkg "libpq-dev"
check_pkg "tzdata"
check_pkg "curl"
check_pkg "git"
check_pkg "openssl"

# Verificamos NodeJS interactuando con su versión
if ! command -v node &> /dev/null; then
    echo "❌ Faltante: nodejs (Motor Node)"
    INSTALL_NODE=true
else
    echo "✅ Instalado: nodejs ($(node -v))"
    INSTALL_NODE=false
fi

# Instalar los faltantes si aplicara
if [ -n "$MISSING_PKGS" ]; then
    echo -e "\n[!] 🔧 Instalando paquetes faltantes: $MISSING_PKGS"
    sudo apt-get install -y $MISSING_PKGS
fi

if [ "$INSTALL_NODE" = true ]; then
    echo -e "\n[!] 🔧 Instalando NodeJS 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
    sudo apt-get install -y nodejs
fi

echo -e "\n[2/6] 📥 OBTENIENDO CÓDIGO DEL REPOSITORIO..."
sudo mkdir -p "$(dirname "$APP_DIR")"
sudo chown $APP_USER:$APP_USER "$(dirname "$APP_DIR")"

if [ -d "$APP_DIR/.git" ]; then
    echo "→ Actualizando Repositorio Existente..."
    cd "$APP_DIR"
    git fetch origin
    git reset --hard origin/master
else
    echo "→ Clonando SRTime desde GitHub..."
    cd "$(dirname "$APP_DIR")"
    git clone $REPO_URL SRTime
    cd SRTime
fi


echo -e "\n[3/6] 📦 DESPLIEGUE DEL PAYLOAD BINARIO (NUITKA + NEXTJS)..."
# Busca si subiste el archivo empaquetado a esta misma carpeta (o root del server)
if [ -f "srtime-web-linux.tar.gz" ]; then
    echo "→ Extrayendo paquete binario..."
    tar -xzf srtime-web-linux.tar.gz -C "$APP_DIR" --strip-components=1
    chmod +x "$APP_DIR/api/run_api"
    chmod +x "$APP_DIR/migrate_sqlite.py" 2>/dev/null || true
else
    echo ""
    echo "⚠️ ADVERTENCIA: No se encontró 'srtime-web-linux.tar.gz'!"
    echo "Clonamos el código fuente, per para usar la arquitectura compilada y protegida"
    echo "debes proveer este archivo generado mediante deploy/linux/build.sh."
    echo "Si deseas compilarlo tú mismo DENTRO del servidor, ejecuta ahora:"
    echo "  > cd $APP_DIR/deploy/linux && bash build.sh"
    echo "Y luego vuelve a correr este setup.sh."
    echo "Pausando instalación..."
    exit 1
fi


echo -e "\n[4/6] 🔐 CONFIGURANDO VARIABLES Y SEGURIDAD..."
if [ ! -f "$APP_DIR/config/.env" ]; then
    mkdir -p "$APP_DIR/config"
    cp "$APP_DIR/config/.env.example" "$APP_DIR/config/.env" 2>/dev/null || cp "$APP_DIR/deploy/.env.production.example" "$APP_DIR/config/.env"
    
    # Inyectar una llave secreta maestra (JWT - 256 bits)
    NEW_SECRET=$(openssl rand -hex 32)
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_SECRET/g" "$APP_DIR/config/.env"
    
    # CHMOD 600 evita que otros usuarios lean la base de base de datos Postgres del cliente
    chmod 600 "$APP_DIR/config/.env"
    echo "→ Archivo JWT configurado. Deberás cargar la contraseña de Postgres manualmente."
fi


echo -e "\n[5/6] ⚙️ CONFIGURANDO DEMONIOS Y PROXY REVERSO (APACHE)..."
sudo mkdir -p /var/log/srtime
sudo chown $APP_USER:$APP_USER /var/log/srtime

# Montaje de Demonios Linux
sudo cp "$APP_DIR/config/srtime-api.service" /etc/systemd/system/ 2>/dev/null || sudo cp "$APP_DIR/deploy/linux/srtime-api.service" /etc/systemd/system/
sudo cp "$APP_DIR/config/srtime-web.service" /etc/systemd/system/ 2>/dev/null || sudo cp "$APP_DIR/deploy/linux/srtime-web.service" /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable srtime-api srtime-web

# Apache Virtual Hosts & Proxy Modules
echo "→ Activando Módulos Apache..."
sudo a2enmod proxy proxy_http proxy_wstunnel rewrite headers > /dev/null

sudo cp "$APP_DIR/config/srtime-apache.conf" /etc/apache2/sites-available/srtime.conf 2>/dev/null || sudo cp "$APP_DIR/deploy/linux/srtime-apache.conf" /etc/apache2/sites-available/srtime.conf
sudo a2ensite srtime > /dev/null
sudo systemctl reload apache2


echo -e "\n[6/6] ✅ INSTALACIÓN ESTRUCTURAL COMPLETADA"
echo "================================================="
echo " PASOS RESTANTES MANUALES:"
echo ""
echo " 1. Edita el archivo central de configuración:"
echo "    nano $APP_DIR/config/.env"
echo ""
echo " 2. Enlaza / Crea la instancia PostgreSQL (Si aún no está creada):"
echo "    sudo -u postgres createuser $APP_USER"
echo "    sudo -u postgres createdb -O $APP_USER srtime_attendance"
echo ""
echo " 3. Arranca los motores lógicos y biométricos:"
echo "    sudo systemctl start srtime-api srtime-web"
echo ""
echo " 4. (Opcional) Abre UFW para tráfico http:"
echo "    sudo ufw allow 80/tcp"
echo ""
echo "  Monitor de Status:"
echo "    curl http://localhost/api/health"
echo "    sudo journalctl -u srtime-api -f"
echo "================================================="
