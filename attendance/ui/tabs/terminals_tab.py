import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QDialog, QFormLayout, 
    QLineEdit, QComboBox, QCheckBox, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from models.terminal import DeviceTerminal
import services.addons

class TerminalDialog(QDialog):
    def __init__(self, parent=None, terminal=None):
        super().__init__(parent)
        self.terminal = terminal
        self.setWindowTitle("Registrar Terminal" if not terminal else "Editar Terminal")
        self.resize(350, 250)

        layout = QFormLayout(self)
        
        self.name_edit = QLineEdit(terminal.name if terminal else "")
        self.ip_edit = QLineEdit(terminal.ip if terminal else "192.168.1.201")
        self.port_edit = QLineEdit(str(terminal.port) if terminal else "4370")
        self.password_edit = QLineEdit(terminal.password if terminal else "0")
        
        self.active_check = QCheckBox()
        self.active_check.setChecked(terminal.is_active if terminal is not None else True)

        self.driver_combo = QComboBox()
        addons = services.addons.get_available_parsers()
        self.driver_list = []
        for name, info in addons.items():
            if info.get("is_driver"):
                self.driver_list.append(name)
                self.driver_combo.addItem(name)
                
        if terminal and terminal.driver_name in self.driver_list:
            self.driver_combo.setCurrentText(terminal.driver_name)
        elif "ZKTeco" in self.driver_list:
            self.driver_combo.setCurrentText("ZKTeco")

        layout.addRow("Ubicación / Nombre:", self.name_edit)
        layout.addRow("Tecnología (Driver):", self.driver_combo)
        layout.addRow("Dirección IP / Host:", self.ip_edit)
        layout.addRow("Puerto Red:", self.port_edit)
        layout.addRow("Contraseña / ComKey:", self.password_edit)
        layout.addRow("Equipo Activo:", self.active_check)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Guardar Equipo")
        save_btn.setStyleSheet("font-weight: bold; background-color: #0078d7; color: white;")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        layout.addRow("", btn_layout)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "driver_name": self.driver_combo.currentText(),
            "ip": self.ip_edit.text().strip(),
            "port": int(self.port_edit.text().strip() or "4370"),
            "password": self.password_edit.text().strip() or "0",
            "is_active": self.active_check.isChecked()
        }


