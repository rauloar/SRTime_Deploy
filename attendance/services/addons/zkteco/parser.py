from typing import Optional, Tuple
from datetime import datetime, date, time
from services.addons.base_parser import AttendanceParser


class ZKTecoParser(AttendanceParser):
    """
    Parser para archivos TXT exportados desde terminales ZKTeco
    (por ejemplo, bajados a un USB/flash drive desde el dispositivo).

    Formato típico ZKTeco USB export:
    1           2025-03-15 08:30:00 1   0   1   0
    (user_id    timestamp           status  verify  ...)
    """
    display_name = "ZKTeco (Archivo USB)"

    def parse_line(self, line: str) -> Optional[Tuple[str, date, time, int, str]]:
        try:
            parts = line.strip().split()
            if len(parts) < 4:
                return None

            # user_id (pad to 15 chars for consistency)
            identifier = parts[0].strip().zfill(15)

            # date + time
            date_str = parts[1]
            time_str = parts[2]
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            d = dt.date()
            t = dt.time()

            # status (IN/OUT)
            mark_type = int(parts[3]) if len(parts) > 3 else 0
            if mark_type not in (0, 1):
                mark_type = 0

            flags = "0100100"

            return identifier, d, t, mark_type, flags
        except Exception:
            return None
