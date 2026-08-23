"""Adapter para el futuro SRTime Terminal Agent desplegado por sede.

Contrato HTTP v1 del agente remoto:
``POST {agent_url}/v1/terminals/{remote_terminal_id}/attendance`` devuelve
``{"logs": [{"identifier": "42", "occurred_at": "2026-07-26T06:01:00",
"mark_type": 0, "flags": "0100100"}]}``.  El agente usa pyzk localmente;
este addon sólo normaliza la respuesta y la entrega al importer compartido.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator, Tuple

from services.addons.base_driver import BiometricDriver


class ZKTecoAgentDriver(BiometricDriver):
    display_name = "ZKTeco Remote Agent"

    def __init__(self) -> None:
        self._params: dict = {}
        self._session = None

    def connect(self, params: dict) -> None:
        import requests

        url = str(params.get("agent_url") or "").strip().rstrip("/")
        terminal_id = str(params.get("remote_terminal_id") or "").strip()
        token = str(params.get("api_token") or "").strip()
        if not url.startswith("https://"):
            raise ValueError("El agente remoto debe usar una URL HTTPS")
        if not terminal_id or not token:
            raise ValueError("ID remoto y token del agente son obligatorios")
        self._params = {"agent_url": url, "remote_terminal_id": terminal_id, "api_token": token}
        self._session = requests.Session()

    def _request(self, path: str):
        if not self._session:
            raise RuntimeError("No hay conexión activa con el agente remoto")
        response = self._session.post(
            f"{self._params['agent_url']}{path}",
            headers={"Authorization": f"Bearer {self._params['api_token']}"},
            timeout=(5, 90),
        )
        response.raise_for_status()
        return response.json()

    def get_attendance_logs(self) -> Iterator[Tuple[str, object, object, int, str]]:
        payload = self._request(f"/v1/terminals/{self._params['remote_terminal_id']}/attendance")
        logs = payload.get("logs", [])
        if not isinstance(logs, list):
            raise ValueError("Respuesta inválida del agente remoto")
        for item in logs:
            occurred_at = datetime.fromisoformat(str(item["occurred_at"]).replace("Z", "+00:00"))
            mark_type = int(item.get("mark_type", 0))
            yield (
                str(item["identifier"]).strip().zfill(15),
                occurred_at.date(),
                occurred_at.time().replace(tzinfo=None),
                mark_type if mark_type in (0, 1) else 0,
                str(item.get("flags") or "0100100")[:7].ljust(7, "0"),
            )

    def test_connection(self, params: dict) -> dict:
        self.connect(params)
        try:
            payload = self._request(f"/v1/terminals/{self._params['remote_terminal_id']}/health")
            return {"status": "ok", "name": payload.get("name"), "serial_number": payload.get("serial_number"), "mac": payload.get("mac")}
        finally:
            self.disconnect()

    def disconnect(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
