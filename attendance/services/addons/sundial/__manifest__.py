manifest = {
    "name": "Sundial ERTeckno",
    # Por ahora sólo importación de TM-MR001.Txt. La conexión directa por red
    # (Tibbo TCP, sin TecknoComm.exe) ya está en protocol.py y se expondrá con
    # un driver propio al estilo ZKTeco: driver_class, connection_fields
    # (host/puerto/dirección) y ui_features de gestión de terminales.
    "type": "parser",
    "description": "Importación de archivos TM-MR001.Txt de terminales Sundial ERTeckno.",
    "parser_class": "SundialParser",
    "ui_features": {
        "file_import": True,
        "terminal_management": False,
        "network_import": False,
        "file_extensions": [".txt"],
        "file_name_patterns": ["TM-MR001.txt"],
        "file_format_hint": "TM-MR001.txt de Sundial ERTeckno",
    },
}
