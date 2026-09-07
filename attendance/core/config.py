"""Ubicación única de configuración para SRTime.

El archivo local ``config/.env`` centraliza red, seguridad y base de datos.
Nunca se versiona; el repositorio sólo incluye ``config/.env.example``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ATTENDANCE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ATTENDANCE_DIR.parent


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
