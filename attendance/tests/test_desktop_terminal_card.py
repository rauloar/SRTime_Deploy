"""La ficha Desktop de terminal muestra sólo lo que el driver declara en su manifest."""
import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from models.terminal import DeviceTerminal  # noqa: E402


@pytest.fixture
def sundial_and_zkteco(monkeypatch):
    """Perfil propio: no depender de SRTIME_ENABLED_ADDONS del config\\.env local."""
    import services.addons

    monkeypatch.setenv("SRTIME_ENABLED_ADDONS", "sundial,zkteco")
    services.addons.clear_addon_cache()
    yield
    services.addons.clear_addon_cache()


def test_terminal_card_follows_driver_capabilities(test_db, sundial_and_zkteco):
    QApplication.instance() or QApplication([])
    from ui.tabs.terminals_tab import TerminalsTab

    zk = DeviceTerminal(name="ZK", driver_name="ZKTeco", ip="127.0.0.1", port=4370)
    sundial = DeviceTerminal(
        name="Sundial", driver_name="Sundial ERTeckno", ip="127.0.0.1", port=3000,
        connection_params={"ip": "127.0.0.1", "port": "3000", "address": "1"},
    )
    test_db.add_all([zk, sundial])
    test_db.commit()
    tab = TerminalsTab(test_db)

    tab._show_terminal_detail(zk)
    assert not tab.btn_list_users.isHidden()
    assert not tab.btn_sync_profiles.isHidden()
    assert tab.btn_pointer.isHidden()

    tab._show_terminal_detail(sundial)
    assert tab.btn_list_users.isHidden()
    assert tab.btn_sync_profiles.isHidden()
    assert not tab.btn_pointer.isHidden()


def test_desktop_hides_terminal_sections_without_terminal_addons(test_db, monkeypatch):
    """Paridad con la Web: sin driver habilitado no hay pestaña Terminales ni descarga por red."""
    QApplication.instance() or QApplication([])
    import services.addons
    from core.database import Base
    from ui.main_window import MainWindow

    monkeypatch.setattr(services.addons, "enabled_ui_features", lambda: {
        "file_import": True, "network_import": False, "terminal_management": False,
    })
    Base.metadata.create_all(test_db.get_bind())
    window = MainWindow({"id": 1, "username": "admin", "role": "root"})
    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]

    assert window.tabs.isTabVisible(titles.index("Terminales")) is False
    import_tab = window.tabs.widget(titles.index("Importar"))
    assert import_tab.tabs.isTabVisible(0) is True
    assert import_tab.tabs.isTabVisible(1) is False


@pytest.fixture
def sundial_only(monkeypatch):
    import services.addons

    monkeypatch.setenv("SRTIME_ENABLED_ADDONS", "sundial")
    services.addons.clear_addon_cache()
    yield
    services.addons.clear_addon_cache()


def test_terminals_of_disabled_addons_are_not_listed(test_db, sundial_only):
    """Una terminal ZKTeco guardada no aparece si el addon zkteco no está habilitado."""
    QApplication.instance() or QApplication([])
    from services.terminals import with_enabled_driver
    from ui.tabs.terminals_tab import TerminalsTab

    test_db.add_all([
        DeviceTerminal(name="Main", driver_name="ZKTeco", ip="192.168.1.201", port=4370),
        DeviceTerminal(name="Sundial", driver_name="Sundial ERTeckno", ip="192.168.1.110", port=3000),
    ])
    test_db.commit()

    listed = with_enabled_driver(test_db.query(DeviceTerminal)).all()
    assert [t.name for t in listed] == ["Sundial"]
    # Sigue guardada: vuelve a verse al habilitar el addon.
    assert test_db.query(DeviceTerminal).count() == 2

    tab = TerminalsTab(test_db)
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 1).text() == "Sundial"


def test_scheduler_skips_terminals_of_disabled_addons(test_db, sundial_only, monkeypatch):
    from datetime import datetime

    import services.terminal_scheduler as scheduler

    zk = DeviceTerminal(
        name="Main", driver_name="ZKTeco", ip="192.168.1.201", port=4370,
        pull_schedule_enabled=True, next_pull_at=datetime(2000, 1, 1),
    )
    test_db.add(zk)
    test_db.commit()
    monkeypatch.setattr(scheduler, "is_database_configured", lambda: True)
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: test_db)
    monkeypatch.setattr(test_db, "close", lambda: None)

    def unexpected_pull(*_args, **_kwargs):
        raise AssertionError("no debe descargar de una terminal sin addon habilitado")

    monkeypatch.setattr(scheduler, "run_pull", unexpected_pull)

    assert scheduler.run_due_pulls() == 0
    assert test_db.get(DeviceTerminal, zk.id).last_pull_status is None


