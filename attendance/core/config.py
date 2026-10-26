"""Ubicación única de configuración para SRTime.

El archivo local ``config/.env`` centraliza red, seguridad y base de datos.
Nunca se versiona; el repositorio sólo incluye ``config/.env.example``.
"""

from __future__ import annotations

import os
import re
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv


ATTENDANCE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ATTENDANCE_DIR.parent

# Claves propias de cada instalación. Un paquete distribuible trae el marcador
# ``__GENERATE__`` (o cualquier ``__...__``) y nunca un valor real compartido.
INSTALLATION_SECRET_KEYS = ("SECRET_KEY", "TERMINAL_CREDENTIAL_KEY")
_SECRET_PLACEHOLDER = re.compile(
    r"^(?P<key>" + "|".join(INSTALLATION_SECRET_KEYS) + r")=__[^\r\n]*__[ \t]*$", re.MULTILINE
)


def runtime_root() -> Path:
    """Directorio base para rutas relativas de datos (SQLite, logs).

    PyInstaller ejecuta los módulos desde ``_internal``; los datos del cliente
    deben quedar junto a ``SRTime_Win.exe``, donde el instalador los preserva.
    En desarrollo y en Nuitka Web se conserva el directorio ``attendance``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent
    return ATTENDANCE_DIR


def resolve_env_path() -> Path:
    """Devuelve el perfil explícito o el archivo global de configuración."""
    explicit = os.getenv("SRTIME_ENV_FILE")
    if explicit:
        return Path(explicit)

    # El ejecutable PyInstaller de escritorio guarda su perfil junto a
    # ``SRTime.exe``. Nuitka Web conserva config/.env dos niveles arriba.
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent / ".env"

    if "__compiled__" in globals():
        return Path(sys.argv[0]).resolve().parent.parent / "config" / ".env"

    return PROJECT_ROOT / "config" / ".env"


def load_application_env() -> Path:
    """Carga el perfil sin sobrescribir variables proporcionadas por el launcher."""
    env_path = resolve_env_path()
    load_dotenv(env_path, override=False)
    return env_path


def ensure_installation_secrets(env_path: Path) -> bool:
    """Reemplaza marcadores ``__...__`` por claves nuevas; nunca rota claves reales.

    Conserva comentarios y orden del archivo. Devuelve ``True`` si escribió claves.
    """
    if not env_path.is_file():
        return False
    content = env_path.read_text(encoding="utf-8")
    updated = _SECRET_PLACEHOLDER.sub(
        lambda match: f"{match.group('key')}={secrets.token_urlsafe(48)}", content
    )
    if updated == content:
        return False
    temporary = env_path.with_suffix(env_path.suffix + ".tmp")
    temporary.write_text(updated, encoding="utf-8")
    os.replace(temporary, env_path)
    return True
