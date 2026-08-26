manifest = {
    "name": "Sundial ERTeckno",
    "type": "both",
    "description": (
        "Conexión con terminales Sundial ERTeckno vía TecknoComm.exe (CLI). "
        "Ejecuta TecknoComm para generar TM-MR001.Txt y lo importa automáticamente. "
        "También parsea archivos TM-MR001.Txt generados manualmente."
    ),
    "driver_class": "SundialDriver",
    "parser_class": "SundialParser",
    "ui_features": {
        "file_import": True,
        "terminal_management": False,
        "network_import": False,
        "file_extensions": [".txt"],
        "file_name_patterns": ["TM-MR001.txt"],
        "file_format_hint": "TM-MR001.txt de Sundial ERTeckno",
    },
    "connection_fields": [
        {
            "name": "tecknocomm_exe",
            "label": "Ruta a TecknoComm.exe",
            "type": "text",
            "default": "",
            "required": True,
        },
        {
            "name": "output_file",
            "label": "Archivo TM-MR001.Txt",
            "type": "text",
            "default": "",
            "required": True,
        },
        {
            "name": "db_password",
            "label": "Contraseña BD TecknoComm",
            "type": "password",
            "default": "",
            "required": True,
        },
        {
            "name": "db_user",
            "label": "Usuario TecknoComm",
            "type": "text",
            "default": "",
            "required": True,
        },
        {
            "name": "db_client",
            "label": "Cliente TecknoComm",
            "type": "text",
            "default": "",
            "required": True,
        },
        {
            "name": "terminals",
            "label": "N° terminales a sincronizar (ej: 1,2,3)",
            "type": "text",
            "default": "",
            "required": True,
        },
        {
            "name": "timeout",
            "label": "Timeout por terminal (segundos)",
            "type": "number",
            "default": "120",
        },
    ],
}
