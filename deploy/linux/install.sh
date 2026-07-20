#!/usr/bin/env bash
# ==============================================================================
# SRTime — Instalador OS-aware desde artefacto compilado (sin código fuente)
# ==============================================================================
# Instala un tarball ya construido (binario Nuitka + Next.js standalone) en un
# servidor Linux. NO clona el repo, NO compila, NO requiere Python ni código
# fuente. Pensado para entrega a cliente.
#
# Requisitos del SO que instala automáticamente: postgresql, nginx, nodejs.
# Soporta gestores de paquetes: pacman (Arch/Manjaro) y apt (Debian/Ubuntu).
#
# Uso:
#   sudo TARBALL=/ruta/srtime-web-linux.tar.gz ./install.sh
#
# Variables (todas con default razonable, sin nada hardcodeado al equipo):
#   APP_USER     usuario dueño de la app        (default: usuario que invoca)
#   APP_DIR      directorio de instalación       (default: /opt/srtime)
#   TARBALL      ruta al .tar.gz compilado        (REQUERIDO)
#   SERVER_NAME  IP/dominio para nginx            (default: IP primaria del host)
#   DB_NAME      base de datos PostgreSQL         (default: srtime_attendance)
#   DB_USER      rol PostgreSQL                   (default: srtime)
#   DB_PASS      password del rol                 (default: se genera aleatorio)
#   ADMIN_PASS   password inicial del admin       (default: se genera aleatorio)
# ==============================================================================
set -euo pipefail

# ── Parámetros ────────────────────────────────────────────────────────────────
APP_USER="${APP_USER:-${SUDO_USER:-$(id -un)}}"
APP_DIR="${APP_DIR:-/opt/srtime}"
TARBALL="${TARBALL:-}"
SERVER_NAME="${SERVER_NAME:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
DB_NAME="${DB_NAME:-srtime_attendance}"
DB_USER="${DB_USER:-srtime}"
DB_PASS="${DB_PASS:-$(openssl rand -hex 16)}"
ADMIN_PASS="${ADMIN_PASS:-$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-12)}"

