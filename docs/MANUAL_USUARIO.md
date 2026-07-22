# Manual de usuario de SRTime

> Versión de uso actual: **Beta 0.9.0-beta.1**. Es apta para operación y pruebas
> controladas; el equipo técnico debe validar el entorno antes de producción.

## Ingreso al sistema

Abrí SRTime en la dirección indicada por la persona técnica, normalmente
`http://127.0.0.1:8000/`.

Ingresá con tu usuario y contraseña de **SRTime**. No uses el usuario
`postgres`: ese usuario pertenece a la base de datos y no sirve para entrar a
la aplicación.

La primera cuenta se llama `admin`. Una persona con rol `root` puede crear más
cuentas desde **Usuarios Autorizados**.

## Qué puede hacer cada persona

- **Viewer**: consultar y exportar información.
- **Supervisor/Admin**: además puede cargar empleados, turnos, terminales e
  importaciones.
- **Root**: administra usuarios, acciones sensibles y aprobaciones.

Si no ves una opción, probablemente tu rol no tiene permiso. Pedí ayuda a una
persona con rol `root`; no compartas tu contraseña.

## Configuración inicial

La primera vez puede aparecer la pantalla **Configuración inicial**. Es para
la persona técnica: solicita datos de PostgreSQL y crea la primera cuenta
`admin`. Una persona usuaria no debe modificar esa información.

## Empleados y turnos

Antes de procesar asistencia, verificar:

1. Cada empleado está cargado en **Empleados** con su identificador correcto.
2. Cada empleado tiene asignado un turno.
3. El turno contiene hora de entrada, salida y tolerancia.

Los turnos nocturnos deben configurarse como tales para que SRTime relacione
correctamente una salida del día siguiente.

## Importar marcaciones

En **Importar** hay dos opciones:

### Desde archivo

1. Elegí **Buscar archivo** y seleccioná un `.txt`.
2. Elegí el formato/parser si corresponde.
3. Presioná **Importar TXT**.
4. Revisá el resultado: nuevos, duplicados y errores.

Podés importar el mismo archivo nuevamente: SRTime omite las marcaciones ya
registradas. El archivo original nunca se elimina.

### Desde red física

1. Elegí una terminal registrada.
2. Usá **Probar conexión** antes de descargar.
3. Presioná **Descargar memorias**.
4. Esperá el resumen y revisá los nuevos registros.

Si falla, verificá que la terminal esté encendida y conectada a la red. No
cambies IP, contraseña ni parámetros del reloj sin autorización.

## Procesar asistencia y reportes

Después de importar, ir a **Asistencia Procesada** y procesar pendientes. El
sistema calcula horas, tardanzas, extras e incompletos según el turno.

Revisá los registros `INCOMPLETO` antes de exportar. Las correcciones y
justificaciones requieren permisos superiores.

Usá las opciones de exportación para generar planillas o reportes. Confirmá el
período antes de compartir un archivo.

## Problemas frecuentes

- **Usuario o contraseña incorrectos**: verificá que uses tu cuenta de SRTime,
  no la cuenta PostgreSQL. Si continúa, pedí restablecimiento a un `root`.
- **Todos los registros son duplicados**: normalmente significa que ya se
  importaron; no es un error.
- **No se conecta a una terminal**: revisar energía, red, IP y permisos con
  soporte técnico.
- **No podés editar**: tu rol puede ser sólo de consulta.
