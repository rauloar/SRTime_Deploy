from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QComboBox, QSpinBox, QFileDialog,
    QMessageBox, QStyle
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from datetime import date

from services.reports import aggregate_monthly, build_monthly_pdf, get_month_name
from services.constants import MONTH_NAMES
from services.export_helpers import build_excel_workbook

_MONTHS = MONTH_NAMES[1:]

_COLS = [
    "Empleado", "Días con registro", "Días OK",
    "Días incompleto", "Días justificado",
    "Min. tardanza", "Min. horas extra", "Horas trabajadas"
]


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
            self.table.setItem(row, 0, QTableWidgetItem(rec["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(str(rec["total"])))
            self.table.setItem(row, 2, QTableWidgetItem(str(rec["ok"])))
            self.table.setItem(row, 3, QTableWidgetItem(str(rec["incomplete"])))
            self.table.setItem(row, 4, QTableWidgetItem(str(rec["justified"])))
            self.table.setItem(row, 5, QTableWidgetItem(str(rec["tardiness_minutes"])))
            self.table.setItem(row, 6, QTableWidgetItem(str(rec["overtime_minutes"])))
            self.table.setItem(row, 7, QTableWidgetItem(f"{rec['total_hours']:.2f}"))

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
        data_rows = [
            [r["name"], r["total"], r["ok"], r["incomplete"],
             r["justified"], r["tardiness_minutes"],
             r["overtime_minutes"], r["total_hours"]]
            for r in self._records
        ]
        title = f"Reporte de Asistencia — {month} {year}"
        wb = build_excel_workbook(f"Reporte {month} {year}", _COLS, data_rows, title=title)
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