def test_terminal_card_has_the_web_actions(test_db, sundial_and_zkteco):
    """Mismas acciones y nombres que la tarjeta Web; borrar memoria sólo si el driver lo declara."""
    QApplication.instance() or QApplication([])
    from ui.tabs.terminals_tab import TerminalsTab

    zk = DeviceTerminal(name="ZK", driver_name="ZKTeco", ip="127.0.0.1", port=4370)
    sundial = DeviceTerminal(name="Sundial", driver_name="Sundial ERTeckno", ip="127.0.0.1", port=3000)
    test_db.add_all([zk, sundial])
    test_db.commit()
    tab = TerminalsTab(test_db)

    labels = [tab.btn_pull.text(), tab.btn_schedule.text(), tab.btn_list_users.text(), tab.btn_sync_profiles.text()]
    assert labels == ["Bajar registros", "Programar", "Bajar usuarios", "Subir usuarios"]
    row_buttons = [b.text() for b in tab.table.cellWidget(0, 6).findChildren(type(tab.btn_pull))]
    assert row_buttons == ["Conectar", "Reloj"]

    tab._show_terminal_detail(zk)
    assert not tab.clear_memory_check.isHidden()
    tab._show_terminal_detail(sundial)
    assert tab.clear_memory_check.isHidden()


def test_terminal_card_shows_schedule_and_last_warning(test_db, sundial_and_zkteco):
    from datetime import datetime, time

    QApplication.instance() or QApplication([])
    from ui.tabs.terminals_tab import TerminalsTab

    terminal = DeviceTerminal(
        name="Sundial", driver_name="Sundial ERTeckno", ip="127.0.0.1", port=3000,
        pull_schedule_enabled=True, pull_schedule_mode="weekly", pull_schedule_weekdays=[0, 2],
        pull_schedule_time=time(7, 30), next_pull_at=datetime(2026, 11, 4, 7, 30),
        last_pull_status="warning", last_pull_error="Llegaron marcas desde el 01/01/2011",
    )
    test_db.add(terminal)
    test_db.commit()
    tab = TerminalsTab(test_db)
    tab._show_terminal_detail(terminal)

    text = tab.detail_label.toPlainText()
    assert "Estado automático: Lun, Mié · 07:30" in text
    assert "Próxima descarga: 04/11/2026 07:30" in text
    assert "Último aviso: Llegaron marcas desde el 01/01/2011" in text


def test_schedule_dialog_values_match_the_web_request(test_db):
    from datetime import time

    QApplication.instance() or QApplication([])
    from services.terminal_scheduler import apply_pull_schedule
    from ui.tabs.terminals_tab import ScheduleDialog

    terminal = DeviceTerminal(name="T", driver_name="ZKTeco")
    dialog = ScheduleDialog(None, terminal)
    dialog.enabled.setChecked(True)
    dialog.mode.setCurrentIndex(1)  # Días definidos
    dialog.days[0].setChecked(True)
    dialog.days[4].setChecked(True)
    values = dialog.values()

    assert values["mode"] == "weekly" and values["weekdays"] == [0, 4]
    assert values["interval_minutes"] is None and values["window_start"] is None
    apply_pull_schedule(terminal, **values)
    assert terminal.pull_schedule_weekdays == [0, 4]
    assert terminal.pull_schedule_time == time(7, 0)
    assert terminal.next_pull_at is not None


def test_desktop_pull_uses_shared_service_and_reports_warnings(test_db, sundial_and_zkteco, monkeypatch):
    QApplication.instance() or QApplication([])
    import services.terminals as terminal_service
    import ui.tabs.terminals_tab as terminals_tab
    from services.importer_service import ImportResult
    from ui.tabs.terminals_tab import TerminalsTab

    terminal = DeviceTerminal(name="ZK", driver_name="ZKTeco", ip="127.0.0.1", port=4370)
    test_db.add(terminal)
    test_db.commit()
    calls, shown = [], []

    def fake_run_pull(t, session, progress=None, clear_device_memory=False):
        calls.append((t.id, clear_device_memory))
        result = ImportResult((4, 1, 5, []))
        result.warnings.append("Aviso de prueba")
        return result

    monkeypatch.setattr(terminal_service, "run_pull", fake_run_pull)
    monkeypatch.setattr(terminals_tab, "show_warning", lambda *args: shown.append(args))
    tab = TerminalsTab(test_db)
    tab._show_terminal_detail(terminal)
    tab.clear_memory_check.setChecked(True)

    tab.pull_selected_terminal()
    worker = tab.pull_worker
    worker.wait(5000)
    QApplication.processEvents()

    assert calls == [(terminal.id, True)]
    assert tab.pull_worker is None and tab.btn_pull.text() == "Bajar registros"
    assert shown and shown[0][2] == "Descarga finalizada con avisos."
    assert "Aviso de prueba" in shown[0][3]
