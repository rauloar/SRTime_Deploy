"""Formato único de mensajes Desktop (ui/messages.py), paridad con la Web."""
import os
import pathlib
import re

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import ui.messages as messages  # noqa: E402

ATTENDANCE = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def captured(monkeypatch):
    QApplication.instance() or QApplication([])
    boxes = []

    def fake_exec(box):
        boxes.append(box)
        click = getattr(fake_exec, "click", None)
        if click:
            button = next(b for b in box.buttons() if b.text() == click)
            button.click()

    monkeypatch.setattr(messages, "_exec", fake_exec)
    return fake_exec, boxes


def test_message_uses_title_text_details_and_icon(captured):
    _, boxes = captured
    messages.show_error(None, "Probar conexión", "No se pudo conectar con la terminal.", TimeoutError("timed out"))
    box = boxes[0]
    assert box.windowTitle() == "Probar conexión"
    assert box.text() == "No se pudo conectar con la terminal."
    assert box.informativeText() == "timed out"
    assert box.icon() == QMessageBox.Icon.Critical
    assert [b.text() for b in box.buttons()] == ["Aceptar"]


def test_details_list_is_one_line_each(captured):
    _, boxes = captured
    messages.show_success(None, "Bajar registros", "Descarga finalizada.", ["Nuevos: 2", "", "Duplicados: 0"])
    assert boxes[0].informativeText() == "Nuevos: 2\nDuplicados: 0"


def test_confirm_returns_true_only_for_the_action(captured):
    fake_exec, boxes = captured
    fake_exec.click = "Eliminar"
    assert messages.ask_confirm(None, "Eliminar turno", "¿Eliminar el turno 'Mañana'?", "Eliminar", danger=True)
    fake_exec.click = "Cancelar"
    assert not messages.ask_confirm(None, "Eliminar turno", "¿Eliminar el turno 'Mañana'?", "Eliminar", danger=True)
    # En acciones destructivas el botón por defecto es Cancelar.
    assert boxes[-1].defaultButton().text() == "Cancelar"


def test_no_direct_message_boxes_left_in_tabs():
    """Todas las pestañas Desktop pasan por ui/messages.py."""
    offenders = []
    for path in (ATTENDANCE / "ui" / "tabs").glob("*.py"):
        if re.search(r"QMessageBox\.(information|warning|critical|question)\(", path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    assert offenders == []


def test_no_browser_dialogs_left_in_web():
    """La Web usa MessageProvider/Notice: sin alert/confirm/prompt nativos ni emojis de estado."""
    offenders = []
    for path in (ATTENDANCE / "web" / "app").rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?<![\w.])(window\.)?(alert|confirm|prompt)\(", text) or "✅" in text or "⚠" in text:
            offenders.append(path.name)
    assert offenders == []
