import sys
import platform
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from core.init_db import init_database
from ui.main_window import MainWindow

def detect_system_theme():
    # Windows 10/11: Lee el registro para saber si el sistema está en modo oscuro
    if platform.system() == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize") as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "dark" if value == 0 else "light"
        except Exception:
            return "light"
    # macOS: Usa el comando defaults para saber el modo
    elif platform.system() == "Darwin":
        try:
            import subprocess
            result = subprocess.run([
                "defaults", "read", "-g", "AppleInterfaceStyle"
            ], capture_output=True, text=True)
            return "dark" if "Dark" in result.stdout else "light"
        except Exception:
            return "light"
    # Linux: No estándar, por defecto claro
    return "light"

if __name__ == "__main__":
    init_database()
    app.setStyle("Fusion")
    theme = detect_system_theme()
    # QSS manual para tema claro y oscuro
    qss_light = """
        QWidget { background-color: #f5f6fa; color: #222; }
        QPushButton { border: 2px solid #0078d7; border-radius: 4px; background-color: #e6f0fa; color: #222; padding: 6px 12px; }
        QPushButton:hover { border: 2px solid #005a9e; background-color: #d0e7fa; }
        QPushButton:pressed { border: 2px solid #003366; background-color: #b3d1ea; }
        QTabWidget::pane { border: 1px solid #b3b3b3; border-radius: 6px; }
        QHeaderView::section { background-color: #e6f0fa; color: #222; border: 1px solid #b3b3b3; padding: 4px; }
        QTableWidget { background-color: #fff; alternate-background-color: #f5f6fa; }
    """
    qss_dark = """
        QWidget { background-color: #232629; color: #f5f5f5; }
        QPushButton { border: 2px solid #00bcd4; border-radius: 4px; background-color: #2d333b; color: #f5f5f5; padding: 6px 12px; }
        QPushButton:hover { border: 2px solid #0097a7; background-color: #263238; }
        QPushButton:pressed { border: 2px solid #006064; background-color: #1a2327; }
        QTabWidget::pane { border: 1px solid #444; border-radius: 6px; }
        QHeaderView::section { background-color: #2d333b; color: #f5f5f5; border: 1px solid #444; padding: 4px; }
        QTableWidget { background-color: #232629; alternate-background-color: #2d333b; }
    """
    app.setStyleSheet(qss_dark if theme == "dark" else qss_light)

    # Ventana de login
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
    from sqlalchemy.orm import Session
    from core.security import verify_password, hash_password
    from models.user import AuthUser
    from PySide6.QtGui import QIcon, QPixmap, QFont
    from PySide6.QtCore import Qt
    import base64
    ICON_PNG_BASE64 = """
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
    """
    def get_icon():
        import io
        from PySide6.QtGui import QPixmap, QIcon
        png_bytes = base64.b64decode(ICON_PNG_BASE64)
        pixmap = QPixmap()
        pixmap.loadFromData(png_bytes)
        return QIcon(pixmap)

    app.setWindowIcon(get_icon())

    class LoginDialog(QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("SRTime - Login")
            self.setWindowIcon(get_icon())
            self.accepted_user = None
            self.setModal(True)
            self.setFixedWidth(380)
            self.setSizeGripEnabled(False)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(8)

            logo_label = QLabel()
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setPixmap(get_icon().pixmap(64, 64))
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
            subtitle_label.setObjectName("loginSubtitle")
            layout.addWidget(subtitle_label)

            layout.addSpacing(10)

            layout.addWidget(QLabel("Usuario:"))
            self.user_input = QLineEdit()
            self.user_input.setPlaceholderText("admin")
            self.user_input.setClearButtonEnabled(True)
            layout.addWidget(self.user_input)

            layout.addWidget(QLabel("Contraseña:"))
            self.pass_input = QLineEdit()
            self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.pass_input.setPlaceholderText("••••••")
            layout.addWidget(self.pass_input)

            self.error_label = QLabel("")
            self.error_label.setObjectName("loginError")
            self.error_label.setWordWrap(True)
            self.error_label.setVisible(False)
            layout.addWidget(self.error_label)

            self.btn_login = QPushButton("Iniciar Sesión")
            self.btn_login.setObjectName("loginButton")
            self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(self.btn_login)
            self.btn_login.clicked.connect(self.try_login)
            self.pass_input.returnPressed.connect(self.try_login)
            self.user_input.returnPressed.connect(self.pass_input.setFocus)
            self.error_label.setStyleSheet(
                "padding: 6px 8px; border-radius: 4px;"
                + ("background-color: #4a1f1f; color: #ffb3b3; border: 1px solid #7a2e2e;" if theme == "dark" else "background-color: #fdeaea; color: #8a1f1f; border: 1px solid #d9a3a3;")
            )
            self.user_input.setFocus()

        def show_error(self, message):
            self.error_label.setText(message)
            self.error_label.setVisible(bool(message))

        def try_login(self):
            self.show_error("")
            self.btn_login.setEnabled(False)
            self.btn_login.setText("Iniciando sesión...")
            from core.database import SessionLocal
            session = SessionLocal()
            from models.user import AuthUser
            from core.security import verify_password
            user = session.query(AuthUser).filter_by(username=self.user_input.text()).first()
            # Si user es None, no hay usuario
            if user and hasattr(user, 'password_hash') and isinstance(user.password_hash, str) and verify_password(self.pass_input.text(), user.password_hash):
                if not user.is_active:
                    self.show_error("La cuenta está inactiva.")
                    self.btn_login.setEnabled(True)
                    self.btn_login.setText("Iniciar Sesión")
                    session.close()
                    return

                entered_password = self.pass_input.text()
                is_default_admin_login = user.username == "admin" and entered_password == "admin"
                if bool(getattr(user, "must_change_password", False)) or is_default_admin_login:
                    dlg = QDialog(self)
                    dlg.setWindowTitle("Cambiar contraseña")
                    lyt = QVBoxLayout(dlg)
                    lyt.addWidget(QLabel("Debes cambiar la contraseña por seguridad."))
                    lyt.addWidget(QLabel("Nueva contraseña:"))
                    new_pass = QLineEdit()
                    new_pass.setEchoMode(QLineEdit.EchoMode.Password)
                    lyt.addWidget(new_pass)
                    lyt.addWidget(QLabel("Confirmar contraseña:"))
                    confirm_pass = QLineEdit()
                    confirm_pass.setEchoMode(QLineEdit.EchoMode.Password)
                    lyt.addWidget(confirm_pass)
                    btns = QVBoxLayout()
                    btn_ok = QPushButton("Guardar")
                    btn_cancel = QPushButton("Cancelar")
                    btns.addWidget(btn_ok)
                    btns.addWidget(btn_cancel)
                    lyt.addLayout(btns)

                    def save_new_password():
                        p1 = new_pass.text()
                        p2 = confirm_pass.text()
                        if len(p1) < 6:
                            QMessageBox.warning(dlg, "Error", "La contraseña debe tener al menos 6 caracteres.")
                            return
                        if p1 != p2:
                            QMessageBox.warning(dlg, "Error", "Las contraseñas no coinciden.")
                            return
                        user.password_hash = hash_password(p1)
                        user.must_change_password = False
                        session.commit()
                        dlg.accept()

                    btn_ok.clicked.connect(save_new_password)
                    btn_cancel.clicked.connect(dlg.reject)

                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        self.btn_login.setEnabled(True)
                        self.btn_login.setText("Iniciar Sesión")
                        session.close()
                        return

                self.accepted_user = {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role or "viewer",
                }
                self.accept()
            else:
                self.show_error("Usuario o contraseña incorrectos")
                self.btn_login.setEnabled(True)
                self.btn_login.setText("Iniciar Sesión")
            session.close()

    login = LoginDialog()
    if login.exec() == QDialog.DialogCode.Accepted:
        window = MainWindow(login.accepted_user)
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)