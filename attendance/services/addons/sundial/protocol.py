"""
protocol.py — Comunicación directa con relojes Sundial ERTeckno vía Tibbo
=========================================================================
Reemplaza a TecknoComm.exe: habla el protocolo serie del reloj (RS-232) a
través del módulo Tibbo que lo expone por TCP (modo servidor transparente,
puerto 3000 por defecto). Sólo usa la librería estándar de Python.

Copia de C:/Proyectos/SundialComm/sundial_comm.py (verificada contra
reloj real 2026-10-27). Pendiente: integrarlo en SundialDriver.

Uso (equivalente a los .bat de TecknoComm):
    python -m services.addons.sundial.protocol --config relojes.json -r 1 status
    python -m services.addons.sundial.protocol --config relojes.json -r 1 registers [--no-confirm]
    python -m services.addons.sundial.protocol --config relojes.json -r 1 datetime [-d "01/03/2013 09:23"]
    python -m services.addons.sundial.protocol --config relojes.json -r 1 pointer -d 01/03/2013
    python -m services.addons.sundial.protocol --config relojes.json -r 0 registers   # todos

Protocolo (reconstruido de WinSock.Log de TecknoComm):
    PC → reloj : 'UUU' 7F 7F 01 <dir:3> 02 <cuerpo> 03 <ck>
    reloj → PC : 'UU'  7F 7F 01 <dir:3> 02 <cuerpo> 03 <ck>
    ck = 0x33 XOR cada byte de <cuerpo>
    Cuerpo de pedido: <seq>'0'<cmd>, seq alterna 'n'/'o' (arranca en 'n' tras conectar)
        ^0               establecer conexión          → ^B
        I4               estado                       → Bi1…
        I5               leer bloque de registros     → Bi00DDMMYY<n×19> | Bc30 (no hay más)
        I3               fin de lectura (confirma)    → Bc10
        I2DDMMYYYY       reposicionar puntero         → Bc10
        H0DDMMYYHHMMSS   fecha y hora                 → Bc10
        H2               deshabilitar horario verano  → Bc10
    Registro (19 bytes): tarjeta[15] hora+0x21 minuto+0x21 estado('@'=0,'A'=1) función+0x21
"""

import argparse
import json
import logging
import socket
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


DEFAULT_CONFIG = {
    "output_dir":      ".",
    "timeout_seconds": 5,
    "retries":         2,
    "terminals": {
        # Plantilla: el operador completa la IP del módulo Tibbo y la activa.
        "1": {"host": "", "port": 3000, "address": "001", "active": False},
    },
}

PREAMBLE_TX = b"UUU\x7f\x7f"
SOH, STX, ETX = 0x01, 0x02, 0x03
RECORD_LEN = 19

log = logging.getLogger("sundial")


class SundialError(Exception):
    pass


# ── Tramas ───────────────────────────────────────────────────────────────────
def checksum(body: bytes) -> int:
    ck = 0x33
    for b in body:
        ck ^= b
    return ck


def build_frame(address: str, body: bytes) -> bytes:
    return (PREAMBLE_TX + bytes([SOH]) + address.encode("ascii") + bytes([STX])
            + body + bytes([ETX, checksum(body)]))


def extract_frame(buf: bytes):
    """Busca una trama completa y válida en buf.
    Devuelve (cuerpo, trama_cruda, resto) o None si todavía falta recibir datos.
    El ETX puede aparecer dentro de los datos, por eso se valida el checksum
    en cada ETX candidato antes de aceptar la trama."""
    s = buf.find(bytes([SOH]))
    if s < 0:
        return None
    x = buf.find(bytes([STX]), s)
    if x < 0:
        return None
    e = buf.find(bytes([ETX]), x + 1)
    while 0 <= e < len(buf) - 1:
        body = buf[x + 1:e]
        if checksum(body) == buf[e + 1]:
            start = buf.rfind(b"UU", 0, s)
            start = start if start >= 0 and s - start <= 5 else s
            return body, buf[start:e + 2], buf[e + 2:]
        e = buf.find(bytes([ETX]), e + 1)
    return None


def printable(raw: bytes) -> str:
    return "".join(chr(b) if 0x20 <= b < 0x7f else f"<{b:02X}>" for b in raw)


# ── Datos ────────────────────────────────────────────────────────────────────
@dataclass
class Record:
    card: str        # 15 dígitos
    day: date
    hour: int
    minute: int
    state: int       # 0 / 1
    function: int

    def to_tm_line(self, terminal: int) -> str:
        """Línea de 33 caracteres de TM-MR###.Txt / TM-FICHA.Txt."""
        return (f"{self.card}{self.day:%d%m%y}{self.hour:02d}{self.minute:02d}"
                f"{self.state}{self.function:02d}{terminal:03d}00")


