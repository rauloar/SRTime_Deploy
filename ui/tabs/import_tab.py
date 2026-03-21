import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QLabel, QTextEdit, QPushButton, QFileDialog
from PySide6.QtCore import QThread, Signal
from services.importer_service import import_att_logs

class ImportWorker(QThread):
    progress = Signal(int, int, int, str)  # total, nuevos, duplicados, mensaje
    finished = Signal(int, int)

    def __init__(self, path, session):
        super().__init__()
        self.path = path
        self.session = session

    def run(self):
        from services.importer_service import import_att_logs
        nuevos, duplicados, total, logs_msgs = import_att_logs(self.path, self.session, self.progress)
        self.finished.emit(nuevos, duplicados)

class ImportTab(QWidget):
    def select_file(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar TXT", "", "Text Files (*.txt)")
        if path:
            self.path_label.setText(f"Archivo: {path}")
            self.btn_select.setEnabled(False)
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
            self.btn_select.setEnabled(True)

    def __init__(self, session):
        super().__init__()
        self.session = session
        layout = QVBoxLayout()
        self.status_label = QLabel("Logs: 0 | Nuevos: 0 | Duplicados: 0")
        layout.addWidget(self.status_label)
        self.live_log = QTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setMaximumHeight(120)
        layout.addWidget(self.live_log)
        self.spinner_label = QLabel("Importando...")
        self.spinner_label.setVisible(False)
        layout.addWidget(self.spinner_label)
        self.path_label = QLabel("Archivo: (no seleccionado)")
        layout.addWidget(self.path_label)
        from PySide6.QtWidgets import QStyle
        style = self.style()
        self.btn_select = QPushButton("Buscar Archivo")
        self.btn_select.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.btn_select.clicked.connect(self.select_file)
        layout.addWidget(self.btn_select)

        self.btn_import = QPushButton("Importar TXT")
        self.btn_import.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.btn_import.clicked.connect(self.import_txt)
        layout.addWidget(self.btn_import)

        self.btn_restore = QPushButton("Restaurar Backup")
        self.btn_restore.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_restore.clicked.connect(self.restore_backup)
        layout.addWidget(self.btn_restore)
        self.setLayout(layout)
        
        # Actualizar visualmente la ruta persistente al abrir la ventana
        self.show_path()
    def restore_backup(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Backup", "", "Backup Files (*.bak)")
            if not path:
                return
            with open(path, 'r') as f:
                lines = f.readlines()
            total = len(lines)
            resumen = ""
            valid_lines = 0
            invalid_lines = 0
            consecutive_valid = 0
            for line in lines:
                if len(line) >= 33:
                    try:
                        identifier = line[0:15]
                        fecha_raw  = line[15:21]
                        hora_raw   = line[21:25]
                        mark_type  = int(line[25:26])
                        flags      = line[26:33]
                        from datetime import datetime
                        datetime.strptime(fecha_raw, "%d%m%y")
                        datetime.strptime(hora_raw, "%H%M")
                        if any(substr in line for substr in [identifier.strip(), fecha_raw, hora_raw]):
                            consecutive_valid += 1
                        else:
                            consecutive_valid = 0
                        valid_lines += 1
                    except Exception:
                        invalid_lines += 1
                        consecutive_valid = 0
                else:
                    invalid_lines += 1
                    consecutive_valid = 0
                if consecutive_valid >= 3:
                    break
            if consecutive_valid < 3:
                QMessageBox.warning(self, "Backup inválido", "No se encontraron 3 líneas consecutivas válidas.\nNo se puede restaurar.")
                return
            if total > 0:
                resumen += f"Primer registro: {lines[0][:40]}\n"
                resumen += f"Último registro: {lines[-1][:40]}\n"
            else:
                resumen += "El archivo está vacío.\n"
            resumen += f"Total de registros: {total}\n"
            resumen += f"Válidos: {valid_lines} | Inválidos: {invalid_lines}"
            if invalid_lines > 0:
                QMessageBox.warning(self, "Backup inválido", f"El archivo contiene {invalid_lines} registros inválidos.\nNo se puede restaurar.")
                return
            msg = QMessageBox(self)
            msg.setWindowTitle("Resumen del Backup")
            msg.setText(resumen + "\n¿Deseas restaurar este backup?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            result = msg.exec_()
            if result == QMessageBox.StandardButton.Yes:
                orig_path = path[:-4]  # Quitar .bak
                try:
                    with open(path, 'r') as src, open(orig_path, 'w') as dst:
                        dst.write(src.read())
                    QMessageBox.information(self, "Backup restaurado", f"Backup restaurado como {os.path.basename(orig_path)}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo restaurar el backup:\n{str(e)}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo analizar el backup:\n{str(e)}")

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
        # Mantener referencia al thread
        self.worker = ImportWorker(path, self.session)
        # ...existing code...
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.import_finished)
        self.worker.finished.connect(self.cleanup_worker)
        self.worker.start()

    def cleanup_worker(self, *args):
        self.worker = None
    def show_path(self):
        import os
        from models.attendance import AttendanceLog
        from sqlalchemy import desc
        log_reciente = self.session.query(AttendanceLog).order_by(desc(AttendanceLog.created_at)).first()
        path = log_reciente.source_file if log_reciente and log_reciente.source_file else None
        if path and os.path.exists(path):
            self.path_label.setText(f"Archivo: {path}")
            self.btn_select.setEnabled(False)
        else:
            if path:
                self.path_label.setText(f"Archivo ausente. Revise la ruta:\n{path}")
            else:
                self.path_label.setText("Archivo: (no seleccionado)")
            self.btn_select.setEnabled(True)

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