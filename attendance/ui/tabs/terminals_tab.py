from datetime import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
    QLineEdit, QComboBox, QCheckBox, QApplication, QGroupBox, QTextEdit,
    QDateEdit, QDialogButtonBox, QLabel, QSpinBox, QTimeEdit
)
from PySide6.QtCore import QDate, QTime, Qt

from models.terminal import DeviceTerminal
import services.addons
from ui.messages import ask_confirm, show_error, show_info, show_success, show_warning


WEEKDAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def schedule_label(state: dict) -> str:
    """Mismo texto que la tarjeta Web (scheduleLabel)."""
    if not state.get("enabled"):
        return "Manual"
    if state.get("mode") == "weekly":
        days = ", ".join(WEEKDAYS[day] for day in state.get("weekdays") or [] if 0 <= day <= 6)
        hour = (state.get("scheduled_time") or "")[:5]
        return f"{days or 'Días definidos'}{f' · {hour}' if hour else ''}"
    return f"Cada {state.get('interval_minutes')} min"


class ScheduleDialog(QDialog):
    """Descarga automática de una terminal: mismos campos y reglas que la Web."""

    def __init__(self, parent, terminal: DeviceTerminal):
        super().__init__(parent)
        self.setWindowTitle(f"Automatización · {terminal.name}")
        layout = QVBoxLayout(self)
        note = QLabel(
            "La descarga automática solo guarda movimientos pendientes de procesar. "
            "El procesamiento de asistencias se mantiene manual."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self.enabled = QCheckBox("Descarga automática activa")
        self.enabled.setChecked(bool(terminal.pull_schedule_enabled))
        layout.addWidget(self.enabled)

        self.options = QWidget()
        form = QFormLayout(self.options)
        self.mode = QComboBox()
        self.mode.addItem("Cada intervalo", "interval")
        self.mode.addItem("Días definidos", "weekly")
        self.mode.setCurrentIndex(1 if terminal.pull_schedule_mode == "weekly" else 0)
        form.addRow("Ciclo de descarga:", self.mode)

        self.interval = QSpinBox()
        self.interval.setRange(1, 10080)
        self.interval.setValue(terminal.pull_interval_minutes or 60)
        self.window = QCheckBox("Solo entre")
        self.window.setChecked(terminal.pull_window_start is not None)
        self.window_start = QTimeEdit(self._qtime(terminal.pull_window_start, time(8)))
        self.window_end = QTimeEdit(self._qtime(terminal.pull_window_end, time(20)))
        window_row = QHBoxLayout()
        window_row.addWidget(self.window)
        window_row.addWidget(self.window_start)
        window_row.addWidget(QLabel("y"))
        window_row.addWidget(self.window_end)
        self.interval_rows = [
            ("Intervalo (minutos):", self.interval),
            ("Franja (opcional):", window_row),
        ]

        self.scheduled_time = QTimeEdit(self._qtime(terminal.pull_schedule_time, time(7)))
        days_row = QHBoxLayout()
        self.days = []
        selected = set(terminal.pull_schedule_weekdays or [])
        for index, name in enumerate(WEEKDAYS):
            check = QCheckBox(name)
            check.setChecked(index in selected)
            self.days.append(check)
            days_row.addWidget(check)
        self.weekly_rows = [
            ("Hora de descarga:", self.scheduled_time),
            ("Días de ejecución:", days_row),
        ]
        for label, field in self.interval_rows + self.weekly_rows:
            form.addRow(label, field)

        self.use_start = QCheckBox("Desde")
        self.use_start.setChecked(terminal.pull_schedule_start_date is not None)
        self.start_date = self._date_edit(terminal.pull_schedule_start_date)
        self.use_end = QCheckBox("Hasta")
        self.use_end.setChecked(terminal.pull_schedule_end_date is not None)
        self.end_date = self._date_edit(terminal.pull_schedule_end_date)
        dates_row = QHBoxLayout()
        for widget in (self.use_start, self.start_date, self.use_end, self.end_date):
            dates_row.addWidget(widget)
        form.addRow("Fechas (opcional):", dates_row)
        self.form = form
        layout.addWidget(self.options)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar automatización")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.enabled.toggled.connect(self._refresh)
        self.mode.currentIndexChanged.connect(self._refresh)
        self._refresh()

    @staticmethod
    def _qtime(value, default: time) -> QTime:
        value = value or default
        return QTime(value.hour, value.minute)

    @staticmethod
    def _date_edit(value) -> QDateEdit:
        edit = QDateEdit(QDate(value.year, value.month, value.day) if value else QDate.currentDate())
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd/MM/yyyy")
        return edit

    def _refresh(self):
        self.options.setVisible(self.enabled.isChecked())
        weekly = self.mode.currentData() == "weekly"
        for rows, visible in ((self.interval_rows, not weekly), (self.weekly_rows, weekly)):
            for _label, field in rows:
                self.form.setRowVisible(field, visible)
        self.adjustSize()

    def values(self) -> dict:
        """Argumentos para services.terminal_scheduler.apply_pull_schedule."""
        weekly = self.mode.currentData() == "weekly"
        return {
            "enabled": self.enabled.isChecked(),
            "mode": self.mode.currentData(),
            "interval_minutes": None if weekly else self.interval.value(),
            "weekdays": [index for index, check in enumerate(self.days) if check.isChecked()] if weekly else None,
            "scheduled_time": self.scheduled_time.time().toPython() if weekly else None,
            "window_start": self.window_start.time().toPython() if not weekly and self.window.isChecked() else None,
            "window_end": self.window_end.time().toPython() if not weekly and self.window.isChecked() else None,
            "start_date": self.start_date.date().toPython() if self.use_start.isChecked() else None,
            "end_date": self.end_date.date().toPython() if self.use_end.isChecked() else None,
        }

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
        # Mismas acciones que la tarjeta Web, en el mismo orden y con los mismos nombres.
        self.clear_memory_check = QCheckBox("Borrar memoria de la terminal después de bajar registros")
        detail_layout.addWidget(self.clear_memory_check)
        detail_actions = QHBoxLayout()
        self.btn_pull = QPushButton("Bajar registros")
        self.btn_pull.clicked.connect(self.pull_selected_terminal)
        detail_actions.addWidget(self.btn_pull)
        self.btn_schedule = QPushButton("Programar")
        self.btn_schedule.clicked.connect(self.edit_schedule)
        detail_actions.addWidget(self.btn_schedule)
        self.btn_pointer = QPushButton("Volver a bajar registros desde...")
        self.btn_pointer.clicked.connect(self.set_attendance_pointer)
        detail_actions.addWidget(self.btn_pointer)
        self.btn_list_users = QPushButton("Bajar usuarios")
        self.btn_list_users.clicked.connect(self.list_terminal_users)
        detail_actions.addWidget(self.btn_list_users)
        self.btn_sync_profiles = QPushButton("Subir usuarios")
        self.btn_sync_profiles.clicked.connect(self.sync_terminal_profiles)
        detail_actions.addWidget(self.btn_sync_profiles)
        detail_actions.addStretch()
        detail_layout.addLayout(detail_actions)
        layout.addWidget(self.detail_group)
        self.pull_worker = None
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
        from services.terminals import with_enabled_driver
        terminals = with_enabled_driver(self.session.query(DeviceTerminal)).order_by(asc(DeviceTerminal.id)).all()
        
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
            btn_ping = QPushButton("Conectar")
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
        # La ficha muestra sólo lo que el driver declara en su manifest
        # (capabilities): sin directorio de usuarios no hay botones de usuarios.
        from services.terminals import TerminalOperationError, supports_capability
        try:
            has_users = terminal is not None and supports_capability(terminal, "terminal_users")
            can_sync = terminal is not None and supports_capability(terminal, "terminal_user_name_sync")
            has_pointer = terminal is not None and supports_capability(terminal, "attendance_pointer")
            can_clear = terminal is not None and supports_capability(terminal, "clear_attendance_memory")
        except TerminalOperationError:
            has_users = can_sync = has_pointer = can_clear = False
        self.btn_list_users.setVisible(has_users)
        self.btn_sync_profiles.setVisible(can_sync)
        self.btn_pointer.setVisible(has_pointer)
        self.clear_memory_check.setVisible(can_clear)
        if not can_clear:
            self.clear_memory_check.setChecked(False)
        pulling = self.pull_worker is not None
        for button in (self.btn_list_users, self.btn_sync_profiles, self.btn_pointer, self.btn_pull):
            button.setEnabled(enabled and not pulling)
        self.btn_schedule.setEnabled(terminal is not None)
        if terminal is None:
            self.detail_label.setText("Seleccione una terminal para ver sus detalles y operaciones extendidas.")
            return
        from services.terminal_scheduler import schedule_state
        state = schedule_state(terminal)
        last = state.get("last_error")
        last_line = ""
        if last:
            last_line = f"\n{'Último aviso' if state.get('last_status') == 'warning' else 'Último error'}: {last}"
        self.detail_label.setText(
            f"Nombre: {terminal.name} · {terminal.driver_name}\n"
            f"Última descarga: {terminal.last_sync.strftime('%d/%m/%Y %H:%M') if terminal.last_sync else 'Nunca'}\n"
            f"Estado automático: {schedule_label(state)}\n"
            f"Próxima descarga: {terminal.next_pull_at.strftime('%d/%m/%Y %H:%M') if terminal.next_pull_at else '—'}"
            f"{last_line}"
        )

    def pull_selected_terminal(self):
        terminal = self._selected_terminal()
        if terminal is None or self.pull_worker is not None:
            return
        from ui.tabs.import_tab import ImportWorker
        self.pull_worker = ImportWorker(
            self.session, terminal=terminal, clear_device_memory=self.clear_memory_check.isChecked()
        )
        self.pull_worker.progress.connect(
            lambda current, nuevos, duplicados, message: self.btn_pull.setText(f"Descargando... {current}")
        )
        self.pull_worker.finished.connect(self._pull_finished)
        self.pull_worker.failed.connect(self._pull_failed)
        self.btn_pull.setText("Descargando...")
        self._show_terminal_detail(terminal)
        self.pull_worker.start()

    def _pull_done(self):
        self.pull_worker = None
        self.btn_pull.setText("Bajar registros")
        self.session.expire_all()
        self.load_data()

    def _pull_finished(self, nuevos, duplicados, warnings):
        self._pull_done()
        details = [f"Nuevos: {nuevos}", f"Duplicados: {duplicados}"]
        if warnings:
            show_warning(self, "Bajar registros", "Descarga finalizada con avisos.", details + list(warnings))
        else:
            show_success(self, "Bajar registros", "Descarga finalizada.", details)

    def _pull_failed(self, message):
        self._pull_done()
        show_error(self, "Bajar registros", message or "No se pudieron descargar los registros pendientes.")

    def edit_schedule(self):
        if not self.selected_terminal_id:
            show_warning(self, "Terminales", "Seleccioná una terminal.")
            return
        terminal = self.session.get(DeviceTerminal, self.selected_terminal_id)
        dialog = ScheduleDialog(self, terminal)
        while dialog.exec():
            from services.terminal_scheduler import ScheduleError, apply_pull_schedule
            try:
                apply_pull_schedule(terminal, **dialog.values())
            except ScheduleError as exc:
                self.session.rollback()
                show_warning(self, "Automatización", str(exc))
                continue
            self.session.commit()
            self.load_data()
            return

    def _selected_terminal(self):
        if not self.selected_terminal_id:
            show_warning(self, "Terminales", "Seleccioná una terminal activa.")
            return None
        terminal = self.session.get(DeviceTerminal, self.selected_terminal_id)
        if not terminal or not terminal.is_active:
            show_warning(self, "Terminales", "La terminal seleccionada no está activa.")
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
            show_info(self, "Usuarios de la terminal", f"Usuarios en la terminal: {len(users)}.", lines[:100])
        except Exception as exc:
            show_error(self, "Usuarios de la terminal", "No se pudieron leer los usuarios de la terminal.", exc)
        finally:
            QApplication.restoreOverrideCursor()

    def sync_terminal_profiles(self):
        terminal = self._selected_terminal()
        if terminal is None:
            return
        if not ask_confirm(
            self, "Sincronizar perfiles",
            "Se actualizarán nombre y privilegio (USER/ADMIN) desde SRTime hacia los usuarios existentes de la terminal. UID e ID se preservan. ¿Continuar?",
            "Continuar",
        ):
            return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            from services.terminals import sync_terminal_user_names
            result = sync_terminal_user_names(terminal, self.session)
            show_success(
                self, "Sincronizar perfiles", "Perfiles sincronizados.",
                [
                    f"Usuarios en la terminal: {result['terminal_users']}",
                    f"Coincidentes: {result['matched']}",
                    f"Actualizados: {result['updated']}",
                    f"Privilegios actualizados: {result['privilege_updated']}",
                ],
            )
        except Exception as exc:
            show_error(self, "Sincronizar perfiles", "No se pudieron sincronizar los perfiles de la terminal.", exc)
        finally:
            QApplication.restoreOverrideCursor()

    def set_attendance_pointer(self):
        terminal = self._selected_terminal()
        if terminal is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Volver a bajar registros")
        form = QFormLayout(dialog)
        form.addRow(QLabel(
            "La terminal vuelve a entregar las marcas desde la fecha elegida en la próxima\n"
            "descarga. Las que ya están en SRTime se cuentan como duplicadas."
        ))
        date_edit = QDateEdit(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd/MM/yyyy")
        date_edit.setMaximumDate(QDate.currentDate())
        form.addRow("Desde:", date_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if not dialog.exec():
            return
        since = date_edit.date().toPython()
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            from services.terminals import set_attendance_pointer
            set_attendance_pointer(terminal, since)
            show_success(
                self, "Volver a bajar registros",
                f"Lectura reposicionada. Usá \"Bajar registros\" para bajar desde el {since:%d/%m/%Y}.",
            )
        except Exception as exc:
            show_error(self, "Volver a bajar registros", "No se pudo reposicionar la lectura de la terminal.", exc)
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
            
            details = [f"{item['label']}: {item['value']}" for item in res.get("details", [])]
            show_success(self, "Probar conexión", "La terminal respondió correctamente.", details)
        except Exception as e:
            show_error(self, "Probar conexión", "No se pudo conectar con la terminal.", e)
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
                show_success(self, "Poner en hora", "La terminal quedó en hora con el servidor.")
            else:
                show_warning(self, "Poner en hora", "El driver de la terminal no permite poner la hora.")
        except Exception as e:
            show_error(self, "Poner en hora", "No se pudo poner en hora la terminal.", e)
        finally:
            QApplication.restoreOverrideCursor()

    def add_terminal(self):
        dlg = TerminalDialog(self)
        if dlg.exec_():
            data = dlg.get_data()
            if not data["name"]:
                show_warning(self, "Terminales", "El nombre de la terminal es obligatorio.")
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
        if ask_confirm(self, "Eliminar terminal", f"¿Eliminar definitivamente la terminal '{t.name}'?", "Eliminar", danger=True):
            self.session.delete(t)
            self.session.commit()
            self.load_data()
