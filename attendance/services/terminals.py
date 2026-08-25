"""Operaciones compartidas de terminales para API y PySide6."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from models.terminal import DeviceTerminal
from models.employee import User
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


def supports_capability(terminal: DeviceTerminal, capability: str) -> bool:
    """Consulta capacidades declaradas por el manifest, nunca por la UI."""
    manifest = get_addon_info(terminal).get("manifest") or {}
    return bool((manifest.get("capabilities") or {}).get(capability))


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


def list_terminal_users(terminal: DeviceTerminal) -> dict[str, Any]:
    if not supports_capability(terminal, "terminal_users"):
        raise TerminalOperationError("El driver configurado no admite leer usuarios de la terminal")
    driver = get_driver_instance(terminal)
    try:
        driver.connect(get_connection_params(terminal))
        users = driver.get_terminal_users()
        privilege_labels = (get_addon_info(terminal).get("manifest") or {}).get("terminal_user_privileges") or {}
        return {
            "users": [
                {
                    "uid": item["uid"],
                    "user_id": item["user_id"],
                    "name": item["name"],
                    "privilege": item["privilege"],
                    "privilege_label": privilege_labels.get(
                        str(item["privilege"]), f"Privilegio de terminal ({item['privilege']})"
                    ),
                }
                for item in users
            ],
            "name_max_bytes": driver.get_terminal_user_name_max_bytes(),
        }
    finally:
        _disconnect_safely(driver)


def sync_terminal_user_names(terminal: DeviceTerminal, session) -> dict[str, Any]:
    """Sube sólo nombres SRTime a usuarios ya existentes en la terminal.

    UID, user_id y privilegios del reloj son fuente de verdad del equipo y se
    preservan. Esta operación no crea ni elimina usuarios biométricos.
    """
    if not supports_capability(terminal, "terminal_user_name_sync"):
        raise TerminalOperationError("El driver configurado no admite sincronizar nombres")
    driver = get_driver_instance(terminal)
    try:
        driver.connect(get_connection_params(terminal))
        terminal_users = driver.get_terminal_users()
        identifiers = {str(item["user_id"]).strip().zfill(15) for item in terminal_users}
        employees = {
            employee.identifier: employee
            for employee in session.query(User).filter(User.identifier.in_(identifiers)).all()
        }
        max_bytes = driver.get_terminal_user_name_max_bytes()
        planned = []
        for terminal_user in terminal_users:
            employee = employees.get(str(terminal_user["user_id"]).strip().zfill(15))
            if not employee:
                continue
            desired_name = " ".join(part for part in (employee.last_name, employee.first_name) if part).strip()
            if not desired_name or desired_name == terminal_user["name"]:
                continue
            if max_bytes and len(desired_name.encode("utf-8")) > max_bytes:
                raise TerminalOperationError(
                    f"El nombre de {employee.identifier} supera el límite de {max_bytes} bytes de la terminal"
                )
            planned.append((terminal_user, desired_name))

        for terminal_user, desired_name in planned:
            driver.update_terminal_user_name(terminal_user, desired_name)
        return {
            "terminal_users": len(terminal_users),
            "updated": len(planned),
            "matched": len(employees),
            "name_max_bytes": max_bytes,
        }
    finally:
        _disconnect_safely(driver)
