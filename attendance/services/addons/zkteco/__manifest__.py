manifest = {
    "name": "ZKTeco",
    "type": "both",
    "description": "Conexión directa con terminales ZKTeco por red (pyzk) e importación de att logs exportados por USB.",
    "driver_class": "ZKTecoDriver",
    "parser_class": "ZKTecoParser",
    "connection_fields": [
        {"name": "ip", "label": "Dirección IP", "type": "text", "default": "192.168.1.201"},
        {"name": "port", "label": "Puerto", "type": "number", "default": "4370"},
        {"name": "password", "label": "Contraseña Com (0=Sin Clave)", "type": "text", "default": "0"},
    ],
}
