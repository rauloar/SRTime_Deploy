import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QLabel, QTextEdit, QPushButton, QFileDialog
from PySide6.QtCore import QSettings, QThread, Signal
from services.importer_service import import_att_logs

class ImportWorker(QThread):
    progress = Signal(int, int, int, str)
    finished = Signal(int, int)

    def __init__(self, session, parser_instance, path=None, connection_params=None):
        super().__init__()
        self.session = session
        self.parser_instance = parser_instance
        self.path = path
        self.connection_params = connection_params

    def run(self):
        from services.addons.base_driver import BiometricDriver
        if isinstance(self.parser_instance, BiometricDriver):
            from services.importer_service import import_from_driver
            nuevos, duplicados, total, logs_msgs = import_from_driver(self.parser_instance, self.connection_params, self.session, self.progress)
        else:
            from services.importer_service import import_att_logs
            # parser_instance=None → importación default (formato TXT fijo)
            # parser_instance=AttendanceParser → importación con parser de addon (TXT de marca)
            nuevos, duplicados, total, logs_msgs = import_att_logs(self.path, self.session, self.progress, self.parser_instance)

        self.finished.emit(nuevos, duplicados)

class ImportTab(QWidget):
    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar TXT", "", "Text Files (*.txt)")
        if path:
            self.selected_path = path
            QSettings("SRTime", "Attendance").setValue("import/source_file", path)
            self.path_label.setText(f"Archivo: {path}")
        else:
            self.path_label.setText("Archivo: (no seleccionado)")

            self.show_path()

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.selected_path = str(
            QSettings("SRTime", "Attendance").value("import/source_file", "") or ""
        )
        layout = QVBoxLayout()
        from PySide6.QtWidgets import QStyle, QTabWidget, QComboBox, QLineEdit
        style = self.style()

        # Obtener Addons
        import services.addons
        self.addons = services.addons.get_available_parsers()

        # --- TAB WIDGET PRINCIPAL ---
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- TAB 1: ARCHIVO ---
        self.tab_file = QWidget()
        file_layout = QVBoxLayout(self.tab_file)

        self.btn_import = QPushButton("Importar TXT")
        self.btn_import.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.btn_import.clicked.connect(self.import_txt)

        self.path_label = QLabel("Archivo: (no seleccionado)")
        file_layout.addWidget(self.path_label)

        self.btn_select = QPushButton("Buscar Archivo")
        self.btn_select.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.btn_select.clicked.connect(self.select_file)
        file_layout.addWidget(self.btn_select)

        file_layout.addWidget(self.btn_import)
        file_layout.addStretch()
        self.tabs.addTab(self.tab_file, "Desde Archivo")

        # --- TAB 2: TERMINAL DE RED ---
        self.tab_device = QWidget()
        self.device_layout = QVBoxLayout(self.tab_device)

        self.terminal_selector = QComboBox()
        self.device_layout.addWidget(QLabel("Equipo Registrado:"))
        self.device_layout.addWidget(self.terminal_selector)

        # Load Terminals into ComboBox
        self.update_terminal_selector()

        from PySide6.QtWidgets import QHBoxLayout
        self.device_btn_layout = QHBoxLayout()

        self.btn_test_conn = QPushButton("Probar Conexión")
        self.btn_test_conn.clicked.connect(self.test_driver_connection)
        self.device_btn_layout.addWidget(self.btn_test_conn)

        self.btn_sync_time = QPushButton("Sincronizar Hora")
        self.btn_sync_time.clicked.connect(self.sync_driver_time)
        self.device_btn_layout.addWidget(self.btn_sync_time)

        self.device_layout.addLayout(self.device_btn_layout)

        self.btn_import_driver = QPushButton("Descargar Memorias")
        self.btn_import_driver.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px; background-color: #2e6b2e; color: white;")
        self.btn_import_driver.clicked.connect(self.import_from_driver_ui)
        self.device_layout.addWidget(self.btn_import_driver)
        self.device_layout.addStretch()

        self.tabs.addTab(self.tab_device, "Desde Terminal")

        # --- LOGS COMUNES (Bottom) ---
        self.status_label = QLabel("Logs: 0 | Nuevos: 0 | Duplicados: 0")
        layout.addWidget(self.status_label)
        self.live_log = QTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setMaximumHeight(120)
        layout.addWidget(self.live_log)
        self.spinner_label = QLabel("Importando...")
        self.spinner_label.setVisible(False)
        layout.addWidget(self.spinner_label)
        self.setLayout(layout)
        
        self.show_path()

    def update_terminal_selector(self):
        self.terminal_selector.clear()
        from models.terminal import DeviceTerminal
        terminals = self.session.query(DeviceTerminal).filter_by(is_active=True).all()
        for t in terminals:
            self.terminal_selector.addItem(f"{t.name} ({t.ip})", userData=t.id)

    def test_driver_connection(self):
        t_id_val = self.terminal_selector.currentData()
        if not t_id_val:
            QMessageBox.warning(self, "Aviso", "No hay terminal seleccionada.")
            return

        from models.terminal import DeviceTerminal
        terminal = self.session.query(DeviceTerminal).get(t_id_val)
        if not terminal: return
        
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            from services.terminals import test_connection
            res = test_connection(terminal)
            QMessageBox.information(self, "Conexión Exitosa",
                f"Dispositivo: {res.get('name')}\n"
                f"MAC: {res.get('mac')}\n"
                f"Número de Serie: {res.get('serial_number')}\n"
                f"Firmware: {res.get('firmware')}\n"
                f"Hora Reloj: {res.get('time')}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error de conexión", f"No se pudo conectar al dispositivo:\n{str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def sync_driver_time(self):
        t_id_val = self.terminal_selector.currentData()
        if not t_id_val:
            QMessageBox.warning(self, "Aviso", "No hay terminal seleccionada.")
            return

        from models.terminal import DeviceTerminal
        terminal = self.session.query(DeviceTerminal).get(t_id_val)
        if not terminal: return

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            from services.terminals import sync_time
            ok = sync_time(terminal)
            if ok:
                QMessageBox.information(self, "Sincronización Exitosa", "Se actualizó la hora del dispositivo correctamente.")
            else:
                QMessageBox.warning(self, "Aviso", "El controlador no pudo sincronizar la hora.")
        except Exception as e:
            QMessageBox.critical(self, "Error al sincronizar", f"Fallo al sincronizar hora:\n{str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def import_from_driver_ui(self):
        t_id_val = self.terminal_selector.currentData()
        if not t_id_val:
            QMessageBox.warning(self, "Aviso", "No hay terminal seleccionada.")
            return

        from models.terminal import DeviceTerminal
        terminal = self.session.query(DeviceTerminal).get(t_id_val)
        if not terminal: return

        from services.terminals import get_connection_params, get_driver_instance
        driver_instance = get_driver_instance(terminal)
        params = get_connection_params(terminal)
            
        self.spinner_label.setVisible(True)
        self.status_label.setText(f"Importando desde {terminal.name}...")
        self.live_log.clear()
        
        self.worker = ImportWorker(self.session, driver_instance, connection_params=params)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.import_finished)
        self.worker.finished.connect(self.cleanup_worker)
        self.worker.start()

    def import_txt(self):
        path = self.selected_path
        if not path or not os.path.exists(path):
            msg = QMessageBox(self)
            msg.setWindowTitle("Archivo no encontrado")
            msg.setText("No se encontró el archivo. ¿Deseas buscarlo?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            result = msg.exec_()
            if result == QMessageBox.StandardButton.Yes:
                self.select_file()
            return
        self.spinner_label.setVisible(True)
        self.status_label.setText("Importando...")
        self.live_log.clear()
        
        # Importación default: formato TXT fijo, no necesita parser de addon
        self.worker = ImportWorker(self.session, None, path=path)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.import_finished)
        self.worker.finished.connect(self.cleanup_worker)
        self.worker.start()

    def cleanup_worker(self, *args):
        self.worker = None
    def show_path(self):
        path = self.selected_path
        if path and os.path.exists(path):
            self.path_label.setText(f"Archivo: {path}")
            self.btn_select.setVisible(False)
        else:
            if path:
                self.path_label.setText(f"Archivo ausente. Revise la ruta:\n{path}")
            else:
                self.path_label.setText("Archivo: (no seleccionado)")
            self.btn_select.setVisible(True)

    def update_progress(self, total, nuevos, duplicados, msg):
        self.status_label.setText(f"Logs: {total} | Nuevos: {nuevos} | Duplicados: {duplicados}")
        if msg:
            self.live_log.append(msg)

    def import_finished(self, nuevos, duplicados):
        self.spinner_label.setVisible(False)
        QMessageBox.information(self, "Importación finalizada", f"Nuevos: {nuevos}\nDuplicados: {duplicados}")
