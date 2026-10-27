"""Desktop first-run dialog; mirrors the Web "Configuración inicial" wizard.

All rules live in ``services.setup_service``; this dialog only collects input.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import core.database as database
from services import setup_service
from services.setup_service import SetupError

PASSWORD_RULES = "Al menos 8 caracteres, con una letra y un número; sin caracteres especiales."


class SetupDialog(QDialog):
    """Create/connect the database (PostgreSQL only) and the initial admin."""

    def __init__(self, icon: QIcon, error_style: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SRTime - Configuración inicial")
        self.setWindowIcon(icon)
        self.setModal(True)
        self.setFixedWidth(420)
        self.accepted_user = None
        self.engine_name = setup_service.database_engine()
        self.database_ready = setup_service.is_database_configured()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setPixmap(icon.pixmap(64, 64))
        layout.addWidget(logo_label)

        title_label = QLabel("SRTime")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        subtitle_label = QLabel("Sistema de Control de Asistencias")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_label)
        layout.addSpacing(10)

        intro = QLabel(
            "SRTime creará la base local en este equipo. Definí el usuario inicial para comenzar."
            if self.engine_name == "sqlite"
            else "Primero creá o conectá la base de datos. Luego definí el usuario inicial de SRTime."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Paso 1: base de datos. Sólo PostgreSQL necesita datos de conexión.
        self.database_box = QGroupBox("Base de datos")
        database_layout = QVBoxLayout(self.database_box)
        self.database_form = QWidget()
        form = QFormLayout(self.database_form)
        form.setContentsMargins(0, 0, 0, 0)
        # Valores propuestos desde el perfil local; la base sólo se crea si el
        # operador confirma.
        suggested = setup_service.suggested_connection()
        self.db_host = QLineEdit(suggested["db_host"])
        self.db_port = QSpinBox()
        self.db_port.setRange(1, 65535)
        self.db_port.setValue(suggested["db_port"])
        self.db_user = QLineEdit(suggested["db_user"])
        self.db_password = QLineEdit()
        self.db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_name = QLineEdit(suggested["db_name"])
        form.addRow("Servidor PostgreSQL:", self.db_host)
        form.addRow("Puerto:", self.db_port)
        form.addRow("Usuario PostgreSQL:", self.db_user)
        form.addRow("Contraseña PostgreSQL:", self.db_password)
        form.addRow("Base de datos:", self.db_name)
        database_layout.addWidget(self.database_form)
        self.btn_database = QPushButton("Crear base de datos")
        self.btn_database.clicked.connect(self.create_database)
        database_layout.addWidget(self.btn_database)
        self.database_status = QLabel()
        self.database_status.setWordWrap(True)
        database_layout.addWidget(self.database_status)
        layout.addWidget(self.database_box)

        # Paso 2: administrador inicial, siempre "admin" con rol root.
        self.admin_box = QGroupBox("Administrador")
        admin_layout = QVBoxLayout(self.admin_box)
        admin_layout.addWidget(QLabel("Usuario inicial de SRTime:"))
        admin_user = QLineEdit(setup_service.INITIAL_ADMIN_USERNAME)
        admin_user.setEnabled(False)
        admin_layout.addWidget(admin_user)
        self.admin_hint = QLabel()
        self.admin_hint.setObjectName("loginSubtitle")
        self.admin_hint.setWordWrap(True)
        admin_layout.addWidget(self.admin_hint)
        admin_layout.addWidget(QLabel("Contraseña para el usuario admin:"))
        self.admin_password = QLineEdit()
        self.admin_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_password.setToolTip(PASSWORD_RULES)
        admin_layout.addWidget(self.admin_password)
        admin_layout.addWidget(QLabel("Confirmar contraseña:"))
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setToolTip(PASSWORD_RULES)
        admin_layout.addWidget(self.confirm_password)
        rules = QLabel(PASSWORD_RULES)
        rules.setWordWrap(True)
        admin_layout.addWidget(rules)
        self.match_label = QLabel()
        admin_layout.addWidget(self.match_label)
        layout.addWidget(self.admin_box)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        self.error_label.setStyleSheet(error_style)
        layout.addWidget(self.error_label)

        self.btn_admin = QPushButton("Crear administrador e iniciar")
        self.btn_admin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_admin.clicked.connect(self.create_admin)
        layout.addWidget(self.btn_admin)

        self.admin_password.textChanged.connect(self.refresh_state)
        self.confirm_password.textChanged.connect(self.refresh_state)
        self.confirm_password.returnPressed.connect(self.create_admin)
        self.refresh_state()

    def passwords_match(self) -> bool:
        password = self.admin_password.text()
        confirmation = self.confirm_password.text()
        return bool(password) and bool(confirmation) and password == confirmation

    def refresh_state(self) -> None:
        if self.engine_name == "sqlite":
            self.database_form.setVisible(False)
            self.btn_database.setVisible(False)
            self.database_status.setText("Base local lista para inicializar.")
            self.admin_hint.setText("Administrador de la base local de este equipo.")
        elif self.database_ready:
            self.database_form.setEnabled(False)
            self.btn_database.setVisible(False)
            self.database_status.setText("Conexión y esquema de la base listos. Ahora creá el administrador de SRTime.")
            self.admin_hint.setText("")
        else:
            self.database_status.setText("")
            self.admin_hint.setText("Disponible luego de crear la base de datos.")
        self.admin_password.setEnabled(self.database_ready)
        self.confirm_password.setEnabled(self.database_ready)

        confirmation = self.confirm_password.text()
        if confirmation and not self.passwords_match():
            self.match_label.setText("Las contraseñas no coinciden.")
        elif self.passwords_match():
            self.match_label.setText("Las contraseñas coinciden.")
        else:
            self.match_label.setText("")
        self.btn_admin.setEnabled(self.database_ready and self.passwords_match())

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def create_database(self) -> None:
        self.show_error("")
        self.btn_database.setEnabled(False)
        self.btn_database.setText("Creando...")
        try:
            setup_service.configure_postgres(
                self.db_host.text(), self.db_port.value(), self.db_user.text(),
                self.db_password.text(), self.db_name.text().strip(),
            )
        except SetupError as exc:
            self.show_error(exc.message)
        else:
            self.database_ready = True
        finally:
            self.btn_database.setEnabled(True)
            self.btn_database.setText("Crear base de datos")
        self.refresh_state()

    def create_admin(self) -> None:
        if not self.btn_admin.isEnabled():
            return
        self.show_error("")
        self.btn_admin.setEnabled(False)
        self.btn_admin.setText("Creando...")
        try:
            # SessionLocal is re-bound by configure_postgres when step 1 ran.
            with database.SessionLocal() as session:
                admin = setup_service.create_initial_admin(
                    session, self.admin_password.text(), self.confirm_password.text()
                )
                # Igual que la Web: al crear el administrador se inicia sesión.
                self.accepted_user = {"id": admin.id, "username": admin.username, "role": admin.role}
        except SetupError as exc:
            self.show_error(exc.message)
            self.btn_admin.setText("Crear administrador e iniciar")
            self.refresh_state()
            return
        self.accept()
