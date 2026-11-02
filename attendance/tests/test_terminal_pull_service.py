"""Descarga y programación compartidas por Web, Desktop y programador (SQLite y PostgreSQL)."""
from datetime import date, datetime, time

import pytest

import services.terminal_scheduler as scheduler
import services.terminals as terminals
from models.terminal import DeviceTerminal
from services.importer_service import ImportResult
from services.locks import try_exclusive


def _terminal(session, **fields):
    terminal = DeviceTerminal(name="Recepción", driver_name="Sundial ERTeckno", ip="192.0.2.10", port=3000, **fields)
    session.add(terminal)
    session.commit()
    return terminal


def test_run_pull_records_ok(test_db, monkeypatch):
    terminal = _terminal(test_db)
    monkeypatch.setattr(terminals, "pull_logs", lambda *a, **k: ImportResult((2, 1, 3, [])))

    assert terminals.run_pull(terminal, test_db)[:3] == (2, 1, 3)
    test_db.expire_all()
    assert test_db.get(DeviceTerminal, terminal.id).last_pull_status == "ok"


def test_run_pull_records_warning(test_db, monkeypatch):
    terminal = _terminal(test_db)

    def with_warning(*_a, **_k):
        result = ImportResult((1, 0, 1, []))
        result.warnings.append("Llegaron marcas viejas")
        return result

    monkeypatch.setattr(terminals, "pull_logs", with_warning)
    terminals.run_pull(terminal, test_db)
    test_db.expire_all()
    stored = test_db.get(DeviceTerminal, terminal.id)
    assert (stored.last_pull_status, stored.last_pull_error) == ("warning", "Llegaron marcas viejas")


def test_run_pull_records_error_and_raises(test_db, monkeypatch):
    terminal = _terminal(test_db)

    def broken(*_a, **_k):
        raise RuntimeError("sin red")

    monkeypatch.setattr(terminals, "pull_logs", broken)
    with pytest.raises(RuntimeError, match="sin red"):
        terminals.run_pull(terminal, test_db)
    test_db.expire_all()
    stored = test_db.get(DeviceTerminal, terminal.id)
    assert (stored.last_pull_status, stored.last_pull_error) == ("error", "sin red")


def test_second_pull_of_the_same_terminal_is_refused(test_db, monkeypatch):
    """Web, Desktop y programador no descargan la misma terminal a la vez."""
    terminal = _terminal(test_db)
    nested = {}

    def pull_while_another_starts(*_a, **_k):
        with pytest.raises(terminals.TerminalBusy, match="ya se está descargando") as info:
            terminals.run_pull(terminal, test_db)
        nested["error"] = info.value
        return ImportResult((0, 0, 0, []))

    monkeypatch.setattr(terminals, "pull_logs", pull_while_another_starts)
    terminals.run_pull(terminal, test_db)
    assert "error" in nested
    # Terminada la primera, se puede volver a descargar.
    monkeypatch.setattr(terminals, "pull_logs", lambda *a, **k: ImportResult((0, 0, 0, [])))
    terminals.run_pull(terminal, test_db)


def test_scheduler_runs_once_per_database(test_db, monkeypatch):
    _terminal(test_db, pull_schedule_enabled=True, next_pull_at=datetime(2000, 1, 1))
    monkeypatch.setattr(scheduler, "is_database_configured", lambda: True)
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: test_db)
    monkeypatch.setattr(test_db, "close", lambda: None)
    pulls = []
    monkeypatch.setattr(scheduler, "run_pull", lambda terminal, db: pulls.append(terminal.id) or ImportResult((0, 0, 0, [])))

    # Otra instancia (Web u otro Desktop) ya está corriendo el programador.
    with try_exclusive(test_db.get_bind(), scheduler.SCHEDULER_LOCK) as acquired:
        assert acquired
        assert scheduler.run_due_pulls() == 0
    assert pulls == []

    assert scheduler.run_due_pulls() == 1
    assert len(pulls) == 1


@pytest.mark.parametrize("fields, message", [
    ({"mode": "interval", "interval_minutes": 0}, "al menos un minuto"),
    ({"mode": "weekly", "weekdays": [], "scheduled_time": time(8)}, "al menos un día"),
    ({"mode": "weekly", "weekdays": [0], "scheduled_time": None}, "hora de descarga"),
    ({"mode": "interval", "interval_minutes": 30, "start_date": date(2026, 2, 1), "end_date": date(2026, 1, 1)}, "fecha final"),
    ({"mode": "interval", "interval_minutes": 30, "window_start": time(8)}, "inicio y fin de franja"),
])
def test_invalid_schedule_is_rejected(fields, message):
    terminal = DeviceTerminal(name="T", driver_name="ZKTeco")
    with pytest.raises(scheduler.ScheduleError, match=message):
        scheduler.apply_pull_schedule(terminal, enabled=True, **fields)


def test_schedule_is_applied_and_cleared():
    terminal = DeviceTerminal(name="T", driver_name="ZKTeco", last_pull_status="error", last_pull_error="x")
    now = datetime(2026, 11, 2, 10, 0)
    scheduler.apply_pull_schedule(terminal, enabled=True, mode="interval", interval_minutes=30, now=now)
    assert terminal.next_pull_at == datetime(2026, 11, 2, 10, 30)
    assert scheduler.schedule_state(terminal)["interval_minutes"] == 30

    scheduler.apply_pull_schedule(terminal, enabled=False)
    state = scheduler.schedule_state(terminal)
    assert (state["enabled"], state["next_pull_at"], state["last_status"]) == (False, None, None)
