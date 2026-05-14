from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QFormLayout, QLabel, QLineEdit,
    QDateEdit, QCheckBox, QMessageBox, QStyle
)
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session
from datetime import date


class HolidaysTab(QWidget):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        btn_bar = QHBoxLayout()
        self.btn_add = QPushButton("Nuevo Feriado")
        self.btn_add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.btn_add.clicked.connect(self._add_holiday)
        btn_bar.addWidget(self.btn_add)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

    def load_data(self):
        from models.holiday import Holiday
        holidays = self.session.query(Holiday).order_by(Holiday.date).all()

        self.table.clearContents()
        self.table.setRowCount(len(holidays))
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Fecha", "Nombre", "Repite anualmente", "Acciones"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for row, h in enumerate(holidays):
            self.table.setItem(row, 0, QTableWidgetItem(h.date.strftime("%d/%m/%Y")))
            self.table.setItem(row, 1, QTableWidgetItem(h.name))
            self.table.setItem(row, 2, QTableWidgetItem("Sí" if h.is_recurring else "No"))

            btn_panel = QWidget()
            btn_layout = QHBoxLayout(btn_panel)
            btn_layout.setContentsMargins(2, 2, 2, 2)

            btn_edit = QPushButton("Editar")
            btn_edit.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
            btn_edit.clicked.connect(lambda _, hid=h.id: self._edit_holiday(hid))

            btn_del = QPushButton("Eliminar")
            btn_del.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
            btn_del.clicked.connect(lambda _, hid=h.id: self._delete_holiday(hid))

            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_del)
            self.table.setCellWidget(row, 3, btn_panel)

    def _holiday_dialog(self, title: str, h=None) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QFormLayout(dialog)

        de_date = QDateEdit()
        de_date.setCalendarPopup(True)
        de_date.setDisplayFormat("dd/MM/yyyy")
        if h:
            de_date.setDate(QDate(h.date.year, h.date.month, h.date.day))
        else:
            de_date.setDate(QDate.currentDate())

        le_name = QLineEdit(h.name if h else "")
        chk_recurring = QCheckBox()
        chk_recurring.setChecked(h.is_recurring if h else False)

        layout.addRow("Fecha:", de_date)
        layout.addRow("Nombre:", le_name)
        layout.addRow("Repite anualmente:", chk_recurring)

        btn_bar = QHBoxLayout()
        btn_save = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btn_bar.addWidget(btn_save)
        btn_bar.addWidget(btn_cancel)
        layout.addRow(btn_bar)

        dialog._de_date = de_date
        dialog._le_name = le_name
        dialog._chk_recurring = chk_recurring
        btn_save.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        return dialog

    def _add_holiday(self):
        from models.holiday import Holiday
        dlg = self._holiday_dialog("Nuevo Feriado")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        name = dlg._le_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            return

        qd = dlg._de_date.date()
        d = date(qd.year(), qd.month(), qd.day())

        if self.session.query(Holiday).filter_by(date=d).first():
            QMessageBox.warning(self, "Error", f"Ya existe un feriado en la fecha {d.strftime('%d/%m/%Y')}.")
            return

        self.session.add(Holiday(date=d, name=name, is_recurring=dlg._chk_recurring.isChecked()))
        self.session.commit()
        self.load_data()

    def _edit_holiday(self, hid: int):
        from models.holiday import Holiday
        h = self.session.query(Holiday).filter_by(id=hid).first()
        if not h:
            return

        dlg = self._holiday_dialog("Editar Feriado", h)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        name = dlg._le_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            return

        qd = dlg._de_date.date()
        new_date = date(qd.year(), qd.month(), qd.day())

        conflict = self.session.query(Holiday).filter(
            Holiday.date == new_date, Holiday.id != hid
        ).first()
        if conflict:
            QMessageBox.warning(self, "Error", f"Ya existe otro feriado en {new_date.strftime('%d/%m/%Y')}.")
            return

        h.date = new_date
        h.name = name
        h.is_recurring = dlg._chk_recurring.isChecked()
        self.session.commit()
        self.load_data()

    def _delete_holiday(self, hid: int):
        from models.holiday import Holiday
        h = self.session.query(Holiday).filter_by(id=hid).first()
        if not h:
            return
        confirm = QMessageBox.question(
            self, "Eliminar Feriado",
            f"¿Eliminar '{h.name}' ({h.date.strftime('%d/%m/%Y')})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.session.delete(h)
            self.session.commit()
            self.load_data()
