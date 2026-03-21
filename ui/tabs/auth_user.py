from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QPushButton,
    QDialog,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QComboBox,
    QHeaderView,
    QStyle,
)
from core.security import hash_password
from models.user import AuthUser


ROLES = ["root", "admin", "supervisor", "viewer"]


class AuthUserTab(QWidget):
    def __init__(self, session, current_auth_user=None):
        super().__init__()
        self.session = session
        self.current_auth_user = current_auth_user or {}
        self.current_username = self.current_auth_user.get("username", "")
        self.is_root = self.current_auth_user.get("role") == "root"

        layout = QVBoxLayout(self)

        self.table = QTableWidget(self)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        style = self.style()
        self.btn_add = QPushButton("Agregar Cuenta")
        self.btn_add.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.btn_add.clicked.connect(self.add_auth_user)
        self.btn_add.setEnabled(self.is_root)
        layout.addWidget(self.btn_add)

        self.load_data()

    def load_data(self):
        users = self.session.query(AuthUser).order_by(AuthUser.username.asc()).all()
        self.table.setRowCount(len(users))
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Usuario",
            "Rol",
            "Activo",
            "Creado",
            "Editar",
            "Eliminar",
        ])

        for row, user in enumerate(users):
            self.table.setItem(row, 0, QTableWidgetItem(user.username))
            self.table.setItem(row, 1, QTableWidgetItem(user.role or "admin"))
            self.table.setItem(row, 2, QTableWidgetItem("Sí" if user.is_active else "No"))
            created = user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else ""
            self.table.setItem(row, 3, QTableWidgetItem(created))

            btn_edit = QPushButton("Editar")
            btn_edit.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
            btn_edit.clicked.connect(lambda _, u_id=user.id: self.edit_auth_user(u_id))
            self.table.setCellWidget(row, 4, btn_edit)

            btn_delete = QPushButton("Eliminar")
            btn_delete.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
            btn_delete.clicked.connect(lambda _, u_id=user.id: self.delete_auth_user(u_id))
            self.table.setCellWidget(row, 5, btn_delete)

    def add_auth_user(self):
        if not self.is_root:
            QMessageBox.warning(self, "Acceso denegado", "Solo root puede crear cuentas autorizadas.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Agregar Cuenta")
        layout = QVBoxLayout(dialog)

        le_user = QLineEdit()
        le_pass = QLineEdit()
        le_pass.setEchoMode(QLineEdit.EchoMode.Password)

        cb_role = QComboBox()
        cb_role.addItems(ROLES)

        cb_active = QComboBox()
        cb_active.addItems(["Sí", "No"])

        layout.addWidget(QLabel("Usuario:"))
        layout.addWidget(le_user)
        layout.addWidget(QLabel("Contraseña:"))
        layout.addWidget(le_pass)
        layout.addWidget(QLabel("Rol:"))
        layout.addWidget(cb_role)
        layout.addWidget(QLabel("Activo:"))
        layout.addWidget(cb_active)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        def save():
            username = le_user.text().strip()
            password = le_pass.text()
            role = cb_role.currentText()
            is_active = cb_active.currentText() == "Sí"

            if not username:
                QMessageBox.warning(dialog, "Error", "El usuario es obligatorio.")
                return
            if not password:
                QMessageBox.warning(dialog, "Error", "La contraseña es obligatoria.")
                return
            if len(password) < 6:
                QMessageBox.warning(dialog, "Error", "La contraseña debe tener al menos 6 caracteres.")
                return
            if self.session.query(AuthUser).filter_by(username=username).first():
                QMessageBox.warning(dialog, "Error", "Ese usuario ya existe.")
                return

            new_user = AuthUser(
                username=username,
                password_hash=hash_password(password),
                role=role,
                is_active=is_active,
            )
            self.session.add(new_user)
            self.session.commit()
            dialog.accept()
            self.load_data()

        btn_ok.clicked.connect(save)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def edit_auth_user(self, user_id: int):
        user = self.session.query(AuthUser).filter_by(id=user_id).first()
        if not user:
            QMessageBox.warning(self, "Error", "Cuenta no encontrada.")
            return

        if not self.is_root and user.username != self.current_username:
            QMessageBox.warning(self, "Acceso denegado", "No puedes modificar otras cuentas.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Cuenta")
        layout = QVBoxLayout(dialog)

        le_user = QLineEdit(user.username)
        le_pass = QLineEdit()
        le_pass.setEchoMode(QLineEdit.EchoMode.Password)
        le_pass.setPlaceholderText("Dejar vacío para no cambiar")

        cb_role = QComboBox()
        cb_role.addItems(ROLES)
        role_idx = ROLES.index(user.role) if user.role in ROLES else 0
        cb_role.setCurrentIndex(role_idx)
        cb_role.setEnabled(self.is_root)

        cb_active = QComboBox()
        cb_active.addItems(["Sí", "No"])
        cb_active.setCurrentIndex(0 if user.is_active else 1)
        cb_active.setEnabled(self.is_root)

        layout.addWidget(QLabel("Usuario:"))
        layout.addWidget(le_user)
        layout.addWidget(QLabel("Nueva contraseña (opcional):"))
        layout.addWidget(le_pass)
        layout.addWidget(QLabel("Rol:"))
        layout.addWidget(cb_role)
        layout.addWidget(QLabel("Activo:"))
        layout.addWidget(cb_active)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        def save():
            new_username = le_user.text().strip()
            if not new_username:
                QMessageBox.warning(dialog, "Error", "El usuario es obligatorio.")
                return

            existing = self.session.query(AuthUser).filter(AuthUser.username == new_username, AuthUser.id != user_id).first()
            if existing:
                QMessageBox.warning(dialog, "Error", "Ese usuario ya existe.")
                return

            user.username = new_username
            if self.is_root:
                user.role = cb_role.currentText()
                user.is_active = cb_active.currentText() == "Sí"

            new_pass = le_pass.text()
            if new_pass:
                if len(new_pass) < 6:
                    QMessageBox.warning(dialog, "Error", "La contraseña debe tener al menos 6 caracteres.")
                    return
                user.password_hash = hash_password(new_pass)

            self.session.commit()
            dialog.accept()
            self.load_data()

        btn_ok.clicked.connect(save)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def delete_auth_user(self, user_id: int):
        if not self.is_root:
            QMessageBox.warning(self, "Acceso denegado", "Solo root puede eliminar cuentas.")
            return

        user = self.session.query(AuthUser).filter_by(id=user_id).first()
        if not user:
            QMessageBox.warning(self, "Error", "Cuenta no encontrada.")
            return

        if user.role == "root":
            roots_count = self.session.query(AuthUser).filter_by(role="root").count()
            if roots_count <= 1:
                QMessageBox.warning(self, "Bloqueado", "Debe existir al menos una cuenta root.")
                return

        confirm = QMessageBox.question(
            self,
            "Eliminar Cuenta",
            f"¿Eliminar cuenta '{user.username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.session.delete(user)
            self.session.commit()
            self.load_data()
