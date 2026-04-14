import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QLabel, QTextEdit, QPushButton, QFileDialog
from PySide6.QtCore import QThread, Signal
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
            self.path_label.setText(f"Archivo: {path}")
            # Guardar path en la BD
            from models.attendance import AttendanceLog
            from sqlalchemy import desc
            log_reciente = self.session.query(AttendanceLog).order_by(desc(AttendanceLog.created_at)).first()
            if log_reciente:
                log_reciente.source_file = path
                self.session.commit()
            else:
                # Crear registro dummy para guardar path
                dummy = AttendanceLog(
                    employee_id=None,
                    raw_identifier="",
                    date=None,
                    time=None,
                    mark_type=None,
                    source_file=path
                )
                self.session.add(dummy)
                self.session.commit()
        else:
            self.path_label.setText("Archivo: (no seleccionado)")

            self.show_path()

    def __init__(self, session):
        super().__init__()
        self.session = session
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

    def import_from_driver_ui(self):
        t_id_val = self.terminal_selector.currentData()
        if not t_id_val:
            QMessageBox.warning(self, "Aviso", "No hay terminal seleccionada.")
            return

        from models.terminal import DeviceTerminal
        terminal = self.session.query(DeviceTerminal).get(t_id_val)
        if not terminal: return
        
        import services.addons
        info = services.addons.get_addon_info(terminal.driver_name)
        if not info or not info.get("is_driver"):
            QMessageBox.warning(self, "Aviso", "Driver no encontrado.")
            return
            
        driver_instance = info["class"]()
        params = {"ip": terminal.ip, "port": str(terminal.port), "password": terminal.password or "0"}
            
        self.spinner_label.setVisible(True)
        self.status_label.setText(f"Importando desde {terminal.name}...")
        self.live_log.clear()
        
        self.worker = ImportWorker(self.session, driver_instance, connection_params=params)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.import_finished)
        self.worker.finished.connect(self.cleanup_worker)
        self.worker.start()

    def import_txt(self):
        from models.attendance import AttendanceLog
        from sqlalchemy import desc
        log_reciente = self.session.query(AttendanceLog).order_by(desc(AttendanceLog.created_at)).first()
        path = log_reciente.source_file if log_reciente and log_reciente.source_file else None
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
        from models.attendance import AttendanceLog
        from sqlalchemy import desc
        log_reciente = self.session.query(AttendanceLog).order_by(desc(AttendanceLog.created_at)).first()
        path = log_reciente.source_file if log_reciente and log_reciente.source_file else None
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
        # Solo mostrar mensaje si el archivo tenía datos
        import os
        from models.attendance import AttendanceLog
        from sqlalchemy import desc
        log_reciente = self.session.query(AttendanceLog).order_by(desc(AttendanceLog.created_at)).first()
        path = log_reciente.source_file if log_reciente and log_reciente.source_file else None
        file_has_content = False
        if path and os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    file_has_content = bool(f.read().strip())
                
                backup_path = f"{path}.bak"
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                
                os.rename(path, backup_path)
                with open(path, 'w') as f:
                    pass
                
                if file_has_content:
                    backup_name = os.path.basename(backup_path)
                    QMessageBox.information(self, "Backup generado", f"El archivo original fue renombrado y guardado como:\n{backup_name}\nSe creó un archivo vacío para futuras importaciones.")
            except Exception as e:
                QMessageBox.warning(self, "Error al generar backup", f"No se pudo renombrar el archivo:\n{str(e)}")
        QMessageBox.information(self, "Importación finalizada", f"Nuevos: {nuevos}\nDuplicados: {duplicados}")