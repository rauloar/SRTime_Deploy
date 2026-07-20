# SRTime — Manual de Usuario

SRTime es el sistema de control de asistencias. Se usa desde el navegador, en la
dirección que le indique su administrador (por ejemplo `http://192.168.1.44/`).

---

## 1. Ingreso al sistema

1. Abra el navegador y vaya a la dirección del servidor.
2. Ingrese **usuario** y **contraseña**.
3. En el **primer ingreso** el sistema le pedirá **cambiar la contraseña** por una
   nueva. Elija una contraseña segura y guárdela.

### Roles
| Rol | Permisos |
|-----|----------|
| **root** | Acceso total: usuarios, configuración, aprobaciones |
| **supervisor** | Operación diaria; puede **solicitar** justificaciones |
| **viewer** | Solo consulta |

---

## 2. Panel principal (Dashboard)

Al ingresar verá un resumen del estado de asistencias del día: presentes,
ausentes, tarde e incompletos. Es el punto de partida para la operación diaria.

---

## 3. Empleados

Alta, edición y baja de empleados. Cada empleado puede tener asignado un **turno**.
Se puede **importar** y **exportar** el padrón de empleados.

---

## 4. Turnos

Definición de horarios de trabajo: hora de entrada y salida, tolerancias,
duración del break y **turnos nocturnos** (que cruzan la medianoche). El turno
asignado a cada empleado determina cómo se calculan sus horas.

---

## 5. Feriados

Carga del calendario de feriados, con opción de **recurrencia anual**. Los
feriados se consideran automáticamente al procesar la asistencia.

---

## 6. Terminales

Registro de los relojes biométricos (terminales ZKTeco). Desde aquí se gestionan
los dispositivos desde los que se importan las marcaciones.

---

## 7. Importar marcaciones

Carga de los registros de entrada/salida provenientes de las terminales. Una vez
importados, el sistema los **procesa** contra los turnos para calcular asistencia
y horas trabajadas.

---

## 8. Asistencias procesadas

Listado del resultado del procesamiento por empleado y fecha, con su **estado**:

| Estado | Significado |
|--------|-------------|
| PRESENTE | Jornada completa y correcta |
| TARDE | Ingreso fuera de tolerancia |
| AUSENTE | Sin marcaciones |
| INCOMPLETO | Falta una marcación (p. ej. entró pero no salió) |
| PENDIENTE | Justificación solicitada, a la espera de aprobación |

### Justificaciones (flujo de aprobación)
1. El **supervisor** solicita justificar un registro (estado → **PENDIENTE**).
2. El **root** **aprueba** o **rechaza** la solicitud.
3. Al aprobarse, el registro toma el estado justificado; al rechazarse, vuelve a
   su estado anterior.

---

## 9. Reportes

Generación de reportes de asistencia exportables en **Excel** y **PDF**
(horizontal A4). Permiten filtrar por período y empleado para entregar o archivar.

---

## 10. Recomendaciones

- Cambie su contraseña inicial y no la comparta.
- Importe las marcaciones con regularidad para mantener el tablero al día.
- Ante un estado **INCOMPLETO** inesperado, verifique las marcaciones de la
  terminal antes de justificar.
- Si no puede ingresar, contacte a su administrador (rol root).
