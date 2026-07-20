#!/usr/bin/env bash
# ==============================================================================
# SRTime — Descargar e instalar en el CLIENTE desde un GitHub Release privado
# ==============================================================================
# Baja SOLO el artefacto compilado (sin clonar el repo de fuente), verifica el
# checksum y ejecuta el instalador embebido. Resultado: el target nunca recibe
# código fuente Python.
#
# Requiere: gh CLI autenticado o GH_TOKEN con acceso de lectura al repo privado.
#
# Uso:
#   sudo -E DIST_REPO=rauloar/SRTime_Dist VERSION=v1.0.0 ./srtime-fetch.sh
#   (VERSION=latest baja el release más reciente)
#
# Variables extra se pasan al instalador (APP_DIR, SERVER_NAME, DB_NAME, ...).
# ==============================================================================
set -euo pipefail

DIST_REPO="${DIST_REPO:-rauloar/SRTime_Dist}"
VERSION="${VERSION:-latest}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

command -v gh >/dev/null || { echo "✗ gh CLI no instalado"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "✗ Ejecutá con sudo -E (para conservar GH_TOKEN)"; exit 1; }

echo "→ Descargando release '$VERSION' de $DIST_REPO (solo binario)..."
if [ "$VERSION" = latest ]; then
    gh release download --repo "$DIST_REPO" --pattern 'srtime-web-linux-*' --dir "$WORK"
else
    gh release download "$VERSION" --repo "$DIST_REPO" --pattern 'srtime-web-linux-*' --dir "$WORK"
fi

TARBALL="$(ls "$WORK"/srtime-web-linux-*.tar.gz | head -1)"
[ -f "$TARBALL" ] || { echo "✗ No se descargó ningún tarball"; exit 1; }

# Verificar checksum si vino el .sha256
if [ -f "$TARBALL.sha256" ]; then
    echo "→ Verificando SHA256..."
    ( cd "$WORK" && sha256sum -c "$(basename "$TARBALL").sha256" ) \
        || { echo "✗ Checksum inválido — descarga corrupta o manipulada"; exit 1; }
    echo "  ✔ Checksum OK"
fi

# Extraer SOLO el instalador embebido y ejecutarlo apuntando al tarball
tar -xzf "$TARBALL" -C "$WORK" --strip-components=1 srtime/install.sh
chmod +x "$WORK/install.sh"

echo "→ Ejecutando instalador..."
TARBALL="$TARBALL" "$WORK/install.sh"
