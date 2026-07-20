#!/usr/bin/env bash
# ==============================================================================
# SRTime — Publicar artefacto compilado como GitHub Release (privado, sin fuente)
# ==============================================================================
# Sube el tar.gz + .sha256 + BUILD_MANIFEST a un Release de un repo de
# DISTRIBUCIÓN privado (separado del repo de código fuente). El cliente luego
# descarga SOLO el asset con un token — nunca clona la fuente.
#
# Requiere: gh CLI autenticado (gh auth login) o GH_TOKEN con scope repo.
#
# Variables:
#   DIST_REPO  repo privado de distribución   (default: rauloar/SRTime_Dist)
#   VERSION    tag/version del release          (default: del tarball más reciente)
#   NOTES      texto extra para las notas        (opcional)
# ==============================================================================
set -euo pipefail

PROJ_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$PROJ_DIR/deploy/dist/linux"
DIST_REPO="${DIST_REPO:-rauloar/SRTime_Dist}"

command -v gh >/dev/null || { echo "✗ gh CLI no instalado"; exit 1; }

# Detectar el tarball / versión
if [ -z "${VERSION:-}" ]; then
    TARBALL_PATH="$(ls -t "$DIST_DIR"/srtime-web-linux-*.tar.gz 2>/dev/null | head -1)"
    [ -n "$TARBALL_PATH" ] || { echo "✗ No hay tarball en $DIST_DIR — corré build.sh primero"; exit 1; }
    VERSION="$(basename "$TARBALL_PATH" | sed -E 's/^srtime-web-linux-(.*)\.tar\.gz$/\1/')"
else
    TARBALL_PATH="$DIST_DIR/srtime-web-linux-${VERSION}.tar.gz"
fi
[ -f "$TARBALL_PATH" ] || { echo "✗ No existe $TARBALL_PATH"; exit 1; }

SHA_PATH="$TARBALL_PATH.sha256"
MANIFEST_PATH="$DIST_DIR/BUILD_MANIFEST-${VERSION}.txt"

echo "→ Publicando Release '$VERSION' en repo privado $DIST_REPO"
echo "  Artefacto: $(basename "$TARBALL_PATH")"

ASSETS=("$TARBALL_PATH")
[ -f "$SHA_PATH" ]      && ASSETS+=("$SHA_PATH")
[ -f "$MANIFEST_PATH" ] && ASSETS+=("$MANIFEST_PATH")

NOTES_BODY="SRTime build \`$VERSION\` — artefacto compilado (sin código fuente)."
[ -n "${NOTES:-}" ] && NOTES_BODY="$NOTES_BODY"$'\n\n'"$NOTES"
[ -f "$MANIFEST_PATH" ] && NOTES_BODY="$NOTES_BODY"$'\n\n```\n'"$(cat "$MANIFEST_PATH")"$'\n```'

if gh release view "$VERSION" --repo "$DIST_REPO" >/dev/null 2>&1; then
    echo "→ El release ya existe — subiendo/clobbering assets"
    gh release upload "$VERSION" "${ASSETS[@]}" --repo "$DIST_REPO" --clobber
else
    gh release create "$VERSION" "${ASSETS[@]}" \
        --repo "$DIST_REPO" \
        --title "SRTime $VERSION" \
        --notes "$NOTES_BODY"
fi

echo "✅ Release publicado: https://github.com/$DIST_REPO/releases/tag/$VERSION"
