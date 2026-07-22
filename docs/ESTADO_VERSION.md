# Estado de versión de SRTime

## Versión actual: Beta 0.9.0-beta.1

SRTime se clasifica como **Beta**, no como Alfa ni como versión final 1.0.

La aplicación ya permite un flujo de uso completo: instalación local con
PostgreSQL, creación del administrador, importación TM-MR001, visualización de
marcaciones raw, procesamiento de asistencia, gestión de usuarios y roles, y
exportación. Las pruebas QA recientes validaron importación, procesamiento y
consistencia entre logs raw y procesados.

## Alcance aprobado para Beta

- Uso interno, QA y pilotos controlados.
- PostgreSQL como base de datos de operación.
- Importaciones manuales, procesamiento pendiente e histórico.
- Monitoreo de progreso para importación y procesamiento en la interfaz web.

## Condiciones antes de 1.0

La promoción a **1.0.0** requiere evidencia aprobada de:

1. Prueba de carga con el volumen real de terminales, empleados y marcaciones.
2. Backup PostgreSQL, restauración comprobada y procedimiento de recuperación.
3. Prueba end-to-end del flujo de instalación, importación, reproceso, roles y
   exportaciones en un entorno equivalente a producción.
4. Revisión de seguridad y operación: contraseñas, permisos del archivo de
   entorno, logs y actualización de dependencias.
5. Decisión de despliegue para trabajos en segundo plano. El monitor de progreso
   actual es local en memoria y está diseñado para la ejecución QA de un solo
   proceso; una instalación multiworker requiere persistencia compartida.

## Criterio de cambio de versión

- **Alfa**: cambios frecuentes, sin flujo de usuario estable. SRTime ya superó
  esta etapa.
- **Beta 0.9.0-beta.1**: flujo funcional estable sujeto a validación operativa y de
  rendimiento. Estado actual.
- **1.0.0**: condiciones anteriores cumplidas y aprobadas por QA/operaciones.
