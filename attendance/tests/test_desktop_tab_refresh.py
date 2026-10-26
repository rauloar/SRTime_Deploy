"""Desktop tabs must show employees created by a TXT import, like the Web does."""
import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.database import Base  # noqa: E402
from models.employee import User  # noqa: E402
from services.addons.sundial.parser import SundialParser  # noqa: E402
from services.importer_service import import_att_logs  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "tm_mr001_mock.txt"


def test_employees_tab_reloads_after_txt_import(test_db):
    app = QApplication.instance() or QApplication([])
    Base.metadata.create_all(test_db.get_bind())
    from ui.main_window import MainWindow

    window = MainWindow({"id": 1, "username": "admin", "role": "root"})
    window.session = test_db
    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    users_index = titles.index("Empleados")
    users_tab = window.tabs.widget(users_index)
    import_tab = window.tabs.widget(titles.index("Importar"))
    users_tab.session = import_tab.session = test_db

    window.tabs.setCurrentIndex(users_index)
    app.processEvents()
    assert users_tab.table.rowCount() == 0

    window.tabs.setCurrentIndex(titles.index("Importar"))
    import_att_logs(str(FIXTURE), test_db, None, SundialParser())
    import_tab.data_changed.emit()

    window.tabs.setCurrentIndex(users_index)
    app.processEvents()
    assert users_tab.table.rowCount() == test_db.query(User).count() > 0
    window.close()
