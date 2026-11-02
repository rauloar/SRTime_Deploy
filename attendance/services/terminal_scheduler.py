"""Scheduler liviano para descargas raw de terminales.

Comparte ``services.terminals.run_pull`` con la descarga manual de la Web y del
Desktop: nunca interpreta ni persiste movimientos por su cuenta. Corre en la
Web y en el Desktop; con PostgreSQL compartido sólo una instancia descarga a la
vez (``services.locks``).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from threading import Event, Thread
from typing import Optional

from core.database import SessionLocal
from core.logging_config import get_logger
from core.timezone import local_now
from models.terminal import DeviceTerminal
from services.setup_service import is_database_configured
from services.locks import try_exclusive
from services.terminals import TerminalBusy, run_pull, with_enabled_driver

SCHEDULER_LOCK = "srtime-terminal-scheduler"

logger = get_logger(__name__)
_stop_event = Event()
_thread: Optional[Thread] = None


def schedule_next_pull(terminal: DeviceTerminal, now: datetime | None = None) -> None:
    now = now or local_now().replace(tzinfo=None)
    if terminal.pull_schedule_mode == "weekly":
        weekdays = {int(day) for day in (terminal.pull_schedule_weekdays or []) if 0 <= int(day) <= 6}
        run_time = terminal.pull_schedule_time
        if not weekdays or not run_time:
            terminal.next_pull_at = None
            return
        first_date = max(now.date(), terminal.pull_schedule_start_date or now.date())
        for offset in range(8):
            candidate_date = first_date + timedelta(days=offset)
            if terminal.pull_schedule_end_date and candidate_date > terminal.pull_schedule_end_date:
                terminal.next_pull_at = None
                return
            candidate = datetime.combine(candidate_date, run_time)
            if candidate.weekday() in weekdays and candidate > now:
                terminal.next_pull_at = candidate
                return
        terminal.next_pull_at = None
        return
    interval = terminal.pull_interval_minutes or 60
    terminal.next_pull_at = now + timedelta(minutes=max(1, interval))


def _inside_window(terminal: DeviceTerminal, now: datetime) -> bool:
    start, end = terminal.pull_window_start, terminal.pull_window_end
    if not start or not end:
        return True
    current = now.time()
    if start <= end:
        return start <= current <= end
    # Ventana que cruza medianoche: se conserva para futuros turnos nocturnos.
    return current >= start or current <= end


def run_due_pulls() -> int:
    """Ejecuta como máximo una descarga por terminal vencida y devuelve cantidad.

    Una sola instancia por base: si la Web y uno o más Desktop comparten
    PostgreSQL, el primero que toma el lock descarga y los demás esperan a la
    vuelta siguiente (en SQLite el Desktop es el único proceso).
    """
    # Antes del asistente de primer uso no hay base: no hay terminales que
    # revisar y conectar sólo llenaría el log de errores. El wizard actualiza el
    # entorno del proceso, así que el scheduler arranca solo al terminarlo.
    if not is_database_configured():
        return 0
    db = SessionLocal()
    completed = 0
    try:
        with try_exclusive(db.get_bind(), SCHEDULER_LOCK) as acquired:
            if not acquired:
                return 0
            now = local_now().replace(tzinfo=None)
            due = (
                with_enabled_driver(db.query(DeviceTerminal))
                .filter(
                    DeviceTerminal.is_active.is_(True),
                    DeviceTerminal.pull_schedule_enabled.is_(True),
                    DeviceTerminal.next_pull_at.isnot(None),
                    DeviceTerminal.next_pull_at <= now,
                )
                .order_by(DeviceTerminal.next_pull_at)
                .all()
            )
            for terminal in due:
                terminal_id = terminal.id
                # Siempre avanza la próxima ejecución: una terminal fuera de franja
                # o caída no debe generar un loop de conexiones por segundo.
                schedule_next_pull(terminal, now)
                if not _inside_window(terminal, now):
                    terminal.last_pull_status = "skipped"
                    db.commit()
                    continue
                try:
                    nuevos, duplicados, total, _ = run_pull(terminal, db)
                    completed += 1
                    logger.info(
                        "Scheduled terminal pull complete",
                        extra={"action": "terminal_pull_scheduled", "detail": f"{terminal_id}: {nuevos}/{duplicados}/{total}"},
                    )
                except TerminalBusy:
                    # Una descarga manual de la misma terminal está en curso.
                    db.rollback()
                    _keep_next_pull(db, terminal_id, now)
                    logger.info("Scheduled terminal pull skipped: terminal busy", extra={"action": "terminal_pull_scheduled_busy"})
                except Exception as exc:  # La siguiente terminal debe poder ejecutarse.
                    # run_pull ya dejó el error en la terminal.
                    _keep_next_pull(db, terminal_id, now)
                    logger.warning("Scheduled terminal pull failed: %s", exc, extra={"action": "terminal_pull_scheduled_error"})
    finally:
        db.close()
    return completed


def _keep_next_pull(db, terminal_id: int, now: datetime) -> None:
    terminal = db.get(DeviceTerminal, terminal_id)
    if terminal:
        schedule_next_pull(terminal, now)
        db.commit()


class ScheduleError(ValueError):
    """Programación inválida; el texto es para mostrarlo tal cual."""


def apply_pull_schedule(
    terminal: DeviceTerminal,
    *,
    enabled: bool,
    mode: str = "interval",
    interval_minutes: int | None = None,
    weekdays: list[int] | None = None,
    scheduled_time: time | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    window_start: time | None = None,
    window_end: time | None = None,
    now: datetime | None = None,
) -> None:
    """Valida y aplica la descarga automática de una terminal (Web y Desktop). No confirma."""
    if mode not in ("interval", "weekly"):
        raise ScheduleError("Modo de descarga automática desconocido")
    if enabled and mode == "interval" and (interval_minutes is None or interval_minutes < 1):
        raise ScheduleError("El intervalo debe ser de al menos un minuto")
    if enabled and mode == "weekly":
        if not weekdays or any(day < 0 or day > 6 for day in weekdays):
            raise ScheduleError("Seleccione al menos un día válido de la semana")
        if scheduled_time is None:
            raise ScheduleError("Indique la hora de descarga automática")
    if start_date and end_date and end_date < start_date:
        raise ScheduleError("La fecha final no puede ser anterior a la fecha inicial")
    if (window_start is None) != (window_end is None):
        raise ScheduleError("Indique inicio y fin de franja, o deje ambos vacíos")
    terminal.pull_schedule_enabled = enabled
    terminal.pull_schedule_mode = mode if enabled else "interval"
    terminal.pull_interval_minutes = interval_minutes if enabled and mode == "interval" else None
    terminal.pull_schedule_weekdays = sorted(set(weekdays or [])) if enabled and mode == "weekly" else None
    terminal.pull_schedule_time = scheduled_time if enabled and mode == "weekly" else None
    terminal.pull_schedule_start_date = start_date if enabled else None
    terminal.pull_schedule_end_date = end_date if enabled else None
    terminal.pull_window_start = window_start if enabled else None
    terminal.pull_window_end = window_end if enabled else None
    if enabled:
        schedule_next_pull(terminal, now)
    else:
        terminal.next_pull_at = None
        terminal.last_pull_status = None
        terminal.last_pull_error = None


def schedule_state(terminal: DeviceTerminal) -> dict:
    """Programación y resultado de la última descarga, igual para Web y Desktop."""
    return {
        "enabled": bool(terminal.pull_schedule_enabled),
        "mode": terminal.pull_schedule_mode or "interval",
        "interval_minutes": terminal.pull_interval_minutes,
        "weekdays": terminal.pull_schedule_weekdays or [],
        "scheduled_time": terminal.pull_schedule_time.isoformat() if terminal.pull_schedule_time else None,
        "start_date": terminal.pull_schedule_start_date.isoformat() if terminal.pull_schedule_start_date else None,
        "end_date": terminal.pull_schedule_end_date.isoformat() if terminal.pull_schedule_end_date else None,
        "window_start": terminal.pull_window_start.isoformat() if terminal.pull_window_start else None,
        "window_end": terminal.pull_window_end.isoformat() if terminal.pull_window_end else None,
        "next_pull_at": str(terminal.next_pull_at) if terminal.next_pull_at else None,
        "last_status": terminal.last_pull_status,
        "last_error": terminal.last_pull_error,
    }


def _loop() -> None:
    while not _stop_event.wait(30):
        try:
            run_due_pulls()
        except Exception:
            logger.exception("Terminal scheduler loop failed", extra={"action": "terminal_scheduler_error"})


def start_scheduler() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = Thread(target=_loop, name="srtime-terminal-scheduler", daemon=True)
    _thread.start()
    logger.info("Terminal raw-log scheduler started", extra={"action": "terminal_scheduler_start"})


def stop_scheduler() -> None:
    _stop_event.set()
    if _thread:
        _thread.join(timeout=5)
    logger.info("Terminal raw-log scheduler stopped", extra={"action": "terminal_scheduler_stop"})


def is_scheduler_running() -> bool:
    """Public status check for operational monitoring without exposing the thread."""
    return bool(_thread and _thread.is_alive())
