"""Operaciones compartidas de terminales para API y PySide6."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from models.terminal import DeviceTerminal
from core.credentials import decrypt_credential, encrypt_credential


SECRET_FIELDS = frozenset({"password", "db_password", "token", "api_token", "secret", "api_key"})


class TerminalOperationError(RuntimeError):
    pass


def get_addon_info(terminal: DeviceTerminal) -> dict[str, Any]:
    import services.addons

    info = services.addons.get_addon_info(terminal.driver_name)
    if not info or not info.get("is_driver") or not info.get("driver_class"):
        raise TerminalOperationError(f"Driver '{terminal.driver_name}' no encontrado")
    return info


def get_driver_instance(terminal: DeviceTerminal):
    return get_addon_info(terminal)["driver_class"]()


def get_connection_params(terminal: DeviceTerminal) -> dict[str, Any]:
    """Obtiene parámetros genéricos, con fallback para terminales legacy."""
    params = dict(terminal.connection_params or {})
    if not params:
        params = {
            "ip": terminal.ip,
            "port": str(terminal.port) if terminal.port is not None else None,
            "password": terminal.password or "",
        }
    return {
        key: decrypt_credential(str(value)) if key.lower() in SECRET_FIELDS else value
        for key, value in params.items()
        if value is not None
    }


def public_connection_params(terminal: DeviceTerminal) -> dict[str, Any]:
    """Devuelve configuración editable sin revelar secretos."""
    params = dict(terminal.connection_params or {})
    if not params:
        params = {"ip": terminal.ip, "port": terminal.port}
    return {
        key: value
        for key, value in params.items()
        if key.lower() not in SECRET_FIELDS and value is not None
    }


def merge_connection_params(
    terminal: DeviceTerminal,
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    """Actualiza campos sin borrar secretos omitidos o enviados vacíos."""
    merged = get_connection_params(terminal) if terminal.id else {}
    for key, value in (updates or {}).items():
        if key.lower() in SECRET_FIELDS and (value is None or value == ""):
            continue
        if value is not None:
            merged[key] = (
                encrypt_credential(str(value)) if key.lower() in SECRET_FIELDS else value
            )
    for key in SECRET_FIELDS.intersection(merged):
        merged[key] = encrypt_credential(str(merged[key]))
    return merged


def _disconnect_safely(driver) -> None:
    try:
        driver.disconnect()
    except Exception:
        # La desconexión no debe ocultar el resultado o error principal.
        pass


def test_connection(terminal: DeviceTerminal) -> dict[str, Any]:
    driver = get_driver_instance(terminal)
    try:
        return driver.test_connection(get_connection_params(terminal))
    finally:
        _disconnect_safely(driver)


def sync_time(terminal: DeviceTerminal) -> bool:
    driver = get_driver_instance(terminal)
    try:
        return bool(driver.sync_time(get_connection_params(terminal)))
    finally:
        _disconnect_safely(driver)


def pull_logs(terminal: DeviceTerminal, session, progress_signal=None):
    from services.importer_service import import_from_driver

    driver = get_driver_instance(terminal)
    result = import_from_driver(
        driver,
        get_connection_params(terminal),
        session,
        progress_signal=progress_signal,
    )
    terminal.last_sync = datetime.now()
    session.commit()
    return result
