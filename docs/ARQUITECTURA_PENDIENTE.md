# Arquitectura pendiente

## Turnos que cruzan el día (22:00–06:00)

Esta mejora queda deliberadamente fuera de la primera entrega de Ausencias.
La versión actual permite procesar turnos nocturnos en el motor de asistencia,
pero el calendario de ausencias se limita a jornadas de lunes a viernes y no
debe inferir todavía si una jornada nocturna pertenece al día de inicio, al de
cierre o a ambos.

Antes de habilitar ausencias automáticas para 22:00–06:00 se deberá definir:

- La fecha laboral canónica de la jornada nocturna.
- El tratamiento de feriados en el inicio y en el cierre del turno.
- La planificación semanal por turno, en vez de asumir lunes a viernes.
- Los casos de descanso, licencia y fichadas parciales que cruzan medianoche.

Hasta esa definición, las pruebas funcionales de Ausencias se realizan sobre
turnos diurnos de lunes a viernes, como 06:00–14:00 y 14:00–22:00.
