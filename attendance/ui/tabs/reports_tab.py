from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QComboBox, QSpinBox, QFileDialog,
    QMessageBox, QStyle
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from datetime import date

from services.reports import (
    MONTHLY_REPORT_COLUMNS, aggregate_monthly, build_monthly_pdf,
    monthly_report_headers, monthly_report_rows, monthly_report_title,
)
from services.constants import MONTH_NAMES
from services.export_helpers import build_excel_workbook

_MONTHS = MONTH_NAMES[1:]

_COLS = monthly_report_headers()


class ReportsTab(QWidget):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self._records = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Filter bar ────────────────────────────────────────
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Mes:"))
        self.cb_month = QComboBox()
        for m in _MONTHS:
            self.cb_month.addItem(m)
        today = date.today()
        self.cb_month.setCurrentIndex(today.month - 1)
        filter_bar.addWidget(self.cb_month)

        filter_bar.addWidget(QLabel("Año:"))
        self.sp_year = QSpinBox()
        self.sp_year.setRange(2000, 2100)
        self.sp_year.setValue(today.year)
        filter_bar.addWidget(self.sp_year)

        filter_bar.addWidget(QLabel("Empleado:"))
        self.cb_employee = QComboBox()
        self.cb_employee.setEditable(True)
        self.cb_employee.addItem("Todos")
        filter_bar.addWidget(self.cb_employee)

        self.btn_generate = QPushButton("Generar Reporte")
        self.btn_generate.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        self.btn_generate.clicked.connect(self._generate)
        filter_bar.addWidget(self.btn_generate)

        self.btn_export = QPushButton("Exportar Excel")
        self.btn_export.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon))
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_excel)
        filter_bar.addWidget(self.btn_export)

        self.btn_export_pdf = QPushButton("Exportar PDF")
        self.btn_export_pdf.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.btn_export_pdf.setEnabled(False)
        self.btn_export_pdf.clicked.connect(self._export_pdf)
        filter_bar.addWidget(self.btn_export_pdf)

        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # ── Results table ─────────────────────────────────────
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setColumnCount(len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def load_data(self):
        from models.employee import User
        self.cb_employee.clear()
        self.cb_employee.addItem("Todos")
        employees = self.session.query(User).filter(User.is_active == True).order_by(User.last_name).all()
        for emp in employees:
            name = f"{emp.last_name or ''}, {emp.first_name or ''}".strip(", ")
            self.cb_employee.addItem(f"{emp.identifier} — {name}", emp.id)

    def _generate(self):
        month = self.cb_month.currentIndex() + 1
        year = self.sp_year.value()
        emp_filter_id = self.cb_employee.currentData()

        records = aggregate_monthly(self.session, year, month, emp_filter_id)
        self._records = records

        self.table.clearContents()
        self.table.setRowCount(len(self._records))
        for row, rec in enumerate(self._records):
            for col, (key, _label) in enumerate(MONTHLY_REPORT_COLUMNS):
                value = rec[key]
                text = f"{value:.2f}" if key == "total_hours" else str(value)
                self.table.setItem(row, col, QTableWidgetItem(text))

        self.btn_export.setEnabled(bool(self._records))
        self.btn_export_pdf.setEnabled(bool(self._records))

        if not self._records:
            QMessageBox.information(self, "Sin datos", "No hay registros para el período seleccionado.")

    def _export_excel(self):
        if not self._records:
            return

        path, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", "", "Excel Files (*.xlsx)")
        if not path:
            return

        month = self.cb_month.currentText()
        year = self.sp_year.value()
        wb = build_excel_workbook(
            f"Reporte {month} {year}", _COLS, monthly_report_rows(self._records),
            title=monthly_report_title(month, year),
        )
        wb.save(path)
        QMessageBox.information(self, "Exportado", f"Reporte guardado en:\n{path}")

    def _export_pdf(self):
        if not self._records:
            return

        path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", "", "PDF Files (*.pdf)")
        if not path:
            return

        month = self.cb_month.currentText()
        year = self.sp_year.value()
        build_monthly_pdf(self._records, month, year, path)
        QMessageBox.information(self, "Exportado", f"Reporte PDF guardado en:\n{path}")
