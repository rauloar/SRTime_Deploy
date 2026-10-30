"""La ficha Desktop de terminal muestra sólo lo que el driver declara en su manifest."""
import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from models.terminal import DeviceTerminal  # noqa: E402


def test_terminal_card_follows_driver_capabilities(test_db):
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