@dataclass
class Status:
    clock: datetime | None
    pending: int | None
    raw: bytes


def parse_records(body: bytes) -> list[Record]:
    # body = <seq> 'B' 'i' '00' DDMMYY <registros>
    day = datetime.strptime(body[5:11].decode("ascii"), "%d%m%y").date()
    data = body[11:]
    if len(data) % RECORD_LEN:
        log.warning("Bloque con %d bytes sobrantes (no múltiplo de %d): %s",
                    len(data) % RECORD_LEN, RECORD_LEN, printable(body))
    recs = []
    for i in range(0, len(data) - RECORD_LEN + 1, RECORD_LEN):
        r = data[i:i + RECORD_LEN]
        card = r[:15].decode("ascii", "replace")
        hour, minute = r[15] - 0x21, r[16] - 0x21
        if not (card.isdigit() and 0 <= hour < 24 and 0 <= minute < 60 and r[17] in (0x40, 0x41)):
            log.warning("Registro inválido descartado: %s", printable(r))
            continue
        recs.append(Record(card, day, hour, minute, r[17] - 0x40, r[18] - 0x21))
    return recs


def parse_status(body: bytes) -> Status:
    # body = <seq> 'B' 'i' '10' DDMMYY HHMMSS PPPPP <resto sin documentar>
    s = body[3:].decode("ascii", "replace")
    try:
        clock = datetime.strptime(s[2:14], "%d%m%y%H%M%S")
    except ValueError:
        clock = None
    pending = int(s[14:19]) if s[14:19].isdigit() else None
    return Status(clock, pending, body)


# ── Cliente ──────────────────────────────────────────────────────────────────
class SundialClient:
    def __init__(self, host: str, port: int = 3000, address: str = "001",
                 timeout: float = 5, retries: int = 2):
        self.host, self.port, self.address = host, port, address
        self.timeout, self.retries = timeout, retries
        self.sock = None
        self.seq = b"n"
        self.last_raw = b""

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    def connect(self):
        log.info("Conectando a %s:%d", self.host, self.port)
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        body = self._exchange(b"^0", sequenced=False)
        if not body.startswith(b"^B"):
            raise SundialError(f"Respuesta inesperada a la conexión: {printable(body)}")
        self.seq = b"n"

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _recv_frame(self) -> bytes:
        buf = b""
        while True:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                raise SundialError(f"Sin respuesta del reloj (recibido: {printable(buf)})")
            if not chunk:
                raise SundialError("El Tibbo cerró la conexión")
            buf += chunk
            found = extract_frame(buf)
            if found:
                body, raw, _ = found
                self.last_raw = raw
                log.debug("< %s", printable(raw))
                return body

    def _exchange(self, cmd: bytes, sequenced: bool = True) -> bytes:
        body = (self.seq + b"0" + cmd) if sequenced else cmd
        frame = build_frame(self.address, body)
        for attempt in range(self.retries + 1):
            log.debug("> %s", printable(frame))
            self.sock.sendall(frame)
            try:
                reply = self._recv_frame()
            except SundialError as exc:
                if attempt == self.retries:
                    raise
                log.warning("%s — reintento %d", exc, attempt + 1)
                continue
            if sequenced:
                if reply[:1] != self.seq:
                    raise SundialError(f"Secuencia desfasada: {printable(reply)}")
                self.seq = b"o" if self.seq == b"n" else b"n"
            return reply

    def _expect_ok(self, cmd: bytes, what: str):
        reply = self._exchange(cmd)
        if reply[1:4] != b"Bc1":
            raise SundialError(f"{what}: el reloj respondió {printable(reply)}")

    # Acciones
    def status(self) -> Status:
        reply = self._exchange(b"I4")
        if reply[1:3] != b"Bi":
            raise SundialError(f"Estado: respuesta inesperada {printable(reply)}")
        return parse_status(reply)

    def read_records(self, confirm: bool = True) -> list[Record]:
        records = []
        while True:
            reply = self._exchange(b"I5")
            if reply[1:4] == b"Bc3":
                break
            if reply[1:5] != b"Bi00":
                raise SundialError(f"Lectura: respuesta inesperada {printable(reply)}")
            records += parse_records(reply)
        if confirm:
            self._expect_ok(b"I3", "Fin de lectura")
        return records

    def set_datetime(self, when: datetime):
        self._expect_ok(b"H0" + when.strftime("%d%m%y%H%M%S").encode(), "Fecha y hora")

    def set_pointer(self, since: date):
        self._expect_ok(b"I2" + since.strftime("%d%m%Y").encode(), "Puntero")

    def disable_dst(self):
        self._expect_ok(b"H2", "Horario de verano")


