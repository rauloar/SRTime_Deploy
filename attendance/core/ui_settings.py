"""Visibilidad de las pestañas del menú principal de SRTime_Win y de la Web.

El archivo local ``ui.ini`` vive junto al ``.env`` activo (al lado de
``SRTime_Win.exe`` instalado, en ``config/`` de SRTime_Web, o ``config/ui.ini``
en desarrollo). Sólo oculta pestañas en la interfaz: los widgets se siguen
creando y ningún servicio, modelo, permiso ni endpoint cambia. La Web lo recibe
por ``GET /api/ui/settings``. El repositorio incluye ``config/ui.ini.example``.

Cualquier ausencia o error deja cada pestaña en su valor por defecto, para que
una configuración dañada nunca haga desaparecer una función. Por defecto todas
se ven, salvo en el Desktop: arranca sin Dashboard
(``DESKTOP_DEFAULT_HIDDEN_TABS``) y ``dashboard = true`` lo vuelve a mostrar.
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

# El Desktop (SRTime_Win) arranca sin Dashboard; la Web lo muestra. Única
# fuente del valor: el ui.ini del paquete Desktop se genera desde acá.
DESKTOP_DEFAULT_HIDDEN_TABS = frozenset({"dashboard"})

logger = logging.getLogger(__name__)


def resolve_ui_settings_path() -> Path:
    """Devuelve la ruta de ``ui.ini``, siempre junto al ``.env`` activo."""
    return resolve_env_path().parent / UI_SETTINGS_FILENAME


def load_hidden_tabs(path: Path | None = None, default_hidden: frozenset[str] = frozenset()) -> frozenset[str]:
    """Devuelve las claves de pestañas opcionales ocultas.

    ``default_hidden`` son las que se ocultan cuando el ``ui.ini`` no dice nada
    de ellas (o falta, o está dañado); un ``true`` explícito las muestra.
    """
    path = path or resolve_ui_settings_path()
    default_hidden = frozenset(default_hidden) & OPTIONAL_TABS
    if not path.is_file():
        return default_hidden

    # ``interpolation=None``: un ``%`` escrito a mano no debe romper la lectura.
    parser = configparser.ConfigParser(interpolation=None)
    try:
        # ``utf-8-sig`` acepta el BOM que agrega el Bloc de notas.
        with path.open(encoding="utf-8-sig") as handle:
            parser.read_file(handle)
    except (OSError, UnicodeDecodeError, configparser.Error) as exc:
        logger.warning("No se pudo leer %s (%s); se usan las pestañas por defecto.", path, exc)
        return default_hidden

    if not parser.has_section(TABS_SECTION):
        return default_hidden

    hidden = set(default_hidden)
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
            hidden.discard(key)
            continue
        if key in FIXED_TABS:
            logger.warning("%s: la pestaña '%s' es fija y no se puede ocultar.", path, key)
            continue
        hidden.add(key)
    return frozenset(hidden)


def desktop_ui_ini(example_text: str) -> str:
    """``ui.ini`` del paquete Desktop: el ejemplo con ``DESKTOP_DEFAULT_HIDDEN_TABS`` en ``false``."""
    lines = []
    for line in example_text.splitlines():
        key = line.split("=", 1)[0].strip().lower() if "=" in line and not line.lstrip().startswith((";", "#")) else ""
        lines.append(f"{key} = false" if key in DESKTOP_DEFAULT_HIDDEN_TABS else line)
    return "\n".join(lines) + "\n"


def write_desktop_ui_ini(example_path: Path, destination: Path) -> None:
    """Lo usa el build del Desktop para generar el ``ui.ini`` que instala."""
    text = Path(example_path).read_text(encoding="utf-8-sig")
    Path(destination).write_text(desktop_ui_ini(text), encoding="utf-8")