class TerminalsTab(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        layout = QVBoxLayout(self)
        
        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualizar Lista")
        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_add = QPushButton("+ Registrar Terminal")
        self.btn_add.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        self.btn_add.clicked.connect(self.add_terminal)
        
        toolbar.addWidget(self.btn_refresh)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_add)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "IP", "Driver", "Estado", "Sincronizado", "Conexión", "Acciones"
        ])
        
        header = self.table.horizontalHeader()
        if hasattr(QHeaderView, "ResizeMode"):
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(1, QHeaderView.Stretch)
            
        layout.addWidget(self.table)
        self.load_data()

    def get_driver_instance(self, driver_name):
        info = services.addons.get_addon_info(driver_name)
        if not info or not info.get("is_driver"): return None
        return info["class"]()

    def load_data(self):
        self.table.setRowCount(0)
        from sqlalchemy import asc
        terminals = self.session.query(DeviceTerminal).order_by(asc(DeviceTerminal.id)).all()
        
        for row, t in enumerate(terminals):
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(str(t.id)))
            self.table.setItem(row, 1, QTableWidgetItem(t.name))
            self.table.setItem(row, 2, QTableWidgetItem(f"{t.ip}:{t.port}"))
            self.table.setItem(row, 3, QTableWidgetItem(t.driver_name))
            
            estado = "Activo" if t.is_active else "Inactivo"
            self.table.setItem(row, 4, QTableWidgetItem(estado))
            
            last_sync = t.last_sync.strftime('%Y-%m-%d %H:%M:%S') if t.last_sync else "Nunca"
            self.table.setItem(row, 5, QTableWidgetItem(last_sync))
            
            # --- Panel Acciones PING / SYNC ---
            act_pane = QWidget()
            h = QHBoxLayout(act_pane)
            h.setContentsMargins(2,2,2,2)
            btn_ping = QPushButton("Píng")
            btn_ping.clicked.connect(lambda _, t_id=t.id: self.ping_terminal(t_id))
            btn_sync = QPushButton("Reloj")
            btn_sync.clicked.connect(lambda _, t_id=t.id: self.sync_terminal(t_id))
            
            if not t.is_active:
                btn_ping.setEnabled(False)
                btn_sync.setEnabled(False)

            h.addWidget(btn_ping)
            h.addWidget(btn_sync)
            self.table.setCellWidget(row, 6, act_pane)
            
            # --- Panel Config Edit/Delete ---
            cfg_pane = QWidget()
            h2 = QHBoxLayout(cfg_pane)
            h2.setContentsMargins(2,2,2,2)
            btn_edit = QPushButton("Editar")
            btn_edit.clicked.connect(lambda _, t_id=t.id: self.edit_terminal(t_id))
            btn_del = QPushButton("Borrar")
            btn_del.setStyleSheet("color: #d32f2f;")
            btn_del.clicked.connect(lambda _, t_id=t.id: self.delete_terminal(t_id))
            h2.addWidget(btn_edit)
            h2.addWidget(btn_del)
            self.table.setCellWidget(row, 7, cfg_pane)
            
        self.table.resizeColumnToContents(6)
        self.table.resizeColumnToContents(7)

    def ping_terminal(self, t_id):
        terminal = self.session.query(DeviceTerminal).get(t_id)
        if not terminal: return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            driver = self.get_driver_instance(terminal.driver_name)
            if not driver: raise Exception("Driver no encontrado")
            
            params = {"ip": terminal.ip, "port": str(terminal.port), "password": terminal.password}
            res = driver.test_connection(params)
            
            sn = res.get('serial_number') or res.get('mac')
            if sn and not terminal.serial_number:
                terminal.serial_number = sn
                self.session.commit()
            
            QMessageBox.information(self, "Conexión Exitosa", f"Terminal OK.\nMAC/SN: {sn}\nHora: {res.get('time')}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al conectar:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def sync_terminal(self, t_id):
        terminal = self.session.query(DeviceTerminal).get(t_id)
        if not terminal: return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            driver = self.get_driver_instance(terminal.driver_name)
            if not driver: raise Exception("Driver no encontrado")
            
            params = {"ip": terminal.ip, "port": str(terminal.port), "password": terminal.password}
            ok = driver.sync_time(params)
            from datetime import datetime
            
            if ok:
                QMessageBox.information(self, "Reloj Seteado", f"Hora emparejada con éxito.")
            else:
                QMessageBox.warning(self, "Aviso", "Driver no soporta seteo de hora.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al sincronizar:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def add_terminal(self):
        dlg = TerminalDialog(self)
        if dlg.exec_():
            data = dlg.get_data()
            if not data["name"] or not data["ip"]:
                QMessageBox.warning(self, "Faltan Camos", "Nombre e IP son obligatorios.")
                return
            t = DeviceTerminal(**data)
            self.session.add(t)
            self.session.commit()
            self.load_data()

    def edit_terminal(self, t_id):
        t = self.session.query(DeviceTerminal).get(t_id)
        if not t: return
        dlg = TerminalDialog(self, terminal=t)
        if dlg.exec_():
            data = dlg.get_data()
            t.name = data["name"]
            t.driver_name = data["driver_name"]
            t.ip = data["ip"]
            t.port = data["port"]
            t.password = data["password"]
            t.is_active = data["is_active"]
            self.session.commit()
            self.load_data()

    def delete_terminal(self, t_id):
        t = self.session.query(DeviceTerminal).get(t_id)
        if not t: return
        ans = QMessageBox.question(self, "Confirmar eliminación", f"¿Eliminar definitivamente '{t.name}'?")
        if ans == QMessageBox.StandardButton.Yes:
            self.session.delete(t)
            self.session.commit()
            self.load_data()
