from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QStyle, QInputDialog, QDialog, QLineEdit, QLabel, QTimeEdit)
from PySide6.QtCore import Qt, QTime
from sqlalchemy.orm import Session
from models.shift import Shift
from models.employee import User
from datetime import time

class ShiftsTab(QWidget):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session

        layout = QVBoxLayout(self)

        # Botón agregar
        self.btn_add = QPushButton("Nuevo Turno")
        self.btn_add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.btn_add.clicked.connect(self.add_shift)
        layout.addWidget(self.btn_add)

        # Tabla de turnos
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def load_data(self):
        shifts = self.session.query(Shift).all()
        self.table.clearContents()
        self.table.setRowCount(len(shifts))
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre del Turno", "Entrada Esperada", "Salida Esperada", "Tolerancia (Min)","Acciones"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for row, shift in enumerate(shifts):
            self.table.setItem(row, 0, QTableWidgetItem(str(shift.id)))
            self.table.setItem(row, 1, QTableWidgetItem(shift.name))
            self.table.setItem(row, 2, QTableWidgetItem(shift.expected_in.strftime("%H:%M") if shift.expected_in else ""))
            self.table.setItem(row, 3, QTableWidgetItem(shift.expected_out.strftime("%H:%M") if shift.expected_out else ""))
            self.table.setItem(row, 4, QTableWidgetItem(str(shift.grace_period_minutes)))
            
            btn_panel = QWidget()
            btn_layout = QHBoxLayout(btn_panel)
            btn_layout.setContentsMargins(0,0,0,0)
            
            btn_edit = QPushButton("Editar")
            btn_edit.clicked.connect(lambda _, s_id=shift.id: self.edit_shift(s_id))
            
            btn_del = QPushButton("Eliminar")
            btn_del.clicked.connect(lambda _, s_id=shift.id: self.delete_shift(s_id))
            
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_del)
            self.table.setCellWidget(row, 5, btn_panel)

    def add_shift(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Crear Nuevo Turno")
        layout = QVBoxLayout(dialog)

        le_name = QLineEdit()
        te_in = QTimeEdit()
        te_in.setDisplayFormat("HH:mm")
        te_out = QTimeEdit()
        te_out.setDisplayFormat("HH:mm")
        le_grace = QLineEdit("15")

        layout.addWidget(QLabel("Nombre del Turno (ej: Mañana):"))
        layout.addWidget(le_name)
        layout.addWidget(QLabel("Hora de Entrada:"))
        layout.addWidget(te_in)
        layout.addWidget(QLabel("Hora de Salida:"))
        layout.addWidget(te_out)
        layout.addWidget(QLabel("Minutos de Tolerancia (Tardanza):"))
        layout.addWidget(le_grace)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        def save():
            name = le_name.text().strip()
            if not name:
                QMessageBox.warning(self, "Error", "El nombre del turno es obligatorio.")
                return
            try:
                grace = int(le_grace.text())
            except ValueError:
                QMessageBox.warning(self, "Error", "La tolerancia debe ser un número entero de minutos.")
                return

            # Convert QTime to Python time
            qt_in = te_in.time()
            qt_out = te_out.time()
            
            shift = Shift(
                name=name,
                expected_in=time(qt_in.hour(), qt_in.minute()),
                expected_out=time(qt_out.hour(), qt_out.minute()),
                grace_period_minutes=grace
            )
            self.session.add(shift)
            self.session.flush()

            # New shifts become the default shift for all employees.
            self.session.query(User).update({User.shift_id: shift.id})

            self.session.commit()
            dialog.accept()
            self.load_data()

        btn_ok.clicked.connect(save)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def edit_shift(self, shift_id):
        shift = self.session.query(Shift).filter_by(id=shift_id).first()
        if not shift: return

        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Turno")
        layout = QVBoxLayout(dialog)

        le_name = QLineEdit(shift.name)
        
        te_in = QTimeEdit()
        te_in.setDisplayFormat("HH:mm")
        if shift.expected_in:
            te_in.setTime(QTime(shift.expected_in.hour, shift.expected_in.minute))
            
        te_out = QTimeEdit()
        te_out.setDisplayFormat("HH:mm")
        if shift.expected_out:
            te_out.setTime(QTime(shift.expected_out.hour, shift.expected_out.minute))
            
        le_grace = QLineEdit(str(shift.grace_period_minutes))

        layout.addWidget(QLabel("Nombre del Turno:"))
        layout.addWidget(le_name)
        layout.addWidget(QLabel("Hora de Entrada:"))
        layout.addWidget(te_in)
        layout.addWidget(QLabel("Hora de Salida:"))
        layout.addWidget(te_out)
        layout.addWidget(QLabel("Minutos de Tolerancia (Tardanza):"))
        layout.addWidget(le_grace)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Guardar Cambios")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        def save():
            name = le_name.text().strip()
            if not name:
                QMessageBox.warning(self, "Error", "El nombre del turno es obligatorio.")
                return
            try:
                grace = int(le_grace.text())
            except ValueError:
                QMessageBox.warning(self, "Error", "La tolerancia debe ser un número entero de minutos.")
                return

            qt_in = te_in.time()
            qt_out = te_out.time()
            
            shift.name = name
            shift.expected_in = time(qt_in.hour(), qt_in.minute())
            shift.expected_out = time(qt_out.hour(), qt_out.minute())
            shift.grace_period_minutes = grace
            
            self.session.commit()
            dialog.accept()
            self.load_data()

        btn_ok.clicked.connect(save)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def delete_shift(self, shift_id):
        shift = self.session.query(Shift).filter_by(id=shift_id).first()
        if not shift: return
        
        confirm = QMessageBox.question(self, "Eliminar Turno", f"¿Estás seguro de eliminar el turno '{shift.name}'?\nEsto podría afectar los cálculos de los empleados que lo tengan asignado.", 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.session.delete(shift)
            self.session.commit()
            self.load_data()
