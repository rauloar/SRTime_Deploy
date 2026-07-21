"""
HikvisionDriver — ISAPI Pull Mode
==================================
Se comunica con terminales Hikvision via REST ISAPI usando autenticación HTTP Digest.
No requiere instalar librerías adicionales — usa únicamente `requests` (ya en requirements).

Endpoints ISAPI utilizados:
  GET  /ISAPI/System/deviceInfo           → test_connection / metadatos del dispositivo
  PUT  /ISAPI/System/time                 → sync_time
  POST /ISAPI/AccessControl/AcsEvent/Search → get_attendance_logs (pull paginado)

El identificador del empleado se normaliza a 15 dígitos con ceros a la izquierda
para mantener compatibilidad con el estándar de la tabla AttendanceLog.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, date, time
from typing import Iterator, Tuple

from services.addons.base_driver import BiometricDriver


# Namespace ISAPI
_NS = "http://www.hikvision.com/ver20/XMLSchema"
_ISAPI_NS = {"ns": _NS}


def _xml_text(element, tag: str, ns: str = _NS, default: str = "") -> str:
    found = element.find(f"{{{ns}}}{tag}")
    return found.text.strip() if found is not None and found.text else default


class HikvisionDriver(BiometricDriver):
    display_name = "Hikvision (ISAPI)"

    def __init__(self):
        self._session = None
        self._base_url = ""
        self._timeout = 10.0
        self._timezone = ""
        self._event_minor = 0

    def connect(self, params: dict):
        """
        Establece la sesión HTTP con Digest Auth.
        No abre socket persistente — cada llamada ISAPI es una petición HTTP independiente.
        """
        try:
            import requests
            from requests.auth import HTTPDigestAuth

            ip       = str(params.get("ip") or "").strip()
            port     = int(params.get("port", 80))
            username = str(params.get("username") or "").strip()
            password = params.get("password", "")
            if not ip or not username:
                raise ValueError("La dirección IP y el usuario de la terminal son obligatorios")
            self._timeout = float(params.get("timeout", 10))
            self._timezone = str(params.get("timezone", ""))
            self._event_minor = int(params.get("event_minor", 0))

            self._base_url = f"http://{ip}:{port}"
            self._session = requests.Session()
            self._session.auth = HTTPDigestAuth(username, password)
            # Verificar conectividad básica
            resp = self._session.get(
                f"{self._base_url}/ISAPI/System/deviceInfo", timeout=self._timeout
            )
            if resp.status_code == 401:
                raise Exception("Credenciales incorrectas (HTTP 401)")
            resp.raise_for_status()

        except Exception as e:
            self._session = None
            raise Exception(f"Error al conectar con Hikvision en {ip}:{port} — {str(e)}")

    def test_connection(self, params: dict) -> dict:
        """
        Retorna metadatos del dispositivo: nombre, modelo, firmware, número de serie.
        Compatible con el contrato de BiometricDriver.
        """
        self.connect(params)
        try:
            resp = self._session.get(
                f"{self._base_url}/ISAPI/System/deviceInfo", timeout=self._timeout
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            name     = _xml_text(root, "deviceName")
            model    = _xml_text(root, "model")
            firmware = _xml_text(root, "firmwareVersion")
            serial   = _xml_text(root, "serialNumber")
            mac      = _xml_text(root, "macAddress")

            # Hora del dispositivo
            resp_t = self._session.get(
                f"{self._base_url}/ISAPI/System/time", timeout=self._timeout
            )
            device_time = ""
            if resp_t.ok:
                root_t = ET.fromstring(resp_t.content)
                device_time = _xml_text(root_t, "localTime") or _xml_text(root_t, "isoLocalTime")

            return {
                "status":        "ok",
                "name":          name or model,
                "model":         model,
                "firmware":      firmware,
                "serial_number": serial,
                "mac":           mac,
                "time":          device_time,
            }
        finally:
            self.disconnect()

    def sync_time(self, params: dict) -> bool:
        """
        Actualiza la hora del dispositivo a la hora actual del servidor.
        """
        self.connect(params)
        try:
            now = datetime.now()
            # Formato ISO 8601 requerido por ISAPI
            iso_time = now.strftime("%Y-%m-%dT%H:%M:%S")

            # Obtener zona horaria actual del dispositivo para mantenerla
            resp = self._session.get(
                f"{self._base_url}/ISAPI/System/time", timeout=self._timeout
            )
            timezone = self._timezone
            if resp.ok:
                root = ET.fromstring(resp.content)
                tz = _xml_text(root, "timeZone")
                if tz:
                    timezone = tz

            xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Time xmlns="{_NS}">
  <timeMode>manual</timeMode>
  <localTime>{iso_time}</localTime>
  <timeZone>{timezone}</timeZone>
</Time>"""

            resp = self._session.put(
                f"{self._base_url}/ISAPI/System/time",
                data=xml_body.encode("utf-8"),
                headers={"Content-Type": "application/xml"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            raise Exception(f"Error al sincronizar hora Hikvision: {str(e)}")
        finally:
            self.disconnect()

    def get_attendance_logs(self) -> Iterator[Tuple[str, date, time, int, str]]:
        """
        Descarga registros de acceso/asistencia usando AcsEvent Search (paginado).
        Normaliza el identificador del empleado a 15 dígitos con ceros a la izquierda.

        Hikvision reporta:
          employeeNoString: ID del empleado
          time:             ISO 8601 timestamp
          eventType:        "cardReaderAuthentication" / "face" / etc.
          currentVerifyMode: "cardOrFace", "card", "fingerPrint", etc.

        Mapeamos a SRTime:
          mark_type 0 = entrada (por defecto — Hikvision no distingue en/out en ISAPI básico)
          flags      = modo de verificación del evento
        """
        if not self._session:
            raise Exception("No hay sesión activa. Llamar a connect() primero.")

        search_url = f"{self._base_url}/ISAPI/AccessControl/AcsEvent/Search"

        page_size   = 30
        search_id   = 0
        total_fetched = 0
        keep_going  = True

        while keep_going:
            xml_query = f"""<?xml version="1.0" encoding="UTF-8"?>
<AcsEventCond xmlns="{_NS}">
  <searchID>{search_id}</searchID>
  <searchResultPosition>{total_fetched}</searchResultPosition>
  <maxResults>{page_size}</maxResults>
  <major>5</major>
  <minor>{self._event_minor}</minor>
</AcsEventCond>"""

            try:
                resp = self._session.post(
                    search_url,
                    data=xml_query.encode("utf-8"),
                    headers={"Content-Type": "application/xml"},
                    timeout=self._timeout,
                )
                resp.raise_for_status()
            except Exception as e:
                raise Exception(f"Error al consultar AcsEvent Hikvision: {str(e)}")

            root = ET.fromstring(resp.content)

            # Extraer search_id de la respuesta para continuar la paginación
            resp_search_id = _xml_text(root, "searchID")
            if resp_search_id:
                search_id = int(resp_search_id) if resp_search_id.isdigit() else search_id

            info_list = root.find(f"{{{_NS}}}InfoList") or root.find("InfoList")
            if info_list is None:
                break

            events = list(info_list)
            if not events:
                break

            for event in events:
                try:
                    emp_no = _xml_text(event, "employeeNoString") or _xml_text(event, "employeeNo")
                    if not emp_no:
                        continue

                    # Normalizar a 15 dígitos con ceros (estándar SRTime)
                    identifier = emp_no.strip().zfill(15)

                    # Timestamp ISO 8601 → date + time
                    raw_time = _xml_text(event, "time")
                    if not raw_time:
                        continue
                    # Manejar formatos con y sin timezone: "2024-01-15T08:30:00" o "2024-01-15T08:30:00+03:00"
                    raw_time_clean = raw_time[:19]
                    dt = datetime.strptime(raw_time_clean, "%Y-%m-%dT%H:%M:%S")

                    # Modo de verificación como flag (fingerprint, card, face, etc.)
                    verify_mode = _xml_text(event, "currentVerifyMode", default="unknown")

                    minor = _xml_text(event, "minor", default="0")
                    mark_type = 1 if minor == "76" else 0

                    yield identifier, dt.date(), dt.time(), mark_type, verify_mode[:7].ljust(7)

                    total_fetched += 1

                except Exception:
                    # Registro malformado — ignorar y continuar
                    continue

            # Si retornó menos registros que page_size, terminamos
            if len(events) < page_size:
                keep_going = False

    def disconnect(self):
        """Cierra la sesión HTTP."""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
