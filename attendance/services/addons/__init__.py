# Registry de addons — escanea subcarpetas con __manifest__.py (estilo Odoo)
import os
import importlib
import importlib.util

from .base_driver import BiometricDriver
from .base_parser import AttendanceParser


def get_available_addons():
    """
    Escanea subcarpetas de addons buscando __manifest__.py.
    Retorna un dict: { display_name: addon_info }
    """
    addons = {}
    addons_dir = os.path.dirname(__file__)

    for entry in os.listdir(addons_dir):
        entry_path = os.path.join(addons_dir, entry)
        manifest_path = os.path.join(entry_path, "__manifest__.py")

        if not os.path.isdir(entry_path) or not os.path.exists(manifest_path):
            continue
        if entry.startswith("__"):
            continue

        try:
            # Cargar manifest
            spec = importlib.util.spec_from_file_location(
                f"services.addons.{entry}.__manifest__", manifest_path
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
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
            "class": info.get("driver_class") or info.get("parser_class"),
            "is_driver": info["is_driver"],
            "connection_fields": info.get("connection_fields"),
        }
    return result


def get_addon_info(display_name: str):
    """Retorna info de un addon específico por nombre."""
    parsers = get_available_parsers()
    return parsers.get(display_name, None)


def get_parser_instance(display_name: str):
    """Instancia un driver o parser por nombre."""
    info = get_addon_info(display_name)
    if info and info.get("class"):
        return info["class"]()
    return None
