"""Preferencias de interfaz compartidas por SRTime_Win y la Web.

Expone el mismo ``ui.ini`` (junto al ``.env`` activo) que lee el Desktop. Sólo
informa qué pestañas opcionales se ocultan: ningún permiso ni endpoint cambia,
por lo que ocultar una pestaña no restringe el acceso a sus datos.
"""
from fastapi import APIRouter, Depends

from api.deps import get_current_user
from core.ui_settings import FIXED_TABS, OPTIONAL_TABS, load_hidden_tabs
from models.user import AuthUser

router = APIRouter()


@router.get("/settings")
def ui_settings(current_user: AuthUser = Depends(get_current_user)):
    return {
        "hidden_tabs": sorted(load_hidden_tabs()),
        "fixed_tabs": sorted(FIXED_TABS),
        "optional_tabs": sorted(OPTIONAL_TABS),
    }
