"""Pantalla Desktop para importar archivos y descargar terminales.

La UI descubre formatos desde los manifests de addons. La ingesta y el pull
permanecen en servicios compartidos con la versión Web.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QStyle, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)


class ImportWorker(QThread):
    progress = Signal(int, int, int, str)
    finished = Signal(int, int)
    failed = Signal(str)

    def __init__(self, session, *, parser_instance=None, path=None, terminal=None):
        super().__init__()
        self.session = session
        self.parser_instance = parser_instance
        self.path = path
        self.terminal = terminal

    def run(self):
        try:
            if self.terminal is not None:
                # Incluye los perfiles ZKTeco y conserva el mismo contrato Web.
                from services.terminals import pull_logs
                nuevos, duplicados, _total, _logs = pull_logs(
                    self.terminal, self.session, self.progress
                )
            else:
                from services.importer_service import import_att_logs
                nuevos, duplicados, _total, _logs = import_att_logs(
                    self.path, self.session, self.progress, self.parser_instance
                )
            self.finished.emit(nuevos, duplicados)
        except Exception as exc:
            self.failed.emit(str(exc))


class ImportTab(QWidget):
    # Una importación crea empleados y movimientos: las demás pestañas deben
    # volver a consultar la base, igual que la Web al abrir cada vista.
    data_changed = Signal()

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.worker = None
        self.selected_path = str(QSettings("SRTime", "Attendance").value("import/source_file", "") or "")
        import services.addons
        self.addons = services.addons.get_available_parsers()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._build_file_tab(self.style())
        self._build_device_tab()
        # Igual que la Web: cada origen aparece sólo si un addon habilitado lo usa.
        features = services.addons.enabled_ui_features()
        self.tabs.setTabVisible(0, features["file_import"])
        self.tabs.setTabVisible(1, features["network_import"])
        if not features["file_import"] and features["network_import"]:
            self.tabs.setCurrentIndex(1)

        self.status_label = QLabel("Logs: 0 | Nuevos: 0 | Duplicados: 0")
        layout.addWidget(self.status_label)
        self.live_log = QTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setMaximumHeight(120)
        layout.addWidget(self.live_log)
        self.spinner_label = QLabel("Importando...")
        self.spinner_label.setVisible(False)
        layout.addWidget(self.spinner_label)
        self.show_path()

    def _file_addons(self):
        return [
            (name, info) for name, info in self.addons.items()
            if info.get("is_parser") and (info.get("ui_features") or {}).get("file_import")
        ]

    def _build_file_tab(self, style):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.file_parser_selector = QComboBox()
        for name, info in self._file_addons():
            self.file_parser_selector.addItem(name, name)
        layout.addWidget(QLabel("Formato de archivo:"))
        layout.addWidget(self.file_parser_selector)
        self.file_hint_label = QLabel()
        self.file_hint_label.setWordWrap(True)
        layout.addWidget(self.file_hint_label)
        self.file_parser_selector.currentIndexChanged.connect(self._update_file_hint)
        self._update_file_hint()
        self.path_label = QLabel("Archivo: (no seleccionado)")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        self.btn_select = QPushButton("Buscar archivo")
        self.btn_select.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.btn_select.clicked.connect(self.select_file)
        layout.addWidget(self.btn_select)
        self.btn_import = QPushButton("Importar archivo")
        self.btn_import.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.btn_import.clicked.connect(self.import_file)
        layout.addWidget(self.btn_import)
        layout.addStretch()
        self.tabs.addTab(tab, "Desde archivo")

    def _build_device_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.terminal_selector = QComboBox()
        layout.addWidget(QLabel("Equipo registrado:"))
        layout.addWidget(self.terminal_selector)
        self.update_terminal_selector()
        buttons = QHBoxLayout()
        self.btn_test_conn = QPushButton("Probar conexión")
        self.btn_test_conn.clicked.connect(self.test_driver_connection)
        buttons.addWidget(self.btn_test_conn)
        self.btn_sync_time = QPushButton("Sincronizar hora")
        self.btn_sync_time.clicked.connect(self.sync_driver_time)
        buttons.addWidget(self.btn_sync_time)
        layout.addLayout(buttons)
        self.btn_import_driver = QPushButton("Descargar registros")
        self.btn_import_driver.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px; background-color: #2e6b2e; color: white;")
        self.btn_import_driver.clicked.connect(self.import_from_driver_ui)
        layout.addWidget(self.btn_import_driver)
        layout.addStretch()
        self.tabs.addTab(tab, "Desde terminal")

    def _selected_file_addon(self):
        name = self.file_parser_selector.currentData()
        return self.addons.get(name) if name else None

    def _update_file_hint(self):
        addon = self._selected_file_addon() or {}
        self.file_hint_label.setText((addon.get("ui_features") or {}).get("file_format_hint", ""))

    def _file_dialog_filter(self):
        extensions = sorted({
            ext.lower() for _name, info in self._file_addons()
            for ext in (info.get("ui_features") or {}).get("file_extensions", [])
        })
        return f"Archivos de asistencia ({' '.join(f'*{ext}' for ext in extensions)});;Todos los archivos (*.*)"

    def _select_addon_for_path(self, path):
        suffix = Path(path).suffix.lower()
        for index, (_name, info) in enumerate(self._file_addons()):
            allowed = {ext.lower() for ext in (info.get("ui_features") or {}).get("file_extensions", [])}
            if suffix in allowed:
                self.file_parser_selector.setCurrentIndex(index)
                return

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo de asistencia", "", self._file_dialog_filter())
        if path:
            self.selected_path = path
            self._select_addon_for_path(path)
            QSettings("SRTime", "Attendance").setValue("import/source_file", path)
        self.show_path()

    def update_terminal_selector(self):
        self.terminal_selector.clear()
        from models.terminal import DeviceTerminal
        for terminal in self.session.query(DeviceTerminal).filter_by(is_active=True).all():
            self.terminal_selector.addItem(f"{terminal.name} ({terminal.ip})", terminal.id)

    def _selected_terminal(self):
        terminal_id = self.terminal_selector.currentData()
        if not terminal_id:
            QMessageBox.warning(self, "Aviso", "No hay terminal seleccionada.")
            return None
        from models.terminal import DeviceTerminal
        return self.session.get(DeviceTerminal, terminal_id)

    def test_driver_connection(self):
        terminal = self._selected_terminal()
        if terminal is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            from services.terminals import test_connection
            result = test_connection(terminal)
            details = "\n".join(f"{item['label']}: {item['value']}" for item in result.get("details", []))
            QMessageBox.information(self, "Conexión exitosa", details or "Terminal OK.")
        except Exception as exc:
            QMessageBox.critical(self, "Error de conexión", f"No se pudo conectar al dispositivo:\n{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def sync_driver_time(self):
        terminal = self._selected_terminal()
        if terminal is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            from services.terminals import sync_time
            if sync_time(terminal):
                QMessageBox.information(self, "Sincronización exitosa", "Se actualizó la hora del dispositivo.")
            else:
                QMessageBox.warning(self, "Aviso", "El controlador no pudo sincronizar la hora.")
        except Exception as exc:
            QMessageBox.critical(self, "Error al sincronizar", f"Fallo al sincronizar hora:\n{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def import_from_driver_ui(self):
        terminal = self._selected_terminal()
        if terminal is not None:
            self._start_worker(ImportWorker(self.session, terminal=terminal), f"Descargando desde {terminal.name}...")

    def import_file(self):
        if not self.selected_path or not os.path.isfile(self.selected_path):
            QMessageBox.warning(self, "Archivo no encontrado", "Seleccione un archivo existente.")
            self.select_file()
            return
        addon = self._selected_file_addon()
        if not addon or not addon.get("parser_class"):
            QMessageBox.warning(self, "Formato no disponible", "Seleccione un formato de archivo instalado.")
            return
        allowed = {ext.lower() for ext in (addon.get("ui_features") or {}).get("file_extensions", [])}
        if Path(self.selected_path).suffix.lower() not in allowed:
            QMessageBox.warning(self, "Formato incompatible", "El formato seleccionado no corresponde a la extensión del archivo.")
            return
        self._start_worker(ImportWorker(self.session, parser_instance=addon["parser_class"](), path=self.selected_path), f"Importando {Path(self.selected_path).name}...")

    def _start_worker(self, worker, status):
        self.spinner_label.setVisible(True)
        self.status_label.setText(status)
        self.live_log.clear()
        self.btn_import.setEnabled(False)
        self.btn_import_driver.setEnabled(False)
        self.worker = worker
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.import_finished)
        self.worker.failed.connect(self.import_failed)
        self.worker.finished.connect(self.cleanup_worker)
        self.worker.failed.connect(self.cleanup_worker)
        self.worker.start()

    def cleanup_worker(self, *_args):
        self.spinner_label.setVisible(False)
        self.btn_import.setEnabled(True)
        self.btn_import_driver.setEnabled(True)
        self.worker = None

    def show_path(self):
        if self.selected_path and os.path.isfile(self.selected_path):
            self.path_label.setText(f"Archivo: {self.selected_path}")
        elif self.selected_path:
            self.path_label.setText(f"Archivo ausente. Revise la ruta:\n{self.selected_path}")
        else:
            self.path_label.setText("Archivo: (no seleccionado)")

    def update_progress(self, total, nuevos, duplicados, message):
        self.status_label.setText(f"Logs: {total} | Nuevos: {nuevos} | Duplicados: {duplicados}")
        if message:
            self.live_log.append(message)

    def import_finished(self, nuevos, duplicados):
        self.data_changed.emit()
        QMessageBox.information(self, "Importación finalizada", f"Nuevos: {nuevos}\nDuplicados: {duplicados}")

    def import_failed(self, message):
        self.live_log.append(message)
        QMessageBox.critical(self, "Error de importación", message)
