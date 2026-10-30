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
