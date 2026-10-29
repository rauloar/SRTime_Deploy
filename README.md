# SRTime

SRTime es un sistema de gestión de asistencia que reúne marcaciones de empleados, las procesa según sus turnos y permite consultar y exportar resultados. Está pensado para trabajar con terminales biométricas y archivos de marcaciones.

## Funciones

- **Importación de marcaciones:** desde archivos de texto Sundial `TM-MR001.Txt` y exportaciones ZKTeco `att.dat`; también puede descargar registros por red desde terminales ZKTeco.
- **Gestión de terminales:** registro y configuración de equipos compatibles. El código incluye integraciones adicionales; la disponibilidad depende del modelo, la configuración y la validación del hardware.
- **Empleados, grupos y turnos:** administración de personas, asignación individual o por grupo, tolerancias y turnos que cruzan la medianoche.
- **Procesamiento de asistencia:** conserva las marcaciones originales y calcula asistencia, tardanzas, horas trabajadas, extras y registros incompletos. Permite gestionar justificaciones según los permisos de la cuenta.
- **Consultas y reportes:** movimientos crudos, asistencia procesada, tablero, analítica, reportes mensuales y exportaciones.
- **Feriados y ausencias:** administración de feriados y gestión de ausencias/justificaciones.
- **Control de acceso:** cuentas autenticadas y roles `viewer`, `supervisor`, `admin` (compatibilidad heredada) y `root`.

## Presentaciones

La suite ofrece dos formas de operar:

- **Escritorio Windows:** interfaz PySide6.
- **Web/API:** API FastAPI con una interfaz web estática generada con Next.js. En producción, FastAPI sirve la interfaz y la API desde el mismo servicio; no se necesita un servidor Node.js en ejecución.

Ambas presentaciones comparten la lógica de asistencia. PostgreSQL es la base recomendada para el despliegue web; SQLite se mantiene como opción compatible, especialmente para escritorio.

## Documentación

- [Manual de usuario](https://github.com/rauloar/SRTime_Deploy/blob/deploy/pseudoprod-pro/docs/MANUAL_USUARIO.md)
- [Manual técnico](https://github.com/rauloar/SRTime_Deploy/blob/deploy/pseudoprod-pro/docs/MANUAL_TECNICO.md)
- [Especificaciones de despliegue](https://github.com/rauloar/SRTime_Deploy/blob/deploy/pseudoprod-pro/docs/ESPECIFICACIONES_DESPLIEGUE.md)
- [Acceso desde la red local](https://github.com/rauloar/SRTime_Deploy/blob/deploy/pseudoprod-pro/docs/ACCESO_LAN_WINDOWS.md)
- [Contrato del agente ZKTeco remoto](https://github.com/rauloar/SRTime_Deploy/blob/deploy/pseudoprod-pro/docs/ZKTECO_REMOTE_AGENT_CONTRACT.md)
- [Diseño de addons y formatos de importación](https://github.com/rauloar/SRTime_Deploy/blob/deploy/pseudoprod-pro/ADDONS.md)

## Estado

SRTime se encuentra en etapa beta. Las integraciones dependen de la combinación de terminal, firmware, red y formato de datos, por lo que conviene validar el entorno antes de ponerlo en operación.

## Licencia y uso comercial

SRTime se distribuye bajo **Business Source License 1.1 (BUSL-1.1)**. El código puede inspeccionarse, copiarse, modificarse, redistribuirse y usarse para fines no productivos conforme a [LICENSE](LICENSE). La licencia no concede uso productivo; para usar SRTime en producción se requiere un acuerdo de licencia comercial con el titular, salvo que esa versión ya haya llegado a su fecha de cambio.

Para consultar una licencia comercial, contactar al titular a través de su [perfil de GitHub](https://github.com/rauloar).

Cada versión pasa a estar disponible bajo **GNU GPL versión 2.0 o posterior** cuatro años después de su primera distribución pública bajo BUSL-1.1, según los términos de la licencia. La fecha se calcula por versión.

BUSL-1.1 no es una licencia de código abierto aprobada por OSI. Los componentes de terceros conservan sus propias licencias; consultar sus avisos antes de redistribuir una compilación.


