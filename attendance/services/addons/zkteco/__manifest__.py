manifest = {
    "name": "ZKTeco",
    "type": "both",
    "description": "Conexión directa con terminales ZKTeco por red (pyzk) e importación de att logs exportados por USB.",
    "driver_class": "ZKTecoDriver",
    "parser_class": "ZKTecoParser",
    "ui_features": {
        # ZKTeco admite tanto descarga por red como el archivo USB nativo
        # ``att.dat``. TM-MR001 sigue siendo responsabilidad de Sundial.
        "file_import": True,
        "terminal_management": True,
        "network_import": True,
        "file_extensions": [".dat"],
        "file_name_patterns": ["att.dat"],
        "file_format_hint": "att.dat de ZKTeco: ID, fecha, hora, status, punch, ...",
    },
    "capabilities": {
        "attendance_count": True,
        "terminal_users": True,
        "terminal_user_name_sync": True,
        "terminal_user_privilege_sync": True,
        "clear_attendance_memory": True,
    },
    "terminal_user_privileges": {
        "0": "Usuario de terminal",
        "14": "Administrador de terminal",
    },
    # Lo que informa test_connection, en el orden en que se muestra al conectar.
    "connection_details": [
        {"name": "name", "label": "Dispositivo"},
        {"name": "serial_number", "label": "Número de serie"},
        {"name": "mac", "label": "MAC"},
        {"name": "firmware", "label": "Firmware"},
        {"name": "time", "label": "Hora del reloj"},
    ],
    "connection_fields": [
        {"name": "ip", "label": "Dirección IP", "type": "text", "default": "", "required": True},
        {"name": "port", "label": "Puerto", "type": "number", "default": "4370"},
        {"name": "timeout", "label": "Timeout de conexión (seg)", "type": "number", "default": "5"},
    ],
}
