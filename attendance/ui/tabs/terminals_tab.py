import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QDialog, QFormLayout, 
    QLineEdit, QComboBox, QCheckBox, QApplication, QGroupBox, QTextEdit
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
        self.connection_form = QFormLayout()
        self.connection_edits = {}
        layout.addRow(self.connection_form)
        self.driver_combo.currentTextChanged.connect(self._build_connection_fields)
        self._build_connection_fields(self.driver_combo.currentText())
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

    def _build_connection_fields(self, driver_name):
        while self.connection_form.rowCount():
            self.connection_form.removeRow(0)
        self.connection_edits = {}

        info = services.addons.get_addon_info(driver_name) or {}
        if self.terminal and self.terminal.driver_name == driver_name:
            from services.terminals import get_connection_params
            stored = get_connection_params(self.terminal)
        else:
            stored = {}

        for field in info.get("connection_fields") or []:
            name = field["name"]
            is_secret = field.get("type") == "password" or name in {"password", "db_password"}
            value = "" if is_secret and self.terminal else str(stored.get(name, field.get("default", "")))
            edit = QLineEdit(value)
            if is_secret:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
                if self.terminal:
                    edit.setPlaceholderText("Dejar vacío para conservar")
            self.connection_edits[name] = edit
            self.connection_form.addRow(f"{field.get('label', name)}:", edit)

    def get_data(self):
        params = {
            name: edit.text().strip()
            for name, edit in self.connection_edits.items()
            if edit.text().strip() or name not in {"password", "db_password"}
        }
        return {
            "name": self.name_edit.text().strip(),
            "driver_name": self.driver_combo.currentText(),
            "ip": params.get("ip"),
            "port": int(params["port"]) if params.get("port") else None,
            "password": params.get("password"),
            "connection_params": params,
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

        # Ficha inferior: expone las operaciones extendidas sin duplicar la
        # comunicación pyzk. Todo se delega a services.terminals.
        self.detail_group = QGroupBox("Detalle de terminal")
        detail_layout = QVBoxLayout(self.detail_group)
        self.detail_label = QTextEdit()
        self.detail_label.setReadOnly(True)
        self.detail_label.setMaximumHeight(110)
        detail_layout.addWidget(self.detail_label)
        detail_actions = QHBoxLayout()
        self.btn_list_users = QPushButton("Ver usuarios de terminal")
        self.btn_list_users.clicked.connect(self.list_terminal_users)
        detail_actions.addWidget(self.btn_list_users)
        self.btn_sync_profiles = QPushButton("Sincronizar perfiles hacia terminal")
        self.btn_sync_profiles.clicked.connect(self.sync_terminal_profiles)
        detail_actions.addWidget(self.btn_sync_profiles)
        detail_layout.addLayout(detail_actions)
        layout.addWidget(self.detail_group)
        self.selected_terminal_id = None
        self.table.itemSelectionChanged.connect(self._select_terminal_from_table)
        self.load_data()

    def get_driver_instance(self, driver_name):
        info = services.addons.get_addon_info(driver_name)
        if not info or not info.get("driver_class"):
            return None
        return info["driver_class"]()

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
        if terminals:
            self.table.selectRow(0)
        else:
            self._show_terminal_detail(None)

    def _select_terminal_from_table(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        terminal_id = int(item.text()) if item else None
        terminal = self.session.get(DeviceTerminal, terminal_id) if terminal_id else None
        self._show_terminal_detail(terminal)

    def _show_terminal_detail(self, terminal):
        self.selected_terminal_id = terminal.id if terminal else None
        enabled = terminal is not None and terminal.is_active
        self.btn_list_users.setEnabled(enabled)
        self.btn_sync_profiles.setEnabled(enabled)
        if terminal is None:
            self.detail_label.setText("Seleccione una terminal para ver sus detalles y operaciones extendidas.")
            return
        self.detail_label.setText(
            f"Nombre: {terminal.name}\nDriver: {terminal.driver_name}\n"
            f"Conexión: {terminal.ip or '-'}:{terminal.port or '-'}\n"
            f"Serie: {terminal.serial_number or 'Sin verificar'}\n"
            f"Última descarga: {terminal.last_sync or 'Nunca'}"
        )

    def _selected_terminal(self):
        if not self.selected_terminal_id:
            QMessageBox.warning(self, "Terminal", "Seleccione una terminal activa.")
            return None
        terminal = self.session.get(DeviceTerminal, self.selected_terminal_id)
        if not terminal or not terminal.is_active:
            QMessageBox.warning(self, "Terminal", "La terminal seleccionada no está activa.")
            return None
        return terminal

    def list_terminal_users(self):
        terminal = self._selected_terminal()
        if terminal is None:
            return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            from services.terminals import list_terminal_users
            result = list_terminal_users(terminal)
            users = result.get("users", [])
            lines = [f"{u['user_id']} | {u['name'] or '-'} | {u['privilege_label']}" for u in users]
            QMessageBox.information(self, "Usuarios en terminal", f"Total: {len(users)}\n\n" + "\n".join(lines[:100]))
        except Exception as exc:
            QMessageBox.critical(self, "Usuarios de terminal", f"No se pudieron leer los usuarios:\n{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def sync_terminal_profiles(self):
        terminal = self._selected_terminal()
        if terminal is None:
            return
        answer = QMessageBox.question(
            self, "Sincronizar perfiles",
            "Se actualizarán nombre y privilegio (USER/ADMIN) desde SRTime hacia los usuarios existentes de la terminal. UID e ID se preservan. ¿Continuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            from services.terminals import sync_terminal_user_names
            result = sync_terminal_user_names(terminal, self.session)
            QMessageBox.information(
                self, "Perfiles sincronizados",
                f"Usuarios en terminal: {result['terminal_users']}\nCoincidentes: {result['matched']}\n"
                f"Actualizados: {result['updated']}\nPrivilegios actualizados: {result['privilege_updated']}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Sincronizar perfiles", f"No se pudo sincronizar:\n{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def ping_terminal(self, t_id):
        terminal = self.session.query(DeviceTerminal).get(t_id)
        if not terminal: return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            from services.terminals import test_connection
            res = test_connection(terminal)
            
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
            from services.terminals import sync_time
            ok = sync_time(terminal)
            
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
            if not data["name"]:
                QMessageBox.warning(self, "Faltan campos", "El nombre es obligatorio.")
                return
            params = data.pop("connection_params")
            data.pop("password", None)
            t = DeviceTerminal(**data, password=None)
            from services.terminals import merge_connection_params
            t.connection_params = merge_connection_params(t, params)
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
            if data["password"]:
                t.password = data["password"]
            t.is_active = data["is_active"]
            from services.terminals import merge_connection_params
            t.connection_params = merge_connection_params(t, data["connection_params"])
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
