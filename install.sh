#!/usr/bin/env bash
# =============================================================================
# SRTime - Production Install Script for Linux (Ubuntu 22.04 / 24.04)
# =============================================================================
# Usage:
#   1. Clone the repo on the server
#   2. cd into the project root (same directory as this script)
#   3. chmod +x install.sh && sudo ./install.sh
#
# What this script does:
#   - Installs system dependencies (Python 3, Node.js 20, PostgreSQL, Nginx)
#   - Creates a PostgreSQL user and database
#   - Creates and populates .env from your input
#   - Creates a Python virtual environment and installs API packages
#   - Initialises the DB schema and creates the admin user
#   - Builds the Next.js frontend
#   - Creates systemd services for both API and web
#   - Configures Nginx as a reverse proxy
#   - Starts and enables all services
#
# NOTE: Windows desktop UI (PySide6/main.py) is NOT installed.
# =============================================================================
set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Must run as root ────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Este script debe ejecutarse como root: sudo ./install.sh"

# ─── Paths ───────────────────────────────────────────────────────────────────
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$INSTALL_DIR/venv"
WEB_DIR="$INSTALL_DIR/web"
SERVICE_USER="srtime"

info "Directorio de instalación: $INSTALL_DIR"

# =============================================================================
# 1. SYSTEM PACKAGES
# =============================================================================
info "Actualizando sistema e instalando dependencias base..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    curl git build-essential \
    libpq-dev

# Nginx y PostgreSQL ya están instalados en el servidor
info "Nginx:      $(nginx -v 2>&1 | head -1)"
info "PostgreSQL: $(psql --version 2>/dev/null || echo 'psql no en PATH, continuando...')"

# Node.js 20 LTS (via NodeSource)
if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d 'v') -lt 20 ]]; then
    info "Instalando Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi
info "Node $(node -v) / npm $(npm -v)"

# =============================================================================
# 2. CREATE SYSTEM USER
# =============================================================================
if ! id "$SERVICE_USER" &>/dev/null; then
    info "Creando usuario del sistema '$SERVICE_USER'..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# =============================================================================
# 3. POSTGRESQL SETUP
# =============================================================================
info "Configurando PostgreSQL (ya instalado)..."
# Solo nos aseguramos que esté corriendo
systemctl start postgresql 2>/dev/null || true

# Prompt for DB credentials
read -rp "Nombre de la base de datos [attendance]: " DB_NAME
DB_NAME="${DB_NAME:-attendance}"
read -rp "Usuario de PostgreSQL [srtime_user]: " DB_USER
DB_USER="${DB_USER:-srtime_user}"
read -rsp "Contraseña para el usuario de PostgreSQL: " DB_PASS; echo
[[ -z "$DB_PASS" ]] && error "La contraseña no puede estar vacía."

# Create postgres user and database (idempotent)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" \
    | grep -q 1 || sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" \
    | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
info "Base de datos '$DB_NAME' lista."

# =============================================================================
# 4. ENVIRONMENT FILE (.env)
# =============================================================================
info "Generando archivo .env..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cat > "$INSTALL_DIR/.env" <<EOF
# SRTime - Production Environment
DB_ENGINE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=$DB_USER
DB_PASS=$DB_PASS
DB_NAME=$DB_NAME
SECRET_KEY=$SECRET_KEY
EOF

chmod 600 "$INSTALL_DIR/.env"
info ".env generado con SECRET_KEY aleatoria."

# =============================================================================
# 5. PYTHON VIRTUAL ENVIRONMENT + API DEPENDENCIES
# =============================================================================
info "Creando entorno virtual Python..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q

# Server-side requirements only (no Windows/GUI packages)
info "Instalando dependencias del API (sin GUI)..."
"$VENV_DIR/bin/pip" install -q \
    fastapi \
    uvicorn[standard] \
    sqlalchemy \
    psycopg2-binary \
    python-dotenv \
    bcrypt \
    python-jose[cryptography] \
    pandas \
    openpyxl \
    reportlab \
    numpy

info "Dependencias Python instaladas."

