"""Scheduler liviano para descargas raw de terminales.

Comparte ``services.terminals.pull_logs`` con la descarga manual: nunca
interpreta ni persiste movimientos por su cuenta.  Está pensado para una sola
instancia FastAPI; un despliegue multi-worker debe ejecutar un worker scheduler
dedicado para no competir por los mismos equipos.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from threading import Event, Lock, Thread
from typing import Optional

from core.database import SessionLocal
from core.logging_config import get_logger
from models.terminal import DeviceTerminal
from services.terminals import pull_logs

logger = get_logger(__name__)
_stop_event = Event()
_thread: Optional[Thread] = None
_run_lock = Lock()


def schedule_next_pull(terminal: DeviceTerminal, now: datetime | None = None) -> None:
    now = now or datetime.now()
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
    """Ejecuta como máximo una descarga por terminal vencida y devuelve cantidad."""
    if not _run_lock.acquire(blocking=False):
        return 0
    db = SessionLocal()
    completed = 0
    try:
        now = datetime.now()
        due = (
            db.query(DeviceTerminal)
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
            # Siempre avanza la próxima ejecución: una terminal fuera de franja
            # o caída no debe generar un loop de conexiones por segundo.
            schedule_next_pull(terminal, now)
            if not _inside_window(terminal, now):
                terminal.last_pull_status = "skipped"
                db.commit()
                continue
            try:
                nuevos, duplicados, total, _ = pull_logs(terminal, db)
                terminal.last_pull_status = "ok"
                terminal.last_pull_error = None
                db.commit()
                completed += 1
                logger.info(
                    "Scheduled terminal pull complete",
                    extra={"action": "terminal_pull_scheduled", "detail": f"{terminal.id}: {nuevos}/{duplicados}/{total}"},
                )
            except Exception as exc:  # La siguiente terminal debe poder ejecutarse.
                db.rollback()
                terminal = db.get(DeviceTerminal, terminal.id)
                if terminal:
                    schedule_next_pull(terminal, now)
                    terminal.last_pull_status = "error"
                    terminal.last_pull_error = str(exc)[:500]
                    db.commit()
                logger.warning("Scheduled terminal pull failed: %s", exc, extra={"action": "terminal_pull_scheduled_error"})
    finally:
        db.close()
        _run_lock.release()
    return completed


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
