manifest = {
    "name": "ZKTeco",
    "type": "both",
    "description": "Conexión directa con terminales ZKTeco por red (pyzk) e importación de att logs exportados por USB.",
    "driver_class": "ZKTecoDriver",
    "parser_class": "ZKTecoParser",
    "connection_fields": [
        {"name": "ip", "label": "Dirección IP", "type": "text", "default": "", "required": True},
        {"name": "port", "label": "Puerto", "type": "number", "default": "4370"},
        {"name": "password", "label": "Contraseña Com (vacío=sin clave)", "type": "password", "default": ""},
    ],
}
