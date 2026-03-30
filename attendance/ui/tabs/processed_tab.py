from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QMessageBox, QHBoxLayout, QDialog, QLabel, QTimeEdit, QTextEdit, QFileDialog, QStyle)
from PySide6.QtCore import Qt, QThread, Signal, QTime
from sqlalchemy.orm import Session
from models.processed_attendance import ProcessedAttendance
from models.employee import User
from models.shift import Shift
from services.engine import AttendanceEngine
from datetime import datetime, time
import pandas as pd

class EngineWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(int, str)

    def __init__(self, session, force_all=False):
        super().__init__()
        self.session = session
        self.force_all = force_all

    def run(self):
        engine = AttendanceEngine(self.session)
        def progress_cb(current, total):
            self.progress.emit(current, total)
        
        try:
            count = engine.process_all(progress_callback=progress_cb, force_all=self.force_all)
            self.finished.emit(count, "")
        except Exception as e:
            self.finished.emit(0, str(e))

class ProcessedTab(QWidget):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session

        layout = QVBoxLayout(self)

        from PySide6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QDateEdit
        from PySide6.QtCore import QDate
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Fecha inicio:"))
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-30))
        filter_layout.addWidget(self.date_start)

        filter_layout.addWidget(QLabel("Fecha fin:"))
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        filter_layout.addWidget(self.date_end)

        filter_layout.addWidget(QLabel("Usuario(s):"))
        self.user_selector = QComboBox()
        self.user_selector.setEditable(True)
        self.user_selector.addItem("Todos")
        filter_layout.addWidget(self.user_selector)
        
        from PySide6.QtWidgets import QStyle
        self.btn_refresh = QPushButton("Actualizar Filtros")
        self.btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_refresh.clicked.connect(self.load_data)
        filter_layout.addWidget(self.btn_refresh)
        
        layout.addLayout(filter_layout)

        # Botón para detonar el motor y justificar
        btn_toolbar = QHBoxLayout()
        self.btn_process = QPushButton("🚀 Procesar Pendientes")
        self.btn_process.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        self.btn_process.clicked.connect(lambda: self.process_data(force_all=False))
        btn_toolbar.addWidget(self.btn_process)
        
        self.btn_reprocess = QPushButton("🔄 Reprocesar Histórico Completo")
        self.btn_reprocess.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        self.btn_reprocess.clicked.connect(lambda: self.process_data(force_all=True))
        btn_toolbar.addWidget(self.btn_reprocess)
        
        self.btn_justify = QPushButton("🛠️ Justificar Fila Seleccionada")
        self.btn_justify.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        self.btn_justify.clicked.connect(self.justify_selected_row)
        btn_toolbar.addWidget(self.btn_justify)

        self.btn_export_csv = QPushButton("Exportar CSV")
        self.btn_export_csv.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_export_csv.clicked.connect(self.export_csv)
        btn_toolbar.addWidget(self.btn_export_csv)

        self.btn_export_excel = QPushButton("Exportar Excel")
        self.btn_export_excel.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon))
        self.btn_export_excel.clicked.connect(self.export_excel)
        btn_toolbar.addWidget(self.btn_export_excel)
        
        layout.addLayout(btn_toolbar)

        # Tabla de resultados
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Empleado", "Fecha", "Primera Entrada", "Última Salida", 
            "Horas Totales", "Tardanza (Min)", "Salida Ant. (Min)", "Hs Extra (Min)", "Estado"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def update_user_selector(self):
        current_data = self.user_selector.currentData()
        self.user_selector.clear()
        self.user_selector.addItem("Todos")
        users = self.session.query(User).filter(User.is_active==True).all()
        idx = 0
        for i, user in enumerate(users, 1):
            display = (user.first_name or "") + " " + (user.last_name or "")
            self.user_selector.addItem(f"{user.identifier} - {display.strip()}", user.identifier)
            if user.identifier == current_data:
                idx = i
        self.user_selector.setCurrentIndex(idx)

    def load_data(self):
        start = self.date_start.date().toPython()
        end = self.date_end.date().toPython()
        user_value = self.user_selector.currentData()
        
        # Consultar asistencias procesadas haciendo join con usuario
        query = self.session.query(ProcessedAttendance, User).join(
            User, ProcessedAttendance.employee_id == User.id
        )
        
        if user_value and user_value != None and self.user_selector.currentText() != "Todos":
            query = query.filter(User.identifier == user_value)
        if start:
            query = query.filter(ProcessedAttendance.date >= start)
        if end:
            query = query.filter(ProcessedAttendance.date <= end)
            
        records = query.order_by(ProcessedAttendance.date.desc(), User.last_name).all()

        self.table.clearContents()
        self.table.setRowCount(len(records))

        for row_idx, (processed, user) in enumerate(records):
            
            emp_name = f"{user.last_name or ''}, {user.first_name or ''}".strip(", ")
            self.table.setItem(row_idx, 0, QTableWidgetItem(emp_name))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(processed.date)))
            
            f_in = processed.first_in.strftime("%H:%M:%S") if processed.first_in else "--:--:--"
            self.table.setItem(row_idx, 2, QTableWidgetItem(f_in))
            
            l_out = processed.last_out.strftime("%H:%M:%S") if processed.last_out else "--:--:--"
            self.table.setItem(row_idx, 3, QTableWidgetItem(l_out))
            
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{processed.total_hours} hs"))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(processed.tardiness_minutes)))
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(processed.early_departure_minutes)))
            self.table.setItem(row_idx, 7, QTableWidgetItem(str(processed.overtime_minutes)))
            self.table.setItem(row_idx, 8, QTableWidgetItem(processed.status))
            
            # Save the processed ID in the User column user-role data for easy retrieval
            self.table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, processed.id)

    def process_data(self, force_all=False):
        self.btn_process.setEnabled(False)
        self.btn_reprocess.setEnabled(False)
        txt = "Reprocesando..." if force_all else "Procesando pendientes..."
        self.btn_process.setText(txt)
        
        self.worker = EngineWorker(self.session, force_all=force_all)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()

    def update_progress(self, current, total):
        self.btn_process.setText(f"Procesando... {current} / {total}")
        
    def on_processing_finished(self, count, error_msg):
        self.btn_process.setEnabled(True)
        self.btn_reprocess.setEnabled(True)
        self.btn_process.setText("🚀 Procesar Pendientes")
        
        if error_msg:
            QMessageBox.critical(self, "Error al Procesar", f"Hubo un problema al procesar los datos:\n{error_msg}")
        else:
            txt = "Novedades" if count > 0 else "No había fichadas nuevas"
            QMessageBox.information(self, "Proceso Completado", f"{txt}. Se han procesado {count} flujos diarios.")
            self.load_data()

    def justify_selected_row(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Atención", "Por favor selecciona una fila primero.")
            return
            
        item = self.table.item(row, 0)
        processed_id = item.data(Qt.ItemDataRole.UserRole)
        
        processed = self.session.query(ProcessedAttendance).filter_by(id=processed_id).first()
        if not processed: return
        
        if processed.status == "OK":
            reply = QMessageBox.question(self, "Aviso", "Este registro ya está OK. ¿Deseas justificarlo de todos modos?", 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Justificar Asistencia")
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel(f"Fecha: {processed.date}"))
        
        te_in = QTimeEdit()
        te_in.setDisplayFormat("HH:mm")
        if processed.first_in:
            te_in.setTime(QTime(processed.first_in.hour, processed.first_in.minute))
            
        te_out = QTimeEdit()
        te_out.setDisplayFormat("HH:mm")
        if processed.last_out:
            te_out.setTime(QTime(processed.last_out.hour, processed.last_out.minute))
            
        layout.addWidget(QLabel("Entrada Real / Justificada:"))
        layout.addWidget(te_in)
        layout.addWidget(QLabel("Salida Real / Justificada:"))
        layout.addWidget(te_out)
        
        layout.addWidget(QLabel("Razón de Justificación:"))
        te_reason = QTextEdit(processed.justification or "")
        te_reason.setMaximumHeight(80)
        layout.addWidget(te_reason)
        
        btns = QHBoxLayout()
        btn_save = QPushButton("Guardar Justificación")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)
        
        def save():
            reason = te_reason.toPlainText().strip()
            if not reason:
                QMessageBox.warning(dialog, "Obligatorio", "Debe explicar el motivo de la justificación.")
                return
                
            qt_in = te_in.time()
            qt_out = te_out.time()
            
            processed.first_in = time(qt_in.hour(), qt_in.minute())
            processed.last_out = time(qt_out.hour(), qt_out.minute())
            
            # Recalcular horas manualmente
            dt_in = datetime.combine(processed.date, processed.first_in)
            dt_out = datetime.combine(processed.date, processed.last_out)
            if dt_out > dt_in:
                processed.total_hours = round((dt_out - dt_in).total_seconds() / 3600.0, 2)
            else:
                processed.total_hours = 0.0
                
            # Recalculate early departure and overtime based on shift if exists
            employee = self.session.query(User).filter_by(id=processed.employee_id).first()
            if employee and employee.shift_id:
                shift = self.session.query(Shift).filter_by(id=employee.shift_id).first()
                if shift:
                    expected_out_dt = datetime.combine(processed.date, shift.expected_out)
                    if dt_out < expected_out_dt:
                        diff = (expected_out_dt - dt_out).total_seconds() / 60.0
                        processed.early_departure_minutes = int(diff)
                        processed.overtime_minutes = 0
                    elif dt_out > expected_out_dt:
                        diff = (dt_out - expected_out_dt).total_seconds() / 60.0
                        processed.overtime_minutes = int(diff)
                        processed.early_departure_minutes = 0
                    else:
                        processed.early_departure_minutes = 0
                        processed.overtime_minutes = 0
                
            processed.status = "JUSTIFICADO"
            processed.justification = reason
            self.session.commit()
            
            dialog.accept()
            QMessageBox.information(self, "Justificado", "El registro ha sido justificado manualmente. El motor automático no lo sobreescribirá.")
            self.load_data()
            
        btn_save.clicked.connect(save)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def _collect_export_data(self):
        data = []
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row_indexes = [idx.row() for idx in selected_rows]
        else:
            row_indexes = list(range(self.table.rowCount()))

        for row in row_indexes:
            empleado = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            fecha = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
            primera_entrada = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
            ultima_salida = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
            horas_totales = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
            tardanza = self.table.item(row, 5).text() if self.table.item(row, 5) else ""
            salida_ant = self.table.item(row, 6).text() if self.table.item(row, 6) else ""
            hs_extra = self.table.item(row, 7).text() if self.table.item(row, 7) else ""
            estado = self.table.item(row, 8).text() if self.table.item(row, 8) else ""
            data.append([
                empleado,
                fecha,
                primera_entrada,
                ultima_salida,
                horas_totales,
                tardanza,
                salida_ant,
                hs_extra,
                estado,
            ])
        return data

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        data = self._collect_export_data()
        df = pd.DataFrame(data, columns=[
            "Empleado", "Fecha", "Primera Entrada", "Última Salida", "Horas Totales",
            "Tardanza (Min)", "Salida Ant. (Min)", "Hs Extra (Min)", "Estado"
        ])
        df.to_csv(path, index=False)

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", "", "Excel Files (*.xlsx)")
        if not path:
            return
        data = self._collect_export_data()
        df = pd.DataFrame(data, columns=[
            "Empleado", "Fecha", "Primera Entrada", "Última Salida", "Horas Totales",
            "Tardanza (Min)", "Salida Ant. (Min)", "Hs Extra (Min)", "Estado"
        ])
        df.to_excel(path, index=False)
