manifest = {
    "name": "ZKTeco Remote Agent",
    "type": "driver",
    "description": "Conecta SRTime con un agente ZKTeco de una sede remota mediante HTTPS. El agente conserva la conexión pyzk dentro de la red local.",
    "driver_class": "ZKTecoAgentDriver",
    "ui_features": {
        "file_import": False,
        "terminal_management": True,
        "network_import": True,
    },
    # Lo que informa test_connection, en el orden en que se muestra al conectar.
    "connection_details": [
        {"name": "name", "label": "Dispositivo"},
        {"name": "serial_number", "label": "Número de serie"},
        {"name": "mac", "label": "MAC"},
    ],
    "connection_fields": [
        {"name": "agent_url", "label": "URL del agente (HTTPS)", "type": "text", "default": "", "required": True},
        {"name": "remote_terminal_id", "label": "ID de terminal en la sede", "type": "text", "default": "", "required": True},
        {"name": "api_token", "label": "Token del agente", "type": "password", "default": "", "required": True},
    ],
}
