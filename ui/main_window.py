from PySide6.QtWidgets import QMainWindow, QTabWidget, QPushButton
from ui.tabs.import_tab import ImportTab
from ui.tabs.users_tab import UsersTab
from ui.tabs.movements_tab import MovementsTab
from ui.tabs.processed_tab import ProcessedTab
from ui.tabs.shifts_tab import ShiftsTab
from core.database import SessionLocal
from PySide6.QtGui import QIcon

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRTime")
        self.resize(1000, 600)
        from PySide6.QtGui import QIcon, QPixmap
        from PIL import Image
        import io
        import os
        import base64
        ICON_PNG_BASE64 = """
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
"""
        def get_icon():
            from PySide6.QtGui import QPixmap, QIcon
            png_bytes = base64.b64decode(ICON_PNG_BASE64)
            pixmap = QPixmap()
            pixmap.loadFromData(png_bytes)
            return QIcon(pixmap)
        self.setWindowIcon(get_icon())

        self.session = SessionLocal()

        tabs = QTabWidget()
        import_tab = ImportTab(self.session)
        shifts_tab = ShiftsTab(self.session)
        users_tab = UsersTab(self.session)
        movements_tab = MovementsTab(self.session)
        processed_tab = ProcessedTab(self.session)
        
        # Referencia cruzada
        users_tab.movements_tab = movements_tab
        
        tabs.addTab(import_tab, "Importar")
        tabs.addTab(shifts_tab, "Turnos Horarios")
        tabs.addTab(users_tab, "Usuarios")
        tabs.addTab(movements_tab, "Movimientos")
        tabs.addTab(processed_tab, "Asistencia Procesada")
        
        def on_tab_changed(index):
            if index == 1 and hasattr(shifts_tab, 'load_data'):
                shifts_tab.load_data()
            elif index == 2 and hasattr(users_tab, 'load_data'):
                users_tab.load_data()
            elif index == 3 and hasattr(movements_tab, 'load_data'):
                movements_tab.load_data()
            elif index == 4 and hasattr(processed_tab, 'load_data'):
                if hasattr(processed_tab, 'update_user_selector'):
                    processed_tab.update_user_selector()
                processed_tab.load_data()
                
        tabs.currentChanged.connect(on_tab_changed)
        self.setCentralWidget(tabs)

        # Menú para cambiar tema (QSS manual)
        from PySide6.QtWidgets import QMenuBar
        from PySide6.QtGui import QAction
        menubar = QMenuBar(self)
        theme_menu = menubar.addMenu("Tema")
        light_action = QAction("Claro", self)
        dark_action = QAction("Oscuro", self)
        theme_menu.addAction(light_action)
        theme_menu.addAction(dark_action)
        self.setMenuBar(menubar)

        qss_light = """
            QWidget {
                background-color: #f5f6fa;
                color: #222;
            }
            QPushButton {
                border: 2px solid #0078d7;
                border-radius: 4px;
                background-color: #e6f0fa;
                color: #222;
                padding: 6px 12px;
            }
            QPushButton:hover {
                border: 2px solid #005a9e;
                background-color: #d0e7fa;
            }
            QPushButton:pressed {
                border: 2px solid #003366;
                background-color: #b3d1ea;
            }
            QTabWidget::pane {
                border: 1px solid #b3b3b3;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #e6f0fa;
                color: #222;
                border: 1px solid #b3b3b3;
                padding: 4px;
            }
            QTableWidget {
                background-color: #fff;
                alternate-background-color: #f5f6fa;
            }
        """
        qss_dark = """
            QWidget {
                background-color: #232629;
                color: #f5f5f5;
            }
            QPushButton {
                border: 2px solid #00bcd4;
                border-radius: 4px;
                background-color: #2d333b;
                color: #f5f5f5;
                padding: 6px 12px;
            }
            QPushButton:hover {
                border: 2px solid #0097a7;
                background-color: #263238;
            }
            QPushButton:pressed {
                border: 2px solid #006064;
                background-color: #1a2327;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #2d333b;
                color: #f5f5f5;
                border: 1px solid #444;
                padding: 4px;
            }
            QTableWidget {
                background-color: #232629;
                alternate-background-color: #2d333b;
            }
        """
        def set_light():
            if self.parent() and hasattr(self.parent(), 'setStyleSheet'):
                self.parent().setStyleSheet(qss_light)
            elif hasattr(self, 'setStyleSheet'):
                self.setStyleSheet(qss_light)
        def set_dark():
            if self.parent() and hasattr(self.parent(), 'setStyleSheet'):
                self.parent().setStyleSheet(qss_dark)
            elif hasattr(self, 'setStyleSheet'):
                self.setStyleSheet(qss_dark)
        light_action.triggered.connect(set_light)
        dark_action.triggered.connect(set_dark)