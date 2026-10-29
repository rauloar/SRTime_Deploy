"""
Pruebas contra sesiones reales grabadas por TecknoComm en WinSock.Log.

Un reloj simulado (servidor TCP local) reproduce cada sesión: exige que cada
pedido del cliente sea idéntico byte a byte al que envió TecknoComm y contesta
con la respuesta real grabada.

    pytest tests/test_sundial_protocol.py -v

Los logs de referencia NO están en el repo (contienen tarjetas reales): se leen
de C:/Proyectos/SundialComm/referencia o de la carpeta indicada en SUNDIAL_REFERENCE_DIR. Si no
existen, los tests que los necesitan se saltean.
"""

import logging
import os
import re
import socket
import tempfile
import threading
import unittest
from datetime import date, datetime
from pathlib import Path

import pytest

from services.addons.sundial import protocol as sc

REFERENCE_DIR = Path(os.environ.get("SUNDIAL_REFERENCE_DIR", r"C:\Proyectos\SundialComm\referencia"))
WINSOCK_LOG   = REFERENCE_DIR / "WinSock.Log"
AGL_LOG       = REFERENCE_DIR / "AGL_001.Txt"

pytestmark = pytest.mark.skipif(not WINSOCK_LOG.exists(),
                                reason=f"No está el log de referencia {WINSOCK_LOG}")


def load_sessions():
    """Lista de (ip, [(pedido, respuesta), ...]) por conexión."""
    data = WINSOCK_LOG.read_bytes()
    sessions, cur, pending = [], None, None
    entry = re.compile(rb"\d\d/\d\d/\d{4} \d\d:\d\d:\d\d: (.*?)(?=\r?\n\d\d/\d\d/\d{4} \d\d:\d\d:\d\d: |\Z)", re.S)
    for m in entry.finditer(data):
        txt = m.group(1)
        if txt.startswith(b"Asignacion de Host"):
            cur = (txt[27:].split(b":")[0].decode(), [])
            sessions.append(cur)
            continue
        f = re.match(rb"(Requerimiento|Respuesta)[^{]*\{(.*)\}", txt, re.S)
        if not f or cur is None:
            continue
        if f.group(1) == b"Requerimiento":
            pending = f.group(2)
        elif pending is not None:
            cur[1].append((pending, f.group(2)))
            pending = None
    return sessions


def clean_sessions():
    """Sesiones donde todas las respuestas tienen checksum válido."""
    return [(ip, ex) for ip, ex in load_sessions()
            if ex and all(sc.extract_frame(r) for _, r in ex)]


class FakeTerminal(threading.Thread):
    def __init__(self, exchanges, chunk=7):
        super().__init__(daemon=True)
        self.exchanges, self.chunk = exchanges, chunk
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.port = self.srv.getsockname()[1]
        self.error = None

    def run(self):
        conn, _ = self.srv.accept()
        self.srv.close()
        with conn:
            for expected, reply in self.exchanges:
                got = b""
                while len(got) < len(expected):
                    part = conn.recv(4096)
                    if not part:
                        self.error = f"cliente cerró; esperaba {expected!r}"
                        return
                    got += part
                if got != expected:
                    self.error = f"pedido distinto:\n  esperado {expected!r}\n  recibido {got!r}"
                    return
                # respuesta en pedazos chicos, como puede llegar por TCP
                for i in range(0, len(reply), self.chunk):
                    conn.sendall(reply[i:i + self.chunk])


def find(sessions, pred):
    for ip, ex in sessions:
        if pred(ex):
            return ip, ex
    raise unittest.SkipTest("No hay sesión de ese tipo en WinSock.Log")


class TestFraming(unittest.TestCase):
    def test_checksum_all_logged_frames(self):
        ok = sum(1 for _, ex in clean_sessions() for q, r in ex
                 if sc.extract_frame(q) and sc.extract_frame(r))
        self.assertGreater(ok, 200)  # pares pedido/respuesta

    def test_build_matches_logged(self):
        self.assertEqual(sc.build_frame("001", b"^0"), b"UUU\x7f\x7f\x01001\x02^0\x03]")
        self.assertEqual(sc.build_frame("001", b"n0I4"), b"UUU\x7f\x7f\x01001\x02n0I4\x03\x10")


