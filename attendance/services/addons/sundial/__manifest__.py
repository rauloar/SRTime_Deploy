manifest = {
    "name": "Sundial ERTeckno",
    "type": "both",
    "description": "Conexión directa con relojes Sundial ERTeckno por red (módulo Tibbo, TCP 3000) e importación de archivos TM-MR001.Txt.",
    "driver_class": "SundialDriver",
    "parser_class": "SundialParser",
    "ui_features": {
        "file_import": True,
        "terminal_management": True,
        "network_import": True,
        "file_extensions": [".txt"],
        "file_name_patterns": ["TM-MR001.txt"],
        "file_format_hint": "TM-MR001.txt de Sundial ERTeckno",
    },
    "capabilities": {
        # El reloj informa cuántos registros tiene pendientes de entregar.
        "attendance_count": True,
        # I2: volver a entregar registros desde una fecha (puntero de lectura).
        "attendance_pointer": True,
        # Sin directorio de usuarios ni borrado de memoria: el reloj entrega
        # sólo lo pendiente y avanza su puntero al confirmar la lectura.
        "terminal_users": False,
        "terminal_user_name_sync": False,
        "terminal_user_privilege_sync": False,
        "clear_attendance_memory": False,
    },
    # Lo que informa test_connection, en el orden en que se muestra al conectar.
    "connection_details": [
        {"name": "address", "label": "Número de terminal"},
        {"name": "time", "label": "Hora del reloj"},
        {"name": "clock_drift", "label": "Desvío de hora"},
        {"name": "pending_records", "label": "Registros pendientes"},
    ],
    "connection_fields": [
        {"name": "ip", "label": "Dirección IP (módulo Tibbo)", "type": "text", "default": "", "required": True},
        {"name": "port", "label": "Puerto", "type": "number", "default": "3000"},
        {"name": "address", "label": "Número de terminal", "type": "number", "default": "1"},
        {"name": "timeout", "label": "Timeout de conexión (seg)", "type": "number", "default": "5"},
    ],
}
