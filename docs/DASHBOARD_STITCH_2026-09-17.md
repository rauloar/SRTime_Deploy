# Dashboard web basado en Stitch — 2026-09-17

Referencia local: `dash_stich/code.html`, `DESIGN.md` y `screen.png`.

La adaptación está en `attendance/web/app/components/DashboardTab.tsx` y
`dashboard.css`. Conserva SRTime y el logotipo existente, autenticación, navegación,
roles, temas claro/oscuro y export estático Next.js servido por FastAPI.

## Adaptación del diseño

- Cuatro indicadores con tendencias reales cuando hay más de una fecha.
- Evolución diaria apilada, con selector de jornadas o porcentajes.
- Anillo de distribución de registros procesados, incluyendo feriados.
- Comparación por grupos; pulsar un grupo identificado filtra el panel.
- Mapa por grupo y fecha de ausencias, incompletos y pendientes. La intensidad
  representa su proporción sobre jornadas procesadas no feriadas. Una celda sin
  jornadas muestra un guion, no un cero. Pulsar selecciona el día y el grupo si
  tiene una opción identificable; «Sin grupo» selecciona únicamente el día.
- Incidencias con acceso a las secciones existentes y estado de terminales.
- Filtros por fechas, grupo, turno y persona, vista de hoy y restablecimiento.
- Cancelación de consultas anteriores y protección contra respuestas desordenadas.

Todo proviene del contrato existente `/api/analytics/dashboard`. No se incluyen
mock data, supuestos de presencia en planta, pausas, comparaciones inventadas,
notificaciones externas ni motor de inferencia del prototipo. Los accesos a otras
secciones abren esas secciones; no transfieren filtros al destino.

## Validación

- ESLint, TypeScript y build Next.js estático: correctos.
- pytest: 146 passed, 1 skipped. Integración PostgreSQL opt-in: 1 passed.
- Alembic identifica head `c9d0e1f2a304`; SQL offline falla en la migración histórica
  `1cb2fbdaf750` por inspección de MockConnection. No se modificaron migraciones.
- `pip_audit` no está instalado en el venv canónico.
- Revisión automática en navegador no realizada: la herramienta falló al
  inicializar sus recursos locales. QA visual aprobado luego por el usuario; no se afirma cobertura automática de escritorio/móvil y ambos temas.

No se aplicaron migraciones ni se eliminaron datos. El esquema temporal de la
prueba PostgreSQL se revierte mediante rollback.

Auditoría npm de dependencias de producción: 0 vulnerabilidades.

Publicación autorizada por el usuario: tag de suite v0.9.0-beta.6.