class TestReplay(unittest.TestCase):
    def setUp(self):
        self.sessions = clean_sessions()

    def replay(self, exchanges, fn):
        term = FakeTerminal(exchanges)
        term.start()
        with sc.SundialClient("127.0.0.1", term.port, timeout=3, retries=0) as c:
            result = fn(c)
        term.join(3)
        self.assertIsNone(term.error, term.error)
        return result

    def test_registers_multi_block(self):
        _, ex = find(self.sessions, lambda ex: sum(q.endswith(b"I5\x03" + q[-1:]) for q, _ in ex) >= 8)
        recs = self.replay(ex, lambda c: (c.status(), c.read_records())[1])
        self.assertGreater(len(recs), 20)

    def test_registers_match_agl(self):
        """Primera descarga del 20/08/2024 contra el log interno del reloj (AGL_001.Txt)."""
        _, ex = find(self.sessions, lambda ex: any(b"Bi00200824" in r for _, r in ex))
        recs = self.replay(ex, lambda c: (c.status(), c.read_records())[1])
        agl = [l.split("\t") for l in AGL_LOG.read_text(encoding="latin-1").splitlines()[1:] if l.strip()]
        agl = [(datetime.strptime(a[9][:16], "%Y-%m-%d %H:%M"), a[6]) for a in agl if len(a) > 9]
        got = [(datetime.combine(r.day, datetime.min.time()).replace(hour=r.hour, minute=r.minute),
                "S" if r.state == 0 else "E") for r in recs if r.day == date(2024, 8, 20)]
        self.assertEqual(got, agl[:len(got)])

    def test_status(self):
        _, ex = find(self.sessions, lambda ex: len(ex) == 2 and b"I4" in ex[1][0])
        st = self.replay(ex, lambda c: c.status())
        self.assertIsNotNone(st.clock)
        self.assertIsNotNone(st.pending)

    def test_status_pending_matches_download(self):
        """El campo de pendientes coincide con la cantidad de registros descargados."""
        for _, ex in self.sessions:
            if len(ex) > 3 and b"I4" in ex[1][0] and ex[-1][1].find(b"Bc1") > 0:
                recs = self.replay(ex, lambda c: (c.status(), c.read_records()))
                self.assertEqual(recs[0].pending, len(recs[1]))

    def test_datetime(self):
        _, ex = find(self.sessions, lambda ex: len(ex) == 2 and b"H0010313092300" in ex[1][0])
        self.replay(ex, lambda c: c.set_datetime(datetime(2013, 3, 1, 9, 23)))

    def test_pointer(self):
        _, ex = find(self.sessions, lambda ex: len(ex) == 2 and b"I222082024" in ex[1][0])
        self.replay(ex, lambda c: c.set_pointer(date(2024, 8, 22)))

    def test_cli_writes_tecknocomm_files(self):
        _, ex = find(self.sessions, lambda ex: any(b"Bi00200824" in r for _, r in ex))
        term = FakeTerminal(ex)
        term.start()
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "cfg.json"
            cfg.write_text('{"output_dir": ".", "terminals": {"1": {"host": "127.0.0.1", "port": %d}}}'
                           % term.port, encoding="utf-8")
            rc = sc.main(["-r", "1", "registers", "--config", str(cfg)])
            for h in logging.root.handlers[:]:
                h.close()
                logging.root.removeHandler(h)
            self.assertEqual(rc, 0)
            lines = (Path(tmp) / "TM-MR001.Txt").read_bytes().split(b"\r\n")
            self.assertEqual(lines[0], b"000000000999999200824192800100100")
            self.assertTrue(all(len(l) == 33 for l in lines if l))
        term.join(3)
        self.assertIsNone(term.error, term.error)


if __name__ == "__main__":
    unittest.main()