# ── Archivos de salida (compatibles con TecknoComm) ──────────────────────────
def append_lines(path: Path, lines: list[str]):
    with open(path, "a", encoding="latin-1", newline="") as f:
        for line in lines:
            f.write(line + "\r\n")


def append_status(path: Path, raw: bytes):
    with open(path, "ab") as f:
        f.write(f"\r\n{datetime.now():%d/%m/%Y %H:%M:%S}:Status [ ".encode() + raw + b" ]")


def save_records(out: Path, number: int, recs: list[Record]):
    lines = [r.to_tm_line(number) for r in recs]
    append_lines(out / f"TM-MR{number:03d}.Txt", lines)
    append_lines(out / "TM-FICHA.Txt", lines)


def save_status(out: Path, number: int, raw: bytes):
    append_status(out / f"TM-ST{number:03d}.Txt", raw)
    append_status(out / "TM-STATUS.Txt", raw)


# ── CLI ──────────────────────────────────────────────────────────────────────
def load_config(path: Path) -> dict:
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        log.info("Se creó %s como plantilla: completá host y active de cada reloj", path)
    cfg = {**DEFAULT_CONFIG, **json.loads(path.read_text(encoding="utf-8"))}
    out = Path(cfg["output_dir"])
    cfg["output_dir"] = out if out.is_absolute() else (path.parent / out).resolve()
    return cfg


def run_action(cfg: dict, number: int, term: dict, args) -> int:
    out: Path = cfg["output_dir"]
    client = SundialClient(term["host"], term.get("port", 3000), term.get("address", "001"),
                           cfg["timeout_seconds"], cfg["retries"])
    with client:
        if args.action == "status":
            st = client.status()
            save_status(out, number, client.last_raw)
            drift = (st.clock - datetime.now()).total_seconds() if st.clock else None
            log.info("Reloj %d: hora %s (desvío %+.0fs), registros pendientes: %s",
                     number, st.clock, drift or 0, st.pending)
        elif args.action == "registers":
            st = client.status()
            log.info("Reloj %d: %s registros pendientes", number, st.pending)
            # Igual que TecknoComm: sin pendientes no se pide I5 (el reloj no contesta)
            recs = [] if st.pending == 0 else client.read_records(confirm=not args.no_confirm)
            save_records(out, number, recs)
            log.info("Reloj %d: %d registros descargados%s", number, len(recs),
                     " (puntero NO confirmado)" if args.no_confirm else "")
        elif args.action == "datetime":
            when = datetime.strptime(args.date, "%d/%m/%Y %H:%M") if args.date else datetime.now()
            client.set_datetime(when)
            log.info("Reloj %d: fecha/hora asignada %s", number, when)
        elif args.action == "pointer":
            if not args.date:
                raise SundialError("pointer requiere -d DD/MM/AAAA")
            since = datetime.strptime(args.date, "%d/%m/%Y").date()
            client.set_pointer(since)
            log.info("Reloj %d: puntero reposicionado a %s", number, since)
        elif args.action == "nodst":
            client.disable_dst()
            log.info("Reloj %d: horario de verano deshabilitado", number)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Comunicación directa con relojes Sundial vía Tibbo")
    p.add_argument("action", choices=["status", "registers", "datetime", "pointer", "nodst"])
    p.add_argument("-r", "--reloj", type=int, required=True, help="número de reloj (0 = todos los activos)")
    p.add_argument("-d", "--date", help='"DD/MM/AAAA HH:MM" (datetime) o "DD/MM/AAAA" (pointer)')
    p.add_argument("--no-confirm", action="store_true", help="registers: no envía I3 (no avanza el puntero)")
    p.add_argument("--config", type=Path, required=True, help="JSON con los relojes (fuera del repo)")
    p.add_argument("-v", "--verbose", action="store_true", help="muestra las tramas")
    args = p.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%d/%m/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)])

    cfg = load_config(args.config)
    cfg["output_dir"].mkdir(parents=True, exist_ok=True)
    terms = {int(k): v for k, v in cfg["terminals"].items()}
    if args.reloj == 0:
        targets = [(n, t) for n, t in sorted(terms.items()) if t.get("active", True)]
    elif args.reloj in terms:
        targets = [(args.reloj, terms[args.reloj])]
    else:
        log.error("Reloj %d no está en %s", args.reloj, args.config)
        return 2
    missing = [n for n, t in targets if not str(t.get("host", "")).strip()]
    if missing:
        log.error("Reloj %s sin host en %s", ", ".join(map(str, missing)), args.config)
        return 2

    rc = 0
    for number, term in targets:
        try:
            run_action(cfg, number, term, args)
        except (OSError, SundialError, ValueError) as exc:
            log.error("Reloj %d (%s): %s", number, term["host"], exc)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
