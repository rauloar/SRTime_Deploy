from datetime import date, time

from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QStyle, QTableWidget, QTableWidgetItem,
    QTimeEdit, QVBoxLayout, QWidget, QHeaderView, QTextEdit, QComboBox,
)
from sqlalchemy.orm import Session

from models.employee import User
from models.processed_attendance import ProcessedAttendance
from services.absences import AbsenceService, attendance_attention_filter
from services.justification import JustificationService


class AbsencesTab(QWidget):
    """Vista desktop de ausencias e incompletos, basada en processed_attendance."""

    def __init__(self, session: Session, current_auth_user: dict | None = None):
        super().__init__()
        self.session = session
        auth = current_auth_user or {}
        self.current_role = auth.get("role", "viewer")
        self.current_username = auth.get("username", "")
        self.is_root = self.current_role == "root"
        self.can_manage = self.current_role in {"root", "admin", "supervisor"}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Desde:"))
        self.date_start = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_start.setCalendarPopup(True)
        filters.addWidget(self.date_start)
        filters.addWidget(QLabel("Hasta:"))
        self.date_end = QDateEdit(QDate.currentDate())
        self.date_end.setCalendarPopup(True)
        filters.addWidget(self.date_end)
        filters.addWidget(QLabel("Estado:"))
        self.status_selector = QComboBox()
        self.status_selector.addItems(["Todos", "AUSENTE", "INCOMPLETO", "PENDIENTE", "JUSTIFICADO"])
        filters.addWidget(self.status_selector)
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_refresh.clicked.connect(self.load_data)
        filters.addWidget(self.btn_refresh)
        filters.addStretch()
        layout.addLayout(filters)

        toolbar = QHBoxLayout()
        if self.can_manage:
            self.btn_reprocess = QPushButton("Reprocesar Ausencias")
            self.btn_reprocess.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
            self.btn_reprocess.clicked.connect(self.reprocess)
            toolbar.addWidget(self.btn_reprocess)
        if self.is_root:
            self.btn_handle = QPushButton("Gestionar Selección")
            self.btn_handle.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
            self.btn_handle.clicked.connect(self.handle_selected)
            toolbar.addWidget(self.btn_handle)
            self.btn_approve = QPushButton("Aprobar Ausencia")
            self.btn_approve.clicked.connect(self.approve_selected)
            toolbar.addWidget(self.btn_approve)
            self.btn_reject = QPushButton("Rechazar Ausencia")
            self.btn_reject.clicked.connect(self.reject_selected)
            toolbar.addWidget(self.btn_reject)
        elif self.can_manage:
            self.btn_handle = QPushButton("Solicitar Gestión")
            self.btn_handle.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
            self.btn_handle.clicked.connect(self.handle_selected)
            toolbar.addWidget(self.btn_handle)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Empleado", "Fecha", "Entrada", "Salida", "Estado", "Motivo", "Solicitado por",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def _selected_record(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Atención", "Seleccioná una fila primero.")
            return None
        item = self.table.item(row, 0)
        record_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return self.session.get(ProcessedAttendance, record_id) if record_id else None

    def load_data(self):
        start = self.date_start.date().toPython()
        end = self.date_end.date().toPython()
        query = self.session.query(ProcessedAttendance, User).join(User, ProcessedAttendance.employee_id == User.id).filter(
            attendance_attention_filter(), ProcessedAttendance.date >= start, ProcessedAttendance.date <= end,
        )
        status = self.status_selector.currentText()
        if status != "Todos":
            query = query.filter(ProcessedAttendance.status == status)
        rows = query.order_by(ProcessedAttendance.date.desc(), User.last_name).all()
        self.table.setRowCount(len(rows))
        for index, (record, employee) in enumerate(rows):
            name = f"{employee.last_name or ''}, {employee.first_name or ''}".strip(", ") or employee.identifier
            employee_item = QTableWidgetItem(name)
            employee_item.setData(Qt.ItemDataRole.UserRole, record.id)
            self.table.setItem(index, 0, employee_item)
            self.table.setItem(index, 1, QTableWidgetItem(str(record.date)))
            self.table.setItem(index, 2, QTableWidgetItem(record.first_in.strftime("%H:%M") if record.first_in else "--:--"))
            self.table.setItem(index, 3, QTableWidgetItem(record.last_out.strftime("%H:%M") if record.last_out else "--:--"))
            self.table.setItem(index, 4, QTableWidgetItem(record.status))
            self.table.setItem(index, 5, QTableWidgetItem(record.justification or record.pending_justification or ""))
            self.table.setItem(index, 6, QTableWidgetItem(record.requested_by or ""))

    def reprocess(self):
        start = self.date_start.date().toPython()
        end = self.date_end.date().toPython()
        if end < start or end > date.today():
            QMessageBox.warning(self, "Rango inválido", "Elegí un rango válido que no incluya fechas futuras.")
            return
        created = AbsenceService(self.session).sync(start, end)
        QMessageBox.information(self, "Ausencias", f"Reproceso completado: {created} ausencia(s) nueva(s).")
        self.load_data()

    def _reason_dialog(self, title: str, record: ProcessedAttendance):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        form = QFormLayout(dialog)
        form.addRow("Fecha:", QLabel(str(record.date)))
        reason = QTextEdit(record.justification or record.pending_justification or "")
        reason.setMaximumHeight(80)
        form.addRow("Motivo (obligatorio):", reason)
        buttons = QHBoxLayout()
        save = QPushButton("Guardar")
        cancel = QPushButton("Cancelar")
        buttons.addWidget(save); buttons.addWidget(cancel)
        form.addRow(buttons)
        save.clicked.connect(dialog.accept)
        cancel.clicked.connect(dialog.reject)
        return dialog, reason

    def _incomplete_dialog(self, record: ProcessedAttendance, direct: bool):
        dialog = QDialog(self)
        dialog.setWindowTitle("Corregir y justificar" if direct else "Solicitar corrección")
        form = QFormLayout(dialog)
        form.addRow("Fecha:", QLabel(str(record.date)))
        form.addRow("Entrada registrada:", QLabel(record.first_in.strftime("%H:%M") if record.first_in else "--:--"))
        form.addRow("Salida registrada:", QLabel(record.last_out.strftime("%H:%M") if record.last_out else "--:--"))
        entry = QTimeEdit(QTime(record.first_in.hour, record.first_in.minute) if record.first_in else QTime(8, 0))
        exit = QTimeEdit(QTime(record.last_out.hour, record.last_out.minute) if record.last_out else QTime(17, 0))
        entry.setDisplayFormat("HH:mm"); exit.setDisplayFormat("HH:mm")
        reason = QTextEdit(record.justification or "")
        reason.setMaximumHeight(80)
        form.addRow("Entrada justificada:", entry)
        form.addRow("Salida justificada:", exit)
        form.addRow("Motivo (obligatorio):", reason)
        buttons = QHBoxLayout(); save = QPushButton("Guardar"); cancel = QPushButton("Cancelar")
        buttons.addWidget(save); buttons.addWidget(cancel); form.addRow(buttons)
        save.clicked.connect(dialog.accept); cancel.clicked.connect(dialog.reject)
        return dialog, entry, exit, reason

    def handle_selected(self):
        record = self._selected_record()
        if not record:
            return
        if record.status == "AUSENTE":
            dialog, reason = self._reason_dialog("Justificar ausencia" if self.is_root else "Solicitar justificación", record)
            if dialog.exec() != QDialog.DialogCode.Accepted or not reason.toPlainText().strip():
                return
            service = JustificationService(self.session)
            if self.is_root:
                service.apply_absence_direct(record, reason.toPlainText().strip())
            else:
                service.request_absence(record, reason.toPlainText().strip(), self.current_username)
        elif record.status == "INCOMPLETO":
            dialog, entry, exit, reason = self._incomplete_dialog(record, self.is_root)
            if dialog.exec() != QDialog.DialogCode.Accepted or not reason.toPlainText().strip():
                return
            service = JustificationService(self.session)
            first_in = time(entry.time().hour(), entry.time().minute())
            last_out = time(exit.time().hour(), exit.time().minute())
            if self.is_root:
                service.apply_direct(record, first_in, last_out, reason.toPlainText().strip())
            else:
                service.request(record, first_in, last_out, reason.toPlainText().strip(), self.current_username)
        else:
            QMessageBox.information(self, "Gestión", "Los pendientes de movimientos se administran desde Movimientos Procesados.")
            return
        self.load_data()

    def approve_selected(self):
        record = self._selected_record()
        if not record or record.status != "PENDIENTE" or record.previous_status != "AUSENTE":
            QMessageBox.warning(self, "Atención", "Seleccioná una justificación de ausencia pendiente.")
            return
        JustificationService(self.session).approve_absence(record)
        self.load_data()

    def reject_selected(self):
        record = self._selected_record()
        if not record or record.status != "PENDIENTE" or record.previous_status != "AUSENTE":
            QMessageBox.warning(self, "Atención", "Seleccioná una justificación de ausencia pendiente.")
            return
        JustificationService(self.session).reject_absence(record)
        self.load_data()
