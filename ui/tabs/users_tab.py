from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMessageBox, QHBoxLayout, QPushButton, QInputDialog, QStyle
from models.employee import User
from models.user import AuthUser
from models.shift import Shift
from PySide6.QtWidgets import QSizePolicy

class UsersTab(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.movements_tab = None  # Para evitar el warning de atributo desconocido

        from PySide6.QtWidgets import QHeaderView, QSizePolicy, QStyle
        from PySide6.QtCore import Qt
        layout = QVBoxLayout()
        self.table = QTableWidget(self)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.table, stretch=1)

        style = self.style()
        self.btn_add = QPushButton("Agregar Usuario")
        self.btn_add.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        self.btn_add.clicked.connect(self.add_user)
        layout.addWidget(self.btn_add)

        self.btn_export_excel = QPushButton("Exportar Excel")
        self.btn_export_excel.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_export_excel.clicked.connect(self.export_excel)
        layout.addWidget(self.btn_export_excel)

        self.setLayout(layout)

        # Ajuste de columnas: las dos últimas (botones) usan ResizeToContents, el resto Stretch
        def adjust_table_columns():
            col_count = self.table.columnCount()
            if col_count >= 2:
                for col in range(col_count - 2):
                    self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
                self.table.horizontalHeader().setSectionResizeMode(col_count - 2, QHeaderView.ResizeToContents)
                self.table.horizontalHeader().setSectionResizeMode(col_count - 1, QHeaderView.ResizeToContents)
            else:
                for col in range(col_count):
                    self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
            self.table.horizontalHeader().setStretchLastSection(True)
            self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.adjust_table_columns = adjust_table_columns
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.load_data()

    def export_excel(self):
        from PySide6.QtWidgets import QFileDialog
        import pandas as pd
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", "", "Excel Files (*.xlsx)")
        if path:
            users = self.session.query(User).all()
            data = []
            for user in users:
                data.append([
                    user.identifier,
                    user.first_name or "",
                    user.last_name or "",
                    "Sí" if user.is_active else "No"
                ])
            df = pd.DataFrame(data, columns=["Identificador", "Nombre", "Apellido", "Activo"])
            df.to_excel(path, index=False)
        # Layout is only defined in __init__, do not call here.

    def load_data(self):
        self.table.setSortingEnabled(False)
        users = self.session.query(User).all()
        self.table.setRowCount(len(users))
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Identificador", "Nombre", "Apellido", "Turno", "Activo", "Editar", "Eliminar"])
        for row, user in enumerate(users):
            self.table.setItem(row, 0, QTableWidgetItem(user.identifier))
            self.table.setItem(row, 1, QTableWidgetItem(user.first_name or ""))
            self.table.setItem(row, 2, QTableWidgetItem(user.last_name or ""))
            
            shift = self.session.query(Shift).filter_by(id=user.shift_id).first() if user.shift_id else None
            shift_name = shift.name if shift else "Sin Turno"
            self.table.setItem(row, 3, QTableWidgetItem(shift_name))
            
            self.table.setItem(row, 4, QTableWidgetItem("Sí" if user.is_active else "No"))
            # Botón Editar
            btn_edit = QPushButton("Editar")
            btn_edit.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
            btn_edit.clicked.connect(lambda _, u_id=user.id: self.edit_user_by_id(u_id))
            self.table.setCellWidget(row, 5, btn_edit)
            # Botón Eliminar
            btn_delete = QPushButton("Eliminar")
            btn_delete.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
            btn_delete.clicked.connect(lambda _, u_id=user.id: self.delete_user_by_id(u_id))
            self.table.setCellWidget(row, 6, btn_delete)
        self.table.setSortingEnabled(True)

    def edit_user_by_id(self, user_id):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QComboBox, QLabel, QPushButton, QHBoxLayout
        user = self.session.query(User).filter_by(id=user_id).first()
        if not user:
            QMessageBox.warning(self, "Error", "Usuario no encontrado.")
            return
        identifier = user.identifier
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Usuario")
        layout = QVBoxLayout(dialog)
        le_id = QLineEdit(user.identifier)
        le_first = QLineEdit(user.first_name or "")
        le_last = QLineEdit(user.last_name or "")
        
        cb_shift = QComboBox()
        cb_shift.addItem("Sin Turno", None)
        shifts = self.session.query(Shift).all()
        current_idx = 0
        for i, s in enumerate(shifts):
            cb_shift.addItem(s.name, s.id)
            if user.shift_id == s.id:
                current_idx = i + 1
        cb_shift.setCurrentIndex(current_idx)

        cb_active = QComboBox()
        cb_active.addItems(["Sí", "No"])
        cb_active.setCurrentIndex(0 if user.is_active else 1)
        
        layout.addWidget(QLabel("Identificador:"))
        layout.addWidget(le_id)
        layout.addWidget(QLabel("Nombre:"))
        layout.addWidget(le_first)
        layout.addWidget(QLabel("Apellido:"))
        layout.addWidget(le_last)
        layout.addWidget(QLabel("Turno Horario:"))
        layout.addWidget(cb_shift)
        layout.addWidget(QLabel("Activo:"))
        layout.addWidget(cb_active)
        
        btns = QHBoxLayout()
        btn_ok = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)
        
        def guardar():
            new_id = le_id.text()
            if new_id != identifier and self.session.query(User).filter_by(identifier=new_id).first():
                QMessageBox.warning(dialog, "Error", "El identificador ya existe.")
                return
            user.identifier = new_id
            user.first_name = le_first.text()
            user.last_name = le_last.text()
            # If both name and surname are empty, show identifier in table
            if not user.first_name.strip() and not user.last_name.strip():
                user.first_name = user.identifier
                user.last_name = ""
                
            user.shift_id = cb_shift.currentData()
            user.is_active = (cb_active.currentText() == "Sí")
            self.session.commit()
            dialog.accept()
            QMessageBox.information(self, "Usuario editado", f"Usuario actualizado a '{new_id}'.")
            self.load_data()
            
        btn_ok.clicked.connect(guardar)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def delete_user_by_id(self, user_id):
        user = self.session.query(User).filter_by(id=user_id).first()
        if not user:
            QMessageBox.warning(self, "Error", "Usuario no encontrado.")
            return
        identifier = user.identifier
        confirm = QMessageBox.question(self, "Eliminar Usuario", f"¿Eliminar usuario '{identifier}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.session.delete(user)
            self.session.commit()
            QMessageBox.information(self, "Usuario eliminado", f"Usuario '{identifier}' eliminado.")
            self.load_data()

    def add_user(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QComboBox, QLabel, QPushButton, QHBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("Agregar Usuario")
        layout = QVBoxLayout(dialog)
        le_id = QLineEdit()
        le_first = QLineEdit()
        le_last = QLineEdit()
        
        cb_shift = QComboBox()
        cb_shift.addItem("Sin Turno", None)
        shifts = self.session.query(Shift).all()
        for s in shifts:
            cb_shift.addItem(s.name, s.id)

        cb_active = QComboBox()
        cb_active.addItems(["Sí", "No"])
        
        layout.addWidget(QLabel("Identificador (Obligatorio):"))
        layout.addWidget(le_id)
        layout.addWidget(QLabel("Nombre:"))
        layout.addWidget(le_first)
        layout.addWidget(QLabel("Apellido:"))
        layout.addWidget(le_last)
        layout.addWidget(QLabel("Turno Horario:"))
        layout.addWidget(cb_shift)
        layout.addWidget(QLabel("Activo:"))
        layout.addWidget(cb_active)
        
        btns = QHBoxLayout()
        btn_ok = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)
        
        def guardar():
            identifier = le_id.text().strip()
            if not identifier:
                QMessageBox.warning(dialog, "Error", "El identificador es obligatorio.")
                return
            if self.session.query(User).filter_by(identifier=identifier).first():
                QMessageBox.warning(dialog, "Error", "El identificador ya existe.")
                return

            user = User(
                identifier=identifier, 
                first_name=le_first.text(), 
                last_name=le_last.text(), 
                is_active=(cb_active.currentText()=="Sí"),
                shift_id=cb_shift.currentData()
            )
            self.session.add(user)
            self.session.commit()
            dialog.accept()
            QMessageBox.information(self, "Usuario agregado", f"Usuario '{identifier}' creado.")
            self.load_data()
            
        btn_ok.clicked.connect(guardar)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def edit_user(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Selecciona un usuario para editar.")
            return
        item = self.table.item(row, 0)
        identifier = item.text() if item else ""
        user = self.session.query(User).filter_by(identifier=identifier).first()
        if not user:
            QMessageBox.warning(self, "Error", "Usuario no encontrado.")
            return
        # Use QInputDialog from PySide6
        new_identifier, ok = QInputDialog.getText(self, "Editar Usuario", "Nuevo identificador:", text=user.identifier)
        if not ok or not new_identifier:
            return
        if new_identifier != identifier and self.session.query(User).filter_by(identifier=new_identifier).first():
            QMessageBox.warning(self, "Error", "El identificador ya existe.")
            return
        first_name, ok = QInputDialog.getText(self, "Editar Usuario", "Nombre:", text=user.first_name or "")
        if not ok:
            return
        last_name, ok = QInputDialog.getText(self, "Editar Usuario", "Apellido:", text=user.last_name or "")
        if not ok:
            return
        activo, ok = QInputDialog.getItem(self, "Editar Usuario", "¿Activo?", ["Sí", "No"], 0 if user.is_active else 1, False)
        if not ok:
            return
        # Mostrar todos los datos actuales en el modal
        summary = f"Identificador actual: {user.identifier}\nNombre actual: {user.first_name or ''}\nApellido actual: {user.last_name or ''}\nActivo: {'Sí' if user.is_active else 'No'}"
        QMessageBox.information(self, "Datos actuales del usuario", summary)
        user.identifier = new_identifier
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = (activo=="Sí")
        self.session.commit()
        QMessageBox.information(self, "Usuario editado", f"Usuario actualizado a '{new_identifier}'.")
        self.load_data()

    def delete_user(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Selecciona un usuario para eliminar.")
            return
        item = self.table.item(row, 0)
        identifier = item.text() if item else ""
        user = self.session.query(User).filter_by(identifier=identifier).first()
        if not user:
            QMessageBox.warning(self, "Error", "Usuario no encontrado.")
            return
        confirm = QMessageBox.question(self, "Eliminar Usuario", f"¿Eliminar usuario '{identifier}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.session.delete(user)
            self.session.commit()
            QMessageBox.information(self, "Usuario eliminado", f"Usuario '{identifier}' eliminado.")
            self.load_data()