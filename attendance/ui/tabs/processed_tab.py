from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QHBoxLayout, QDialog, QLabel, QTimeEdit,
                               QTextEdit, QFileDialog, QStyle, QComboBox, QDateEdit)
from PySide6.QtCore import Qt, QThread, Signal, QTime, QDate
from sqlalchemy.orm import Session
from models.processed_attendance import ProcessedAttendance
from models.employee import User
from models.shift import Shift
from services.engine import AttendanceEngine
from services.justification import JustificationService
from services.metrics import MetricsCalculator
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
    def __init__(self, session: Session, current_auth_user: dict = None):
        super().__init__()
        self.session = session
        auth = current_auth_user or {}
        self.current_role = auth.get("role", "viewer")
        self.current_username = auth.get("username", "")

        layout = QVBoxLayout(self)

        # ── Filters ────────────────────────────────────────────────────────
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

        filter_layout.addWidget(QLabel("Estado:"))
        self.status_selector = QComboBox()
        self.status_selector.addItems(["Todos", "OK", "INCOMPLETO", "AUSENTE", "JUSTIFICADO", "FERIADO", "PENDIENTE"])
        filter_layout.addWidget(self.status_selector)

        self.btn_refresh = QPushButton("Actualizar Filtros")
        self.btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_refresh.clicked.connect(self.load_data)
        filter_layout.addWidget(self.btn_refresh)
        layout.addLayout(filter_layout)

        # ── Engine + export toolbar ────────────────────────────────────────
        btn_toolbar = QHBoxLayout()

        self.btn_process = QPushButton("Procesar Pendientes")
        self.btn_process.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_process.clicked.connect(lambda: self.process_data(force_all=False))
        btn_toolbar.addWidget(self.btn_process)

        self.btn_reprocess = QPushButton("Reprocesar Histórico")
        self.btn_reprocess.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_reprocess.clicked.connect(lambda: self.process_data(force_all=True))
        btn_toolbar.addWidget(self.btn_reprocess)

        btn_toolbar.addStretch()

        self.btn_export_csv = QPushButton("Exportar CSV")
        self.btn_export_csv.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_export_csv.clicked.connect(self.export_csv)
        btn_toolbar.addWidget(self.btn_export_csv)

        self.btn_export_excel = QPushButton("Exportar Excel")
        self.btn_export_excel.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon))
        self.btn_export_excel.clicked.connect(self.export_excel)
        btn_toolbar.addWidget(self.btn_export_excel)

        self.btn_export_pdf = QPushButton("Exportar PDF")
        self.btn_export_pdf.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        btn_toolbar.addWidget(self.btn_export_pdf)

        layout.addLayout(btn_toolbar)

        # ── Justification toolbar (role-dependent) ─────────────────────────
        justify_toolbar = QHBoxLayout()

        if self.current_role == "root":
            self.btn_justify = QPushButton("Justificar Directamente")
            self.btn_justify.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
            self.btn_justify.clicked.connect(self.justify_selected_row)
            justify_toolbar.addWidget(self.btn_justify)

            self.btn_approve = QPushButton("Aprobar Solicitud")
            self.btn_approve.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
            self.btn_approve.setEnabled(False)
            self.btn_approve.clicked.connect(self.approve_selected_row)
            justify_toolbar.addWidget(self.btn_approve)

            self.btn_reject = QPushButton("Rechazar Solicitud")
            self.btn_reject.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton))
            self.btn_reject.setEnabled(False)
            self.btn_reject.clicked.connect(self.reject_selected_row)
            justify_toolbar.addWidget(self.btn_reject)

        elif self.current_role in ("admin", "supervisor"):
            self.btn_request_justify = QPushButton("Solicitar Justificación")
            self.btn_request_justify.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
            self.btn_request_justify.clicked.connect(self.request_justify_selected_row)
            justify_toolbar.addWidget(self.btn_request_justify)

        justify_toolbar.addStretch()
        layout.addLayout(justify_toolbar)

        # ── Table ──────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Empleado", "Fecha", "Primera Entrada", "Última Salida",
            "Horas Totales", "Tardanza (Min)", "Salida Ant. (Min)", "Hs Extra (Min)", "Estado"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

    def _on_selection_changed(self):
        if self.current_role != "root":
            return
        row = self.table.currentRow()
        if row < 0:
            self.btn_approve.setEnabled(False)
            self.btn_reject.setEnabled(False)
            return
        status_item = self.table.item(row, 8)
        is_pending = status_item and status_item.text() == "PENDIENTE"
        self.btn_approve.setEnabled(bool(is_pending))
        self.btn_reject.setEnabled(bool(is_pending))

    def _get_selected_record(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Atención", "Seleccioná una fila primero.")
            return None
        item = self.table.item(row, 0)
        processed_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not processed_id:
            return None
        return self.session.query(ProcessedAttendance).filter_by(id=processed_id).first()

    def update_user_selector(self):
        current_data = self.user_selector.currentData()
        self.user_selector.clear()
        self.user_selector.addItem("Todos")
        users = self.session.query(User).filter(User.is_active == True).all()
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
        status_value = self.status_selector.currentText()

        query = self.session.query(ProcessedAttendance, User).join(
            User, ProcessedAttendance.employee_id == User.id
        )
        if user_value and self.user_selector.currentText() != "Todos":
            query = query.filter(User.identifier == user_value)
        if status_value != "Todos":
            query = query.filter(ProcessedAttendance.status == status_value)
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

            status_text = processed.status
            if processed.status == "PENDIENTE" and processed.requested_by:
                status_text = f"PENDIENTE ({processed.requested_by})"
            self.table.setItem(row_idx, 8, QTableWidgetItem(status_text))

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
        self.btn_process.setText("Procesar Pendientes")
        if error_msg:
            QMessageBox.critical(self, "Error al Procesar", f"Hubo un problema:\n{error_msg}")
        else:
            txt = "Novedades" if count > 0 else "No había fichadas nuevas"
            QMessageBox.information(
                self,
                "Proceso Completado",
                f"{txt}. Se procesaron {count} flujos diarios y se sincronizaron ausencias del rango.",
            )
            self.load_data()

    # ── Root: justificación directa ────────────────────────────────────────
    def justify_selected_row(self):
        processed = self._get_selected_record()
        if not processed:
            return

        if processed.status == "OK":
            reply = QMessageBox.question(
                self, "Aviso",
                "Este registro ya está OK. ¿Deseás justificarlo de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        self._open_justify_dialog(processed, direct=True)

    def _open_justify_dialog(self, processed, direct: bool):
        dialog = QDialog(self)
        dialog.setWindowTitle("Justificar Asistencia" if direct else "Solicitar Justificación")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Fecha: {processed.date}"))

        te_in = QTimeEdit()
        te_in.setDisplayFormat("HH:mm")
        ref_in = processed.pending_first_in if not direct and processed.pending_first_in else processed.first_in
        if ref_in:
            te_in.setTime(QTime(ref_in.hour, ref_in.minute))

        te_out = QTimeEdit()
        te_out.setDisplayFormat("HH:mm")
        ref_out = processed.pending_last_out if not direct and processed.pending_last_out else processed.last_out
        if ref_out:
            te_out.setTime(QTime(ref_out.hour, ref_out.minute))

        layout.addWidget(QLabel("Entrada justificada:"))
        layout.addWidget(te_in)
        layout.addWidget(QLabel("Salida justificada:"))
        layout.addWidget(te_out)
        layout.addWidget(QLabel("Motivo:"))
        te_reason = QTextEdit(processed.pending_justification or processed.justification or "")
        te_reason.setMaximumHeight(80)
        layout.addWidget(te_reason)

        btns = QHBoxLayout()
        btn_save = QPushButton("Guardar" if direct else "Enviar Solicitud")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        def save():
            reason = te_reason.toPlainText().strip()
            if not reason:
                QMessageBox.warning(dialog, "Obligatorio", "Debe ingresar el motivo.")
                return

            qt_in = te_in.time()
            qt_out = te_out.time()
            t_in = time(qt_in.hour(), qt_in.minute())
            t_out = time(qt_out.hour(), qt_out.minute())

            if direct:
                svc = JustificationService(self.session)
                svc.apply_direct(processed, t_in, t_out, reason)
                dialog.accept()
                QMessageBox.information(self, "Justificado", "Registro justificado correctamente.")
            else:
                svc = JustificationService(self.session)
                svc.request(processed, t_in, t_out, reason, self.current_username)
                dialog.accept()
                QMessageBox.information(self, "Solicitud enviada", "La solicitud quedó pendiente de aprobación.")
            self.load_data()

        btn_save.clicked.connect(save)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    # ── Supervisor: solicitar justificación ───────────────────────────────
    def request_justify_selected_row(self):
        processed = self._get_selected_record()
        if not processed:
            return
        if processed.status == "PENDIENTE":
            QMessageBox.warning(self, "Atención", "Este registro ya tiene una solicitud pendiente.")
            return
        self._open_justify_dialog(processed, direct=False)

    # ── Root: aprobar solicitud pendiente ─────────────────────────────────
    def approve_selected_row(self):
        processed = self._get_selected_record()
        if not processed or processed.status != "PENDIENTE":
            return

        msg = (
            f"Empleado: {processed.employee_id}\n"
            f"Fecha: {processed.date}\n"
            f"Entrada solicitada: {processed.pending_first_in.strftime('%H:%M') if processed.pending_first_in else '--'}\n"
            f"Salida solicitada: {processed.pending_last_out.strftime('%H:%M') if processed.pending_last_out else '--'}\n"
            f"Motivo: {processed.pending_justification or ''}\n"
            f"Solicitado por: {processed.requested_by or ''}\n\n"
            "¿Aprobás esta justificación?"
        )
        reply = QMessageBox.question(self, "Aprobar Justificación", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        svc = JustificationService(self.session)
        svc.approve(processed)
        QMessageBox.information(self, "Aprobado", "Justificación aprobada.")
        self.load_data()

    # ── Root: rechazar solicitud pendiente ────────────────────────────────
    def reject_selected_row(self):
        processed = self._get_selected_record()
        if not processed or processed.status != "PENDIENTE":
            return

        reply = QMessageBox.question(
            self, "Rechazar Solicitud",
            f"¿Rechazás la solicitud de {processed.requested_by or 'supervisor'} para el día {processed.date}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        svc = JustificationService(self.session)
        svc.reject(processed)
        QMessageBox.information(self, "Rechazado", "Solicitud rechazada. El registro volvió a su estado anterior.")
        self.load_data()

    # ── Export helpers ─────────────────────────────────────────────────────
    def _collect_export_data(self):
        data = []
        selected_rows = self.table.selectionModel().selectedRows()
        row_indexes = [idx.row() for idx in selected_rows] if selected_rows else list(range(self.table.rowCount()))
        for row in row_indexes:
            data.append([
                self.table.item(row, c).text() if self.table.item(row, c) else ""
                for c in range(9)
            ])
        return data

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        cols = ["Empleado", "Fecha", "Primera Entrada", "Última Salida", "Horas Totales",
                "Tardanza (Min)", "Salida Ant. (Min)", "Hs Extra (Min)", "Estado"]
        pd.DataFrame(self._collect_export_data(), columns=cols).to_csv(path, index=False)

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", "", "Excel Files (*.xlsx)")
        if not path:
            return
        cols = ["Empleado", "Fecha", "Primera Entrada", "Última Salida", "Horas Totales",
                "Tardanza (Min)", "Salida Ant. (Min)", "Hs Extra (Min)", "Estado"]
        pd.DataFrame(self._collect_export_data(), columns=cols).to_excel(path, index=False)

    def export_pdf(self):
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.lib import colors

        path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", "", "PDF Files (*.pdf)")
        if not path:
            return

        data = self._collect_export_data()
        if not data:
            QMessageBox.information(self, "Sin datos", "No hay filas para exportar.")
            return

        headers = ["Empleado", "Fecha", "1ra Entrada", "Últ. Salida",
                   "Hs Total", "Tard.(Min)", "Sal.Ant.(Min)", "HsEx.(Min)", "Estado"]

        doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                                leftMargin=1*cm, rightMargin=1*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        styles = getSampleStyleSheet()
        elements = [Paragraph("Asistencia Procesada", styles["Title"]), Spacer(1, 0.4*cm)]

        col_widths = [3.8*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2*cm, 2.2*cm, 2.4*cm, 2.4*cm, 2.4*cm]
        table_data = [headers] + data
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDBDBD")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ]
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F5F5")))

        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle(style_cmds))
        elements.append(t)
        doc.build(elements)
