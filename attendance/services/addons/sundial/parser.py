from typing import Optional, Tuple
from datetime import datetime, date, time
from services.addons.base_parser import AttendanceParser


class SundialParser(AttendanceParser):
    """
    Parser para archivos TM-MR001.Txt generados por TecknoComm (Sundial ERTeckno).

    Formato fijo de 33 caracteres por línea:
      [0:15]  identifier  — 15 chars, incluye terminal ID + empleado (ej: "000000000010034")
      [15:21] fecha       — DDMMYY  (ej: "010324" = 01/03/2024)
      [21:25] hora        — HHMM    (ej: "0614"   = 06:14)
      [25]    mark_type   — 0=Entrada, 1=Salida
      [26:33] flags       — 7 chars de estado (ej: "0100100")
    """
    display_name = "Sundial ERTeckno (TM-MR001.Txt)"

    def parse_line(self, line: str) -> Optional[Tuple[str, date, time, int, str]]:
        try:
            raw = line.rstrip("\r\n")
            if len(raw) < 26:
                return None
            # Skip header / comment lines
            if not raw[:15].isdigit():
                return None

            identifier = raw[0:15]
            fecha_raw  = raw[15:21]
            hora_raw   = raw[21:25]
            mark_raw   = raw[25:26]
            flags      = raw[26:33] if len(raw) >= 33 else "0000000"

            d = datetime.strptime(fecha_raw, "%d%m%y").date()
            t = datetime.strptime(hora_raw, "%H%M").time()
            mark_type = int(mark_raw) if mark_raw.isdigit() else 0
            if mark_type not in (0, 1):
                mark_type = 0

            return identifier, d, t, mark_type, flags
        except Exception:
            return None
