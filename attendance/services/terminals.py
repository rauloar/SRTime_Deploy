"""Operaciones compartidas de terminales para API y PySide6."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from models.terminal import DeviceTerminal
from models.employee import TERMINAL_PRIVILEGE_ADMIN, TERMINAL_PRIVILEGE_USER, User
from core.credentials import decrypt_credential, encrypt_credential
from core.logging_config import get_logger
from core.timezone import local_now


SECRET_FIELDS = frozenset({"password", "db_password", "token", "api_token", "secret", "api_key"})
logger = get_logger(__name__)


class TerminalOperationError(RuntimeError):
    pass


def get_addon_info(terminal: DeviceTerminal) -> dict[str, Any]:
    import services.addons

    info = services.addons.get_addon_info(terminal.driver_name)
    if not info or not info.get("is_driver") or not info.get("driver_class"):
        raise TerminalOperationError(f"Driver '{terminal.driver_name}' no encontrado")
    return info


def enabled_driver_names() -> list[str]:
    """Drivers de los addons habilitados en esta instalación (SRTIME_ENABLED_ADDONS)."""
    import services.addons

    return [
        name for name, info in services.addons.get_available_addons().items()
        if info.get("is_driver") and info.get("driver_class")
    ]


def with_enabled_driver(query):
    """Limita una consulta de terminales a las que tienen su addon habilitado.

    Las terminales de un addon deshabilitado siguen en la base y vuelven a
    aparecer al habilitarlo; mientras tanto no se listan, no se programan ni
    se ofrecen para descargar.
    """
    return query.filter(DeviceTerminal.driver_name.in_(enabled_driver_names()))


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


def _connection_details(manifest: dict[str, Any], result: dict[str, Any]) -> list[dict[str, str]]:
    """Rotula lo que informó el driver según su manifest (``connection_details``).

    El core no conoce los datos de ningún equipo: cada addon declara qué
    devuelve su ``test_connection`` y con qué etiqueta. Sin declaración se
    muestra lo informado tal cual.
    """
    declared = manifest.get("connection_details") or [
        {"name": key, "label": key} for key in result if key != "status"
    ]
    return [
        {"label": item.get("label") or item["name"], "value": str(result[item["name"]])}
        for item in declared
        if result.get(item["name"]) not in (None, "")
    ]


def test_connection(terminal: DeviceTerminal) -> dict[str, Any]:
    info = get_addon_info(terminal)
    driver = info["driver_class"]()
    try:
        result = dict(driver.test_connection(get_connection_params(terminal)))
    finally:
        _disconnect_safely(driver)
    result["details"] = _connection_details(info.get("manifest") or {}, result)
    return result


def sync_time(terminal: DeviceTerminal) -> bool:
    driver = get_driver_instance(terminal)
    try:
        return bool(driver.sync_time(get_connection_params(terminal)))
    finally:
        _disconnect_safely(driver)


def set_attendance_pointer(terminal: DeviceTerminal, since: date) -> bool:
    """Pide al equipo que vuelva a entregar registros desde ``since``.

    Sólo para drivers que declaran ``attendance_pointer``. No toca la base: la
    próxima descarga trae esos registros y los ya guardados son duplicados.
    """
    if not supports_capability(terminal, "attendance_pointer"):
        raise TerminalOperationError("El driver configurado no admite volver a bajar registros desde una fecha")
    if since > local_now().date():
        raise TerminalOperationError("La fecha no puede ser posterior a hoy")
    driver = get_driver_instance(terminal)
    try:
        return bool(driver.set_attendance_pointer(get_connection_params(terminal), since))
    finally:
        _disconnect_safely(driver)


def _split_terminal_name(name: Any) -> tuple[str | None, str | None]:
    """Convierte el único campo ``name`` de ZKTeco al perfil SRTime.

    ZKTeco no separa nombre y apellido. Se respeta el formato explícito
    ``Apellido, Nombre`` cuando existe; en cualquier otro caso se conserva el
    valor completo como nombre para evitar adivinar una separación incorrecta.
    """
    value = str(name or "").strip()
    if not value:
        return None, None
    if "," in value:
        last_name, first_name = (part.strip() for part in value.split(",", 1))
        return first_name or None, last_name or None
    return value, None


def _seed_terminal_employee_profiles(driver, session) -> dict[str, int]:
    """Completa el directorio SRTime desde una terminal sin pisar su fuente.

    La descarga normal de marcaciones no trae nombres. Si la terminal aporta
    un usuario inexistente se crea su empleado; si el importador había creado
    antes un empleado vacío, se completa una única vez. Los nombres que ya
    existen en SRTime son administrados por la aplicación y nunca se
    sobrescriben durante un pull de logs.
    """
    terminal_users = driver.get_terminal_users()
    identifiers = {
        str(item.get("user_id") or "").strip().zfill(15)
        for item in terminal_users
        if str(item.get("user_id") or "").strip()
    }
    if not identifiers:
        return {"created": 0, "completed": 0, "preserved": 0}

    employees = {
        employee.identifier: employee
        for employee in session.query(User).filter(User.identifier.in_(identifiers)).all()
    }
    created = completed = preserved = 0
    for terminal_user in terminal_users:
        raw_identifier = str(terminal_user.get("user_id") or "").strip()
        if not raw_identifier:
            continue
        identifier = raw_identifier.zfill(15)
        first_name, last_name = _split_terminal_name(terminal_user.get("name"))
        privilege = int(terminal_user.get("privilege", TERMINAL_PRIVILEGE_USER))
        if privilege not in (TERMINAL_PRIVILEGE_USER, TERMINAL_PRIVILEGE_ADMIN):
            privilege = TERMINAL_PRIVILEGE_USER

        employee = employees.get(identifier)
        if employee is None:
            employee = User(
                identifier=identifier,
                first_name=first_name,
                last_name=last_name,
                terminal_privilege=privilege,
            )
            session.add(employee)
            employees[identifier] = employee
            created += 1
        elif not (employee.first_name or employee.last_name):
            employee.first_name = first_name
            employee.last_name = last_name
            # El privilegio de terminal sólo se toma al incorporar/completar
            # el perfil. Luego SRTime es la fuente que se sincroniza hacia ZK.
            employee.terminal_privilege = privilege
            completed += 1
        else:
            preserved += 1
    session.flush()
    return {"created": created, "completed": completed, "preserved": preserved}


def pull_logs(terminal: DeviceTerminal, session, progress_signal=None, clear_device_memory: bool = False):
    from services.importer_service import import_from_driver

    driver = get_driver_instance(terminal)
    profile_result = {"created": 0, "completed": 0, "preserved": 0}
    clear_result = {"cleared": False}

    def on_connected(connected_driver) -> None:
        nonlocal profile_result
        if supports_capability(terminal, "terminal_users"):
            profile_result = _seed_terminal_employee_profiles(connected_driver, session)

    def after_ingested(connected_driver, ingest_result) -> None:
        if not clear_device_memory:
            return
        if not supports_capability(terminal, "clear_attendance_memory"):
            raise TerminalOperationError("El driver no admite borrar la memoria de marcaciones")
        connected_driver.clear_attendance_logs()
        clear_result["cleared"] = True

    result = import_from_driver(
        driver,
        get_connection_params(terminal),
        session,
        progress_signal=progress_signal,
        on_connected=on_connected,
        after_ingested=after_ingested,
    )
    terminal.last_sync = local_now().replace(tzinfo=None)
    session.commit()
    if any(profile_result.values()):
        logger.info("Terminal employee profiles synchronized during pull: %s", profile_result)
    if clear_result["cleared"]:
        logger.warning(
            "Terminal attendance memory cleared after successful pull",
            extra={"action": "terminal_clear_attendance_memory", "terminal_id": terminal.id},
        )
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
            "privilege_options": [
                {"value": TERMINAL_PRIVILEGE_USER, "label": "USER"},
                {"value": TERMINAL_PRIVILEGE_ADMIN, "label": "ADMIN"},
            ],
        }
    finally:
        _disconnect_safely(driver)


def sync_terminal_user_names(terminal: DeviceTerminal, session) -> dict[str, Any]:
    """Sube perfil SRTime a usuarios ya existentes en la terminal.

    UID y user_id siguen siendo identidad del reloj y se preservan. Esta
    operación no crea ni elimina usuarios biométricos. Sundial/TM-MR001 no
    participa de este flujo; allí todos los empleados quedan USER por default.
    """
    if not supports_capability(terminal, "terminal_user_name_sync"):
        raise TerminalOperationError("El driver configurado no admite sincronizar nombres")
    can_sync_privilege = supports_capability(terminal, "terminal_user_privilege_sync")
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
            desired_name = " ".join(part for part in (employee.last_name, employee.first_name) if part).strip() or terminal_user["name"]
            if max_bytes and len(desired_name.encode("utf-8")) > max_bytes:
                raise TerminalOperationError(
                    f"El nombre de {employee.identifier} supera el límite de {max_bytes} bytes de la terminal"
                )
            desired_privilege = int(getattr(employee, "terminal_privilege", TERMINAL_PRIVILEGE_USER) or TERMINAL_PRIVILEGE_USER)
            current_privilege = int(terminal_user.get("privilege", TERMINAL_PRIVILEGE_USER))
            if desired_name != terminal_user["name"] or (can_sync_privilege and desired_privilege != current_privilege):
                planned.append((terminal_user, desired_name, desired_privilege))

        privilege_updates = 0
        for terminal_user, desired_name, desired_privilege in planned:
            previous_privilege = int(terminal_user.get("privilege", TERMINAL_PRIVILEGE_USER))
            if can_sync_privilege:
                driver.update_terminal_user_profile(terminal_user, desired_name, desired_privilege)
                if desired_privilege != previous_privilege:
                    privilege_updates += 1
            else:
                driver.update_terminal_user_name(terminal_user, desired_name)
        return {
            "terminal_users": len(terminal_users),
            "updated": len(planned),
            "privilege_updated": privilege_updates,
            "matched": len(employees),
            "name_max_bytes": max_bytes,
        }
    finally:
        _disconnect_safely(driver)
