"""ui.ini sólo oculta pestañas opcionales de SRTime_Win; las funciones siguen intactas."""
import os

import pytest

from core.ui_settings import FIXED_TABS, load_hidden_tabs, resolve_ui_settings_path


def write_ini(tmp_path, body, encoding="utf-8"):
    path = tmp_path / "ui.ini"
    path.write_text(body, encoding=encoding)
    return path


def test_missing_file_hides_nothing(tmp_path):
    assert load_hidden_tabs(tmp_path / "ui.ini") == frozenset()


def test_optional_tabs_can_be_hidden(tmp_path):
    path = write_ini(tmp_path, "[pestanas]\ndashboard = false\nTerminales = no\nreportes = true\n")
    assert load_hidden_tabs(path) == {"dashboard", "terminales"}


def test_fixed_tabs_cannot_be_hidden(tmp_path):
    body = "[pestanas]\n" + "".join(f"{key} = false\n" for key in FIXED_TABS)
    assert load_hidden_tabs(write_ini(tmp_path, body)) == frozenset()


def test_invalid_and_unknown_entries_stay_visible(tmp_path):
    path = write_ini(tmp_path, "[pestanas]\nferiados = quizas\ninexistente = false\nausencias = 0\n")
    assert load_hidden_tabs(path) == {"ausencias"}


def test_malformed_file_hides_nothing(tmp_path):
    path = write_ini(tmp_path, "esto no es un ini\ndashboard = false\n")
    assert load_hidden_tabs(path) == frozenset()


def test_notepad_bom_is_accepted(tmp_path):
    path = write_ini(tmp_path, "[pestanas]\nferiados = false\n", encoding="utf-8-sig")
    assert load_hidden_tabs(path) == {"feriados"}


def test_ui_ini_lives_beside_active_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SRTIME_ENV_FILE", str(tmp_path / ".env"))
    assert resolve_ui_settings_path() == tmp_path / "ui.ini"


def test_main_window_hides_tabs_without_shifting_indices(test_db, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("SRTIME_ENV_FILE", str(tmp_path / ".env"))
    write_ini(tmp_path, "[pestanas]\ndashboard = false\nterminales = false\nimportar = false\n")
    from ui.main_window import MainWindow

    window = MainWindow({"id": 1, "username": "admin", "role": "root"})
    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    hidden = [title for i, title in enumerate(titles) if not window.tabs.isTabVisible(i)]

    # Las once pestañas existen en el orden de siempre; sólo dos quedan ocultas.
    assert titles == [
        "Dashboard", "Importar", "Terminales", "Empleados", "Turnos Horarios",
        "Movimientos", "Movimientos Procesados", "Ausencias", "Feriados",
        "Reportes", "Usuarios Autorizados",
    ]
    assert hidden == ["Dashboard", "Terminales"]
    assert window.tabs.currentIndex() == titles.index("Importar")
    app.processEvents()
    window.close()
