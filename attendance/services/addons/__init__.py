# Registry de addons — escanea subcarpetas con __manifest__.py (estilo Odoo)
import os
import importlib
import importlib.util
from functools import lru_cache

@lru_cache(maxsize=1)
def get_available_addons():
    """
    Escanea subcarpetas de addons buscando __manifest__.py.
    Retorna un dict: { display_name: addon_info }
    """
    addons = {}
    # Perfil opcional para distribuciones acotadas (por ejemplo, el desktop de
    # prueba que sólo importa TM-MR001). Si no existe, se mantienen todos los
    # addons del producto; nunca se aplica un filtro hardcodeado global.
    enabled_raw = os.getenv("SRTIME_ENABLED_ADDONS", "").strip()
    enabled_addons = {
        item.strip().lower() for item in enabled_raw.split(",") if item.strip()
    }
    addons_dir = os.path.dirname(__file__)
    # A frozen executable stores Python modules inside its archive; therefore
    # there may be no physical ``services/addons`` directory beside the EXE.
    # An explicit profile remains discoverable by importing its packaged module.
    if enabled_addons:
        entries = sorted(enabled_addons)
    else:
        try:
            entries = os.listdir(addons_dir)
        except FileNotFoundError:
            entries = []

    for entry in entries:
        if entry.startswith("__"):
            continue
        entry_path = os.path.join(addons_dir, entry)
        manifest_path = os.path.join(entry_path, "__manifest__.py")

        try:
            if os.path.exists(manifest_path):
                # Desarrollo / instalación no congelada: cargar desde archivo
                # para descubrir addons incorporados sin un registro central.
                spec = importlib.util.spec_from_file_location(
                    f"services.addons.{entry}.__manifest__", manifest_path
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            else:
                # PyInstaller onefile: el manifest está dentro del archivo
                # empaquetado y se importa mediante el cargador de Python.
                mod = importlib.import_module(f"services.addons.{entry}.__manifest__")
            manifest = mod.manifest

            # Importar el módulo del addon
            addon_module = importlib.import_module(f"services.addons.{entry}")

            addon_info = {
                "manifest": manifest,
                "module": addon_module,
                "is_driver": manifest.get("type") in ("driver", "both"),
                "is_parser": manifest.get("type") in ("parser", "both"),
                "connection_fields": manifest.get("connection_fields"),
            }

            # Resolver clases
            driver_cls_name = manifest.get("driver_class")
            if driver_cls_name:
                addon_info["driver_class"] = getattr(addon_module, driver_cls_name)

            parser_cls_name = manifest.get("parser_class")
            if parser_cls_name:
                addon_info["parser_class"] = getattr(addon_module, parser_cls_name)

            addons[manifest["name"]] = addon_info
        except Exception as e:
            print(f"Error cargando addon {entry}: {e}")

    return addons


# ── Funciones de compatibilidad ──────────────────────────────
# Mantienen la misma API que usaban importer.py, import_tab.py (PySide6)
# para que NO se rompa ningún código existente.

def get_available_parsers():
    """
    Backward-compatible: retorna dict en el formato original.
    Usado por: api/routers/importer.py, ui/tabs/import_tab.py
    """
    addons = get_available_addons()
    result = {}
    for name, info in addons.items():
        result[name] = {
            # Compatibilidad: para importaciones de archivo la clase debe ser
            # siempre el parser. Un addon "both" también tiene driver, pero no
            # implementa parse_line().
            "class": info.get("parser_class"),
            "driver_class": info.get("driver_class"),
            "parser_class": info.get("parser_class"),
            "is_driver": info["is_driver"],
            "is_parser": info["is_parser"],
            "connection_fields": info.get("connection_fields"),
        }
    return result


def get_addon_info(display_name: str):
    """Retorna info de un addon específico por nombre."""
    return get_available_addons().get(display_name)


def get_parser_instance(display_name: str):
    """Instancia exclusivamente el parser de archivo de un addon."""
    info = get_addon_info(display_name)
    if info and info.get("parser_class"):
        return info["parser_class"]()
    return None


def clear_addon_cache() -> None:
    """Invalida el registry para desarrollo/instalación de addons."""
    get_available_addons.cache_clear()