# =============================================================================
# 6. DATABASE SCHEMA + DEFAULT ADMIN USER
# =============================================================================
info "Inicializando esquema de base de datos..."
cd "$INSTALL_DIR"
"$VENV_DIR/bin/python" -c "
from core.init_db import init_database
init_database()
print('Tablas creadas.')
"

info "Creando usuario admin de API..."
"$VENV_DIR/bin/python" create_api_admin.py

read -rp "¿Deseas agregar el turno horario por defecto? [S/n]: " ADD_SHIFT
if [[ "${ADD_SHIFT,,}" != "n" ]]; then
    "$VENV_DIR/bin/python" add_default_shift.py 2>/dev/null || warn "add_default_shift.py no encontrado, omitido."
fi

# =============================================================================
# 7. NEXT.JS FRONTEND BUILD
# =============================================================================
info "Instalando dependencias Node.js y compilando frontend..."
cd "$WEB_DIR"
npm ci --silent
npm run build
info "Build de Next.js completado."

# Ownership for service user
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# =============================================================================
# 8. SYSTEMD SERVICES
# =============================================================================
info "Creando servicios systemd..."

# ── API (FastAPI / Uvicorn) ──────────────────────────────────────────────────
cat > /etc/systemd/system/srtime-api.service <<EOF
[Unit]
Description=SRTime FastAPI Backend
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn api.main_api:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/srtime-api.log
StandardError=append:/var/log/srtime-api.log

[Install]
WantedBy=multi-user.target
EOF

# ── Web (Next.js) ───────────────────────────────────────────────────────────
cat > /etc/systemd/system/srtime-web.service <<EOF
[Unit]
Description=SRTime Next.js Frontend
After=network.target srtime-api.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$WEB_DIR
Environment=NODE_ENV=production
Environment=PORT=3000
ExecStart=$(which node) $WEB_DIR/node_modules/.bin/next start -p 3000
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/srtime-web.log
StandardError=append:/var/log/srtime-web.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable srtime-api srtime-web
systemctl start  srtime-api srtime-web

# =============================================================================
# 9. NGINX REVERSE PROXY
# =============================================================================
info "Configurando Nginx..."

# Prompt for domain / IP
read -rp "Dominio o IP del servidor (ej: srtime.miempresa.com o 192.168.1.10): " SERVER_NAME
SERVER_NAME="${SERVER_NAME:-_}"

cat > /etc/nginx/sites-available/srtime <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Frontend (Next.js)
    location / {
        proxy_pass         http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_cache_bypass \$http_upgrade;
    }

    # Backend API (FastAPI)
    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
    }

    # Static Next.js assets (cached)
    location /_next/static/ {
        proxy_pass http://127.0.0.1:3000;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    client_max_body_size 20M;
}
EOF

ln -sf /etc/nginx/sites-available/srtime /etc/nginx/sites-enabled/srtime
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
info "Nginx configurado."

# =============================================================================
# 10. FIREWALL (UFW)
# =============================================================================
if command -v ufw &>/dev/null; then
    info "Configurando firewall UFW..."
    ufw allow OpenSSH
    ufw allow 'Nginx HTTP'
    ufw --force enable
fi

# =============================================================================
# 11. STATUS CHECK
# =============================================================================
echo ""
info "═══════════════════════════════════════════════════════"
info "  INSTALACIÓN COMPLETADA"
info "═══════════════════════════════════════════════════════"
echo ""
echo -e "  ${GREEN}API Backend:${NC}  http://$SERVER_NAME/api/docs"
echo -e "  ${GREEN}Frontend:${NC}     http://$SERVER_NAME"
echo ""
echo "  Logs:"
echo "    API:  journalctl -u srtime-api -f"
echo "    Web:  journalctl -u srtime-web -f"
echo "    O también: tail -f /var/log/srtime-api.log"
echo ""
echo -e "  ${YELLOW}IMPORTANTE:${NC} El usuario admin fue creado con contraseña 'admin'."
echo -e "  ${YELLOW}→ Cambiá la contraseña desde la interfaz web antes de usar en producción.${NC}"
echo ""
systemctl status srtime-api --no-pager | head -8
systemctl status srtime-web --no-pager | head -8
