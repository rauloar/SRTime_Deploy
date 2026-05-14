import subprocess
import os
from typing import Iterator, Tuple
from datetime import date, time, datetime
from services.addons.base_driver import BiometricDriver


class SundialDriver(BiometricDriver):
    """
    Driver para terminales Sundial ERTeckno vía TecknoComm.exe.

    Flujo de descarga:
      1. Llama a TecknoComm.exe con A:Registers para cada terminal configurada.
         TecknoComm.exe se conecta al terminal por TCP/IP (puerto 3000),
         descarga los registros y los escribe en TM-MR001.Txt.
      2. El driver lee y parsea TM-MR001.Txt.
      3. Retorna los registros como tuplas estándar de SRTime.
    """
    display_name = "Sundial ERTeckno"

    connection_fields = [
        {"name": "tecknocomm_exe",  "label": "Ruta a TecknoComm.exe",             "type": "text",   "default": r"C:\TecknoComm\TecknoComm.exe"},
        {"name": "output_file",     "label": "Ruta a TM-MR001.Txt",               "type": "text",   "default": r"C:\TecknoComm\TM-MR001.Txt"},
        {"name": "db_password",     "label": "Contraseña BD (P:)",                "type": "text",   "default": "TecknoComm"},
        {"name": "db_user",         "label": "Usuario (U:)",                      "type": "text",   "default": "admin"},
        {"name": "db_client",       "label": "Cliente (C:)",                      "type": "text",   "default": "admin"},
        {"name": "terminals",       "label": "N° terminales a sync (ej: 1,2,3)",  "type": "text",   "default": "1"},
        {"name": "timeout",         "label": "Timeout por terminal (segundos)",   "type": "number", "default": "120"},
    ]

    def __init__(self):
        self._params = {}
        self._output_file = None

    # ── connect: llama a TecknoComm.exe para generar TM-MR001.Txt ───────────
    def connect(self, params: dict):
        self._params = params
        exe  = params.get("tecknocomm_exe", r"C:\TecknoComm\TecknoComm.exe")
        self._output_file = params.get("output_file", r"C:\TecknoComm\TM-MR001.Txt")

        if not os.path.isfile(exe):
            raise Exception(f"No se encontró TecknoComm.exe en: {exe}")

        pwd     = params.get("db_password", "TecknoComm")
        user    = params.get("db_user",     "admin")
        client  = params.get("db_client",   "admin")
        timeout = int(params.get("timeout", 120))

        terminals_raw = params.get("terminals", "1")
        terminal_ids  = [t.strip() for t in terminals_raw.split(",") if t.strip()]

        exe_dir = os.path.dirname(exe)

        for term_id in terminal_ids:
            arg = f"P:{pwd};U:{user};C:{client};R:{term_id};A:Registers"
            try:
                subprocess.run(
                    [exe, arg],
                    cwd=exe_dir,
                    timeout=timeout,
                    check=True,
                )
            except subprocess.TimeoutExpired:
                raise Exception(f"TecknoComm.exe superó el timeout de {timeout}s (terminal R:{term_id})")
            except subprocess.CalledProcessError as e:
                raise Exception(f"TecknoComm.exe terminó con error (terminal R:{term_id}): código {e.returncode}")

    # ── get_attendance_logs: lee TM-MR001.Txt generado por TecknoComm ───────
    def get_attendance_logs(self) -> Iterator[Tuple[str, date, time, int, str]]:
        if not self._output_file:
            raise Exception("No hay conexión activa. Llame a connect() primero.")

        if not os.path.isfile(self._output_file):
            raise Exception(f"TecknoComm.exe no generó el archivo esperado: {self._output_file}")

        from .parser import SundialParser
        parser = SundialParser()

        with open(self._output_file, "r", encoding="latin-1") as f:
            for line in f:
                parsed = parser.parse_line(line)
                if parsed:
                    yield parsed

    # ── test_connection: verifica que el exe existe y puede correr ───────────
    def test_connection(self, params: dict) -> dict:
        exe = params.get("tecknocomm_exe", r"C:\TecknoComm\TecknoComm.exe")
        if not os.path.isfile(exe):
            return {"status": "error", "message": f"No se encontró: {exe}"}

        pwd    = params.get("db_password", "TecknoComm")
        user   = params.get("db_user",     "admin")
        client = params.get("db_client",   "admin")
        timeout = int(params.get("timeout", 30))
        exe_dir = os.path.dirname(exe)

        terminals_raw = params.get("terminals", "1")
        terminal_ids  = [t.strip() for t in terminals_raw.split(",") if t.strip()]
        term_id = terminal_ids[0] if terminal_ids else "1"

        # A:Pointer solo lee el puntero sin descargar registros — prueba de conectividad
        arg = f"P:{pwd};U:{user};C:{client};R:{term_id};A:Pointer"
        try:
            result = subprocess.run(
                [exe, arg],
                cwd=exe_dir,
                timeout=timeout,
                capture_output=True,
            )
            return {
                "status": "ok",
                "message": f"TecknoComm.exe respondió (código {result.returncode})",
                "exe": exe,
                "terminals": terminals_raw,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": f"Timeout de {timeout}s al probar conexión"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── sync_time: sincroniza fecha/hora de las terminales con el sistema ────
    def sync_time(self, params: dict) -> bool:
        exe     = params.get("tecknocomm_exe", r"C:\TecknoComm\TecknoComm.exe")
        pwd     = params.get("db_password", "TecknoComm")
        user    = params.get("db_user",     "admin")
        client  = params.get("db_client",   "admin")
        timeout = int(params.get("timeout", 60))
        exe_dir = os.path.dirname(exe)

        terminals_raw = params.get("terminals", "1")
        terminal_ids  = [t.strip() for t in terminals_raw.split(",") if t.strip()]

        ok = True
        for term_id in terminal_ids:
            # Sin D: → TecknoComm usa la hora del sistema
            arg = f"P:{pwd};U:{user};C:{client};R:{term_id};A:DateTime"
            try:
                subprocess.run([exe, arg], cwd=exe_dir, timeout=timeout, check=True)
            except Exception:
                ok = False
        return ok

    def disconnect(self):
        pass
