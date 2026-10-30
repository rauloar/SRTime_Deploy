manifest = {
    "name": "Hikvision (ISAPI)",
    "version": "1.0",
    "type": "driver",
    "description": "Conexión directa con terminales Hikvision por red usando la API REST ISAPI (Pull on-demand).",
    "driver_class": "HikvisionDriver",
    # Lo que informa test_connection, en el orden en que se muestra al conectar.
    "connection_details": [
        {"name": "name", "label": "Dispositivo"},
        {"name": "model", "label": "Modelo"},
        {"name": "serial_number", "label": "Número de serie"},
        {"name": "mac", "label": "MAC"},
        {"name": "firmware", "label": "Firmware"},
        {"name": "time", "label": "Hora del reloj"},
    ],
    "connection_fields": [
        {"name": "ip",       "label": "Dirección IP",  "type": "text",     "default": "", "required": True},
        {"name": "port",     "label": "Puerto HTTP",   "type": "number",   "default": "80"},
        {"name": "username", "label": "Usuario",       "type": "text",     "default": "", "required": True},
        {"name": "password", "label": "Contraseña",    "type": "password", "default": ""},
        {"name": "timeout", "label": "Timeout HTTP (segundos)", "type": "number", "default": "10"},
        {"name": "timezone", "label": "Zona horaria ISAPI (fallback)", "type": "text", "default": ""},
        {"name": "event_minor", "label": "Filtro minor ISAPI (0=todos)", "type": "number", "default": "0"},
    ],
}
