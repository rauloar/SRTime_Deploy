#!/bin/bash
set -e

# ==============================================================================
# SRTime Web — Setup Integrado para Debian (Validación, Clonado e Instalación)
# ==============================================================================
# Variables configurables — pueden sobreescribirse por entorno:
#   APP_USER=otrouser GIT_BRANCH=develop bash setup.sh
# ==============================================================================

APP_USER="${APP_USER:-$(whoami)}"
APP_DIR="${APP_DIR:-/home/$APP_USER/proyectos/SRTime}"
REPO_URL="${REPO_URL:-https://github.com/rauloar/SRTime_Deploy.git}"
GIT_BRANCH="${GIT_BRANCH:-master}"

echo "================================================="
echo "  🚀 INICIANDO SETUP DE SRTIME WEB EN DEBIAN"
echo "================================================="
echo "  Usuario : $APP_USER"
echo "  Directorio: $APP_DIR"
echo "  Rama    : $GIT_BRANCH"
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
check_pkg "python3-venv"
check_pkg "python3-pip"
check_pkg "python3-dev"
check_pkg "gcc"
check_pkg "g++"

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
    git reset --hard origin/$GIT_BRANCH
else
    echo "→ Clonando SRTime desde GitHub..."
    cd "$(dirname "$APP_DIR")"
    git clone --branch $GIT_BRANCH $REPO_URL "$(basename "$APP_DIR")"
    cd "$(basename "$APP_DIR")"
fi


echo -e "\n[3/6] 📦 CONSTRUYENDO Y PROTEGIENDO EL PAYLOAD BINARIO LOCALMENTE..."
# Busca si subiste el archivo empaquetado a esta misma carpeta (o root del server)
if [ ! -f "srtime-web-linux.tar.gz" ]; then
    echo "→ No se proveyó empaquetado precompilado. ¡Se compilará Nuitka y NextJS dentro de este servidor ahora mismo!"

    # Preparamos un entorno virtual ciego para Nuitka
    echo "→ Creando entorno de compilación temporal..."
    python3 -m venv "$APP_DIR/venv"
    source "$APP_DIR/venv/bin/activate"
    pip install --upgrade pip > /dev/null
    pip install -r "$APP_DIR/attendance/requirements-web.txt" > /dev/null
    pip install nuitka > /dev/null

    # Corremos el pipeline
    echo "→ Ejecutando pipeline aisla-código en $APP_DIR/deploy/linux/build.sh..."
    cd "$APP_DIR/deploy/linux"
    bash build.sh

    # Traemos el resultado y apagamos el virtual env
    deactivate
    cd "$(dirname "$APP_DIR")"
    cp "$APP_DIR/deploy/dist/linux/srtime-web-linux.tar.gz" "./"
fi

echo -e "\n[4/6] ⚙️ EXTRACCIÓN Y LIMPIEZA FINAL..."
echo "→ Acoplando binarios aislados..."
tar -xzf srtime-web-linux.tar.gz -C "$APP_DIR" --strip-components=1
chmod +x "$APP_DIR/api/run_api"
chmod +x "$APP_DIR/migrate_sqlite.py" 2>/dev/null || true

# Como ya extrajimos el binario, podemos eliminar el código fuente clonado inicialmente si se desea máxima seguridad local
# (Ocultando dependencias en ~/.git y raw código)
# rm -rf "$APP_DIR/attendance" "$APP_DIR/venv"


echo -e "\n[5/7] 🔐 CONFIGURANDO VARIABLES Y SEGURIDAD..."
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


echo -e "\n[6/7] ⚙️ CONFIGURANDO DEMONIOS Y PROXY REVERSO (APACHE)..."
sudo mkdir -p /var/log/srtime
sudo chown $APP_USER:$APP_USER /var/log/srtime

# Montar servicios sustituyendo placeholders con los valores reales
echo "→ Instalando servicios systemd..."
for SERVICE in srtime-api srtime-web; do
    SRC="$APP_DIR/config/$SERVICE.service"
    [ -f "$SRC" ] || SRC="$APP_DIR/deploy/linux/$SERVICE.service"
    sed -e "s|__APP_USER__|$APP_USER|g" \
        -e "s|__APP_DIR__|$APP_DIR|g" \
        "$SRC" | sudo tee /etc/systemd/system/$SERVICE.service > /dev/null
    echo "✅ $SERVICE.service instalado"
done

sudo systemctl daemon-reload
sudo systemctl enable srtime-api srtime-web

# Apache Virtual Hosts & Proxy Modules
echo "→ Activando Módulos Apache..."
sudo a2enmod proxy proxy_http proxy_wstunnel rewrite headers > /dev/null

# Sustituir SERVER_NAME en la config de Apache
SERVER_NAME="${SERVER_NAME:-$(hostname -I | awk '{print $1}')}"
APACHE_SRC="$APP_DIR/config/srtime-apache.conf"
[ -f "$APACHE_SRC" ] || APACHE_SRC="$APP_DIR/deploy/linux/srtime-apache.conf"
sed "s|__SERVER_NAME__|$SERVER_NAME|g" "$APACHE_SRC" | sudo tee /etc/apache2/sites-available/srtime.conf > /dev/null

sudo a2ensite srtime > /dev/null
sudo systemctl reload apache2


echo -e "\n[7/7] ✅ INSTALACIÓN ESTRUCTURAL COMPLETADA"
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
