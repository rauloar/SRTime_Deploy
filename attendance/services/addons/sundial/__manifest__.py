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
    "connection_fields": [
        {
            "name": "tecknocomm_exe",
            "label": "Ruta a TecknoComm.exe",
            "type": "text",
            "default": r"C:\TecknoComm\TecknoComm.exe",
        },
        {
            "name": "output_file",
            "label": "Archivo TM-MR001.Txt",
            "type": "text",
            "default": r"C:\TecknoComm\TM-MR001.Txt",
        },
        {
            "name": "db_password",
            "label": "Contraseña BD TecknoComm",
            "type": "text",
            "default": "TecknoComm",
        },
        {
            "name": "db_user",
            "label": "Usuario TecknoComm",
            "type": "text",
            "default": "admin",
        },
        {
            "name": "db_client",
            "label": "Cliente TecknoComm",
            "type": "text",
            "default": "admin",
        },
        {
            "name": "terminals",
            "label": "N° terminales a sincronizar (ej: 1,2,3)",
            "type": "text",
            "default": "1",
        },
        {
            "name": "timeout",
            "label": "Timeout por terminal (segundos)",
            "type": "number",
            "default": "120",
        },
    ],
}
