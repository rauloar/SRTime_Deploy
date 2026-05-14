from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QGroupBox, QFormLayout, QLabel, QStyle
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from datetime import date


class DashboardTab(QWidget):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        btn_bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_refresh.clicked.connect(self.load_data)
        btn_bar.addWidget(self.btn_refresh)
        btn_bar.addStretch()
        root.addLayout(btn_bar)

        # ── Empleados ────────────────────────────────────────
        grp_emp = QGroupBox("Empleados")
        form_emp = QFormLayout(grp_emp)
        self.lbl_active = QLabel("—")
        self.lbl_inactive = QLabel("—")
        self.lbl_total_emp = QLabel("—")
        form_emp.addRow("Activos:", self.lbl_active)
        form_emp.addRow("Inactivos:", self.lbl_inactive)
        form_emp.addRow("Total:", self.lbl_total_emp)
        root.addWidget(grp_emp)

        # ── Mes actual ───────────────────────────────────────
        self.grp_month = QGroupBox("Mes actual")
        form_month = QFormLayout(self.grp_month)
        self.lbl_month_records = QLabel("—")
        self.lbl_month_ok = QLabel("—")
        self.lbl_month_incomplete = QLabel("—")
        self.lbl_month_justified = QLabel("—")
        self.lbl_month_tardiness = QLabel("—")
        self.lbl_month_overtime = QLabel("—")
        form_month.addRow("Total registros:", self.lbl_month_records)
        form_month.addRow("OK:", self.lbl_month_ok)
        form_month.addRow("Incompletos:", self.lbl_month_incomplete)
        form_month.addRow("Justificados:", self.lbl_month_justified)
        form_month.addRow("Min. tardanza acum.:", self.lbl_month_tardiness)
        form_month.addRow("Min. horas extra acum.:", self.lbl_month_overtime)
        root.addWidget(self.grp_month)

        # ── Últimos 7 días ────────────────────────────────────
        grp_week = QGroupBox("Últimos 7 días")
        form_week = QFormLayout(grp_week)
        self.lbl_week_records = QLabel("—")
        self.lbl_week_incomplete = QLabel("—")
        form_week.addRow("Total registros:", self.lbl_week_records)
        form_week.addRow("Incompletos:", self.lbl_week_incomplete)
        root.addWidget(grp_week)

        # ── Feriados próximos ─────────────────────────────────
        grp_hol = QGroupBox("Feriados próximos (30 días)")
        form_hol = QFormLayout(grp_hol)
        self.lbl_holidays = QLabel("—")
        self.lbl_holidays.setWordWrap(True)
        form_hol.addRow(self.lbl_holidays)
        root.addWidget(grp_hol)

        root.addStretch()

    def load_data(self):
        from models.employee import User
        from models.processed_attendance import ProcessedAttendance
        from models.holiday import Holiday
        from datetime import timedelta
        from sqlalchemy import func

        today = date.today()
        month_start = today.replace(day=1)
        week_start = today - timedelta(days=6)

        # ── Employees ────────────────────────────────────────
        active = self.session.query(User).filter(User.is_active == True).count()
        inactive = self.session.query(User).filter(User.is_active == False).count()
        self.lbl_active.setText(str(active))
        self.lbl_inactive.setText(str(inactive))
        self.lbl_total_emp.setText(str(active + inactive))

        # ── Current month ────────────────────────────────────
        month_q = self.session.query(ProcessedAttendance).filter(
            ProcessedAttendance.date >= month_start,
            ProcessedAttendance.date <= today
        )
        month_recs = month_q.all()
        ok = sum(1 for r in month_recs if r.status == "OK")
        inc = sum(1 for r in month_recs if r.status == "INCOMPLETO")
        jus = sum(1 for r in month_recs if r.status == "JUSTIFICADO")
        tard = sum(r.tardiness_minutes for r in month_recs)
        ot = sum(r.overtime_minutes for r in month_recs)

        self.grp_month.setTitle(f"Mes actual ({today.strftime('%B %Y')})")
        self.lbl_month_records.setText(str(len(month_recs)))
        self.lbl_month_ok.setText(str(ok))
        self.lbl_month_incomplete.setText(str(inc))
        self.lbl_month_justified.setText(str(jus))
        self.lbl_month_tardiness.setText(str(tard))
        self.lbl_month_overtime.setText(str(ot))

        # ── Last 7 days ──────────────────────────────────────
        week_recs = self.session.query(ProcessedAttendance).filter(
            ProcessedAttendance.date >= week_start,
            ProcessedAttendance.date <= today
        ).all()
        w_inc = sum(1 for r in week_recs if r.status == "INCOMPLETO")
        self.lbl_week_records.setText(str(len(week_recs)))
        self.lbl_week_incomplete.setText(str(w_inc))

        # ── Upcoming holidays ─────────────────────────────────
        next30 = today + timedelta(days=30)
        holidays = self.session.query(Holiday).all()
        upcoming = []
        for h in holidays:
            if h.is_recurring:
                candidate = h.date.replace(year=today.year)
                if candidate < today:
                    candidate = candidate.replace(year=today.year + 1)
            else:
                candidate = h.date
            if today <= candidate <= next30:
                upcoming.append(f"{candidate.strftime('%d/%m/%Y')} — {h.name}")

        self.lbl_holidays.setText("\n".join(upcoming) if upcoming else "Sin feriados en los próximos 30 días")
