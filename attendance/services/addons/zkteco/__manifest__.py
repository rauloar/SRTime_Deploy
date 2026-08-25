manifest = {
    "name": "ZKTeco",
    "type": "both",
    "description": "Conexión directa con terminales ZKTeco por red (pyzk) e importación de att logs exportados por USB.",
    "driver_class": "ZKTecoDriver",
    "parser_class": "ZKTecoParser",
    "capabilities": {
        "attendance_count": True,
        "terminal_users": True,
        "terminal_user_name_sync": True,
    },
    "terminal_user_privileges": {
        "0": "Usuario de terminal",
        "14": "Administrador de terminal",
    },
    "connection_fields": [
        {"name": "ip", "label": "Dirección IP", "type": "text", "default": "", "required": True},
        {"name": "port", "label": "Puerto", "type": "number", "default": "4370"},
    ],
}
