"""Visibilidad de las pestañas del menú principal de SRTime_Win y de la Web.

El archivo local ``ui.ini`` vive junto al ``.env`` activo (al lado de
``SRTime_Win.exe`` instalado, en ``config/`` de SRTime_Web, o ``config/ui.ini``
en desarrollo). Sólo oculta pestañas en la interfaz: los widgets se siguen
creando y ningún servicio, modelo, permiso ni endpoint cambia. La Web lo recibe
por ``GET /api/ui/settings``. El repositorio incluye ``config/ui.ini.example``.

Cualquier ausencia o error deja la pestaña visible, para que una configuración
dañada nunca haga desaparecer una función.
"""

from __future__ import annotations

import configparser
import logging
from pathlib import Path

from core.config import resolve_env_path


UI_SETTINGS_FILENAME = "ui.ini"
TABS_SECTION = "pestanas"

# Pestañas que el ``ui.ini`` no puede ocultar.
FIXED_TABS = frozenset({
    "importar",
    "empleados",
    "turnos_horarios",
    "movimientos",
    "movimientos_procesados",
})
OPTIONAL_TABS = frozenset({
    "dashboard",
    "terminales",
    "ausencias",
    "feriados",
    "reportes",
    "usuarios_autorizados",
})

logger = logging.getLogger(__name__)


def resolve_ui_settings_path() -> Path:
    """Devuelve la ruta de ``ui.ini``, siempre junto al ``.env`` activo."""
    return resolve_env_path().parent / UI_SETTINGS_FILENAME


def load_hidden_tabs(path: Path | None = None) -> frozenset[str]:
    """Devuelve las claves de pestañas opcionales marcadas como ocultas."""
    path = path or resolve_ui_settings_path()
    if not path.is_file():
        return frozenset()

    # ``interpolation=None``: un ``%`` escrito a mano no debe romper la lectura.
    parser = configparser.ConfigParser(interpolation=None)
    try:
        # ``utf-8-sig`` acepta el BOM que agrega el Bloc de notas.
        with path.open(encoding="utf-8-sig") as handle:
            parser.read_file(handle)
    except (OSError, UnicodeDecodeError, configparser.Error) as exc:
        logger.warning("No se pudo leer %s (%s); se muestran todas las pestañas.", path, exc)
        return frozenset()

    if not parser.has_section(TABS_SECTION):
        return frozenset()

    hidden = set()
    for key, raw_value in parser.items(TABS_SECTION):
        if key not in FIXED_TABS and key not in OPTIONAL_TABS:
            logger.warning("%s: pestaña desconocida '%s'; se ignora.", path, key)
            continue
        try:
            visible = parser.getboolean(TABS_SECTION, key)
        except ValueError:
            logger.warning("%s: valor inválido '%s' para '%s'; queda visible.", path, raw_value, key)
            continue
        if visible:
            continue
        if key in FIXED_TABS:
            logger.warning("%s: la pestaña '%s' es fija y no se puede ocultar.", path, key)
            continue
        hidden.add(key)
    return frozenset(hidden)
