"""Formato único de mensajes de la app Desktop (paridad con web/app/utils/messages.ts).

- Tipo: info | success | warning | error. El ícono indica el tipo; el título no dice "Error".
- Título: la acción o sección, en minúscula salvo la inicial ("Probar conexión", "Eliminar turno").
- Texto: una o dos oraciones terminadas en punto, sin emojis.
- Detalles: líneas opcionales "Etiqueta: valor" o el detalle técnico (excepción).
- Confirmación: botón con el verbo de la acción ("Eliminar") y "Cancelar"; en acciones
  destructivas el botón por defecto es "Cancelar".
"""
from __future__ import annotations

from typing import Iterable

from PySide6.QtWidgets import QMessageBox, QWidget

_ICONS = {
    "info": QMessageBox.Icon.Information,
    "success": QMessageBox.Icon.Information,
    "warning": QMessageBox.Icon.Warning,
    "error": QMessageBox.Icon.Critical,
}


def _details_text(details: Iterable[object] | str | BaseException | None) -> str:
    if details is None:
        return ""
    if isinstance(details, (str, BaseException)):
        return str(details).strip()
    return "\n".join(str(line) for line in details if str(line).strip())


def _exec(box: QMessageBox) -> None:
    """Punto único de ejecución modal (los tests lo reemplazan para no bloquear)."""
    box.exec()


def _build(parent: QWidget | None, kind: str, title: str, text: str, details=None) -> QMessageBox:
    box = QMessageBox(parent)
    box.setIcon(_ICONS[kind])
    box.setWindowTitle(title)
    box.setText(text)
    extra = _details_text(details)
    if extra:
        box.setInformativeText(extra)
    return box


def show_message(parent: QWidget | None, kind: str, title: str, text: str, details=None) -> None:
    box = _build(parent, kind, title, text, details)
    box.addButton("Aceptar", QMessageBox.ButtonRole.AcceptRole)
    _exec(box)


def show_info(parent, title: str, text: str, details=None) -> None:
    show_message(parent, "info", title, text, details)


def show_success(parent, title: str, text: str, details=None) -> None:
    show_message(parent, "success", title, text, details)


def show_warning(parent, title: str, text: str, details=None) -> None:
    show_message(parent, "warning", title, text, details)


def show_error(parent, title: str, text: str, details=None) -> None:
    show_message(parent, "error", title, text, details)


def ask_confirm(parent, title: str, text: str, confirm_label: str = "Aceptar", danger: bool = False) -> bool:
    """True sólo si se elige la acción."""
    box = _build(parent, "warning" if danger else "info", title, text)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    accept = box.addButton(confirm_label, QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel if danger else accept)
    box.setEscapeButton(cancel)
    _exec(box)
    return box.clickedButton() is accept