log()  { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32m✔\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Ejecutá con sudo/root (instala paquetes y servicios)."
[ -n "$TARBALL" ]    || die "Falta TARBALL=/ruta/srtime-web-linux.tar.gz"
[ -f "$TARBALL" ]    || die "No existe el tarball: $TARBALL"
id "$APP_USER" >/dev/null 2>&1 || die "El usuario '$APP_USER' no existe."

log "Configuración del deploy"
cat <<EOF
  APP_USER    : $APP_USER
  APP_DIR     : $APP_DIR
  TARBALL     : $TARBALL
  SERVER_NAME : $SERVER_NAME
  DB_NAME     : $DB_NAME
  DB_USER     : $DB_USER
EOF

# ── 1. Detección de gestor de paquetes e instalación de dependencias ──────────
log "[1/7] Instalando dependencias del sistema (postgresql, nginx, nodejs)..."
if command -v pacman >/dev/null 2>&1; then
    PKG_MGR=pacman
    pacman -Sy --noconfirm --needed postgresql nginx nodejs openssl >/dev/null
elif command -v apt-get >/dev/null 2>&1; then
    PKG_MGR=apt
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq postgresql nginx nodejs openssl >/dev/null
else
    die "Gestor de paquetes no soportado (se esperaba pacman o apt-get)."
fi
ok "Dependencias instaladas vía $PKG_MGR"
command -v node >/dev/null 2>&1 || die "node no quedó disponible tras instalar."

# ── 2. PostgreSQL: inicializar cluster (Arch), arrancar, crear rol + DB ───────
log "[2/7] Configurando PostgreSQL..."
if [ "$PKG_MGR" = pacman ]; then
    PGDATA="/var/lib/postgres/data"
    if [ ! -s "$PGDATA/PG_VERSION" ]; then
        ok "Inicializando cluster PostgreSQL en $PGDATA"
        install -d -o postgres -g postgres "$PGDATA"
        sudo -u postgres initdb --locale=C.UTF-8 --encoding=UTF8 -D "$PGDATA" >/dev/null
    fi
fi
systemctl enable --now postgresql >/dev/null 2>&1 || systemctl restart postgresql

# Rol + base de datos (idempotente)
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    sudo -u postgres psql -qc "CREATE ROLE \"$DB_USER\" LOGIN PASSWORD '$DB_PASS';"
    ok "Rol '$DB_USER' creado"
else
    sudo -u postgres psql -qc "ALTER ROLE \"$DB_USER\" LOGIN PASSWORD '$DB_PASS';"
    ok "Rol '$DB_USER' ya existía — password actualizado"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
    ok "Base '$DB_NAME' creada"
else
    ok "Base '$DB_NAME' ya existía"
fi

# ── 3. Extraer el artefacto (solo binarios, sin fuente) ───────────────────────
log "[3/7] Extrayendo artefacto en $APP_DIR..."
install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"
tar -xzf "$TARBALL" -C "$APP_DIR" --strip-components=1
chmod +x "$APP_DIR/api/run_api"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
[ -f "$APP_DIR/api/run_api" ] || die "El tarball no contiene api/run_api."
[ -f "$APP_DIR/web/server.js" ] || die "El tarball no contiene web/server.js."
ok "Artefacto extraído"

# ── 4. Generar .env único con secretos (chmod 600) ────────────────────────────
log "[4/7] Generando configuración con secretos..."
install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR/config"
ENV_FILE="$APP_DIR/config/.env"
SECRET_KEY="$(openssl rand -hex 32)"
cat > "$ENV_FILE" <<EOF
DB_ENGINE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=$DB_USER
DB_PASS=$DB_PASS
DB_NAME=$DB_NAME
SECRET_KEY=$SECRET_KEY
API_HOST=127.0.0.1
API_PORT=8000
API_WORKERS=4
CORS_ORIGINS=["http://$SERVER_NAME"]
NEXT_PUBLIC_API_URL=/api
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_DIR=/var/log/srtime
EOF
chown "$APP_USER:$APP_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"
ok ".env generado (600) en $ENV_FILE"

install -d -o "$APP_USER" -g "$APP_USER" /var/log/srtime

# ── 5. Bootstrap de la base de datos (create_all + seed admin) ────────────────
log "[5/7] Inicializando esquema y usuario admin..."
sudo -u "$APP_USER" env \
    SRTIME_ENV_FILE="$ENV_FILE" \
    RUN_DB_BOOTSTRAP=1 \
    SRTIME_ADMIN_PASSWORD="$ADMIN_PASS" \
    "$APP_DIR/api/run_api"
ok "Base inicializada"

# ── 6. Servicios systemd ──────────────────────────────────────────────────────
log "[6/7] Instalando servicios systemd..."
for SERVICE in srtime-api srtime-web; do
    sed -e "s|__APP_USER__|$APP_USER|g" \
        -e "s|__APP_DIR__|$APP_DIR|g" \
        "$APP_DIR/config/$SERVICE.service" > "/etc/systemd/system/$SERVICE.service"
    ok "$SERVICE.service instalado"
done
systemctl daemon-reload
systemctl enable --now srtime-api srtime-web >/dev/null 2>&1 || true

# ── 7. Reverse proxy nginx ────────────────────────────────────────────────────
log "[7/7] Configurando reverse proxy nginx..."
NGINX_CONF="$APP_DIR/config/srtime-nginx.conf"
RENDERED="$(sed "s|__SERVER_NAME__|$SERVER_NAME|g" "$NGINX_CONF")"
if [ -d /etc/nginx/sites-available ]; then           # Debian/Ubuntu
    printf '%s\n' "$RENDERED" > /etc/nginx/sites-available/srtime.conf
    ln -sf /etc/nginx/sites-available/srtime.conf /etc/nginx/sites-enabled/srtime.conf
    rm -f /etc/nginx/sites-enabled/default
else                                                  # Arch/Manjaro
    install -d /etc/nginx/conf.d
    printf '%s\n' "$RENDERED" > /etc/nginx/conf.d/srtime.conf
fi
nginx -t >/dev/null 2>&1 || die "Configuración nginx inválida (nginx -t falló)."
systemctl enable --now nginx >/dev/null 2>&1 || systemctl reload nginx
ok "nginx configurado y recargado"

# ── Resumen ───────────────────────────────────────────────────────────────────
log "✅ INSTALACIÓN COMPLETA"
cat <<EOF
  URL          : http://$SERVER_NAME/
  Admin user   : admin
  Admin pass   : $ADMIN_PASS   (se exige cambiarlo al primer login)
  DB user/pass : $DB_USER / $DB_PASS
  .env         : $ENV_FILE (chmod 600)

  Verificación:
    curl -fsS http://localhost/api/health
    systemctl status srtime-api srtime-web nginx

  ⚠ Guardá estas credenciales: no se vuelven a mostrar.
EOF
