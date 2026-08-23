# Plan de alineación Windows/PySide6/SQLite

## Objetivo

Entregar una nueva distribución Windows de SRTime que conserve SQLite como modo
local predeterminado, permita PostgreSQL de forma opcional y quede alineada
funcionalmente con la versión web/PostgreSQL `v0.9.0-beta.1`.

La lógica de negocio, modelos, seguridad, importación y procesamiento debe
seguir siendo compartida. PySide6 y la web sólo difieren en presentación,
instalación y modo de conexión a base de datos.

## Estado de partida

La base SQLite distribuida en `dist/SRTIime_Win/attendance.db` corresponde a
una versión anterior y no registra `alembic_version`. Le faltan columnas que
ya existen en el contrato actual:

- `auth_user.token_version`.
- `device_terminal.connection_params`.
- `processed_attendance.previous_status`.
- `processed_attendance.pending_first_in`.
- `processed_attendance.pending_last_out`.
- `processed_attendance.pending_justification`.
- `processed_attendance.requested_by`.

La migración no debe ejecutarse por primera vez sobre una base de usuario sin
una copia de seguridad previa y una prueba sobre una copia equivalente.

## Fase 1 — Contrato de paridad

1. Tomar los modelos SQLAlchemy y migraciones actuales como fuente de verdad.
2. Documentar por tabla: columnas, tipos SQLite/PostgreSQL, constraints,
   migración y prueba asociada.
3. Identificar explícitamente tipos o SQL específicos de PostgreSQL para
   ofrecer su equivalente SQLite.
4. Mantener PostgreSQL como contrato de operación web y SQLite como contrato
   de escritorio local, sin divergencias funcionales deliberadas.

## Fase 2 — Upgrade SQLite versionado

1. Registrar versión de esquema con Alembic o una tabla de versión explícita.
2. Hacer que las migraciones sean ejecutables en SQLite.
3. Usar `batch_alter_table` cuando SQLite no soporte el cambio de tabla de
   forma directa.
4. Mantener `init_database()` para bases nuevas; no usarlo como único método
   de actualización de una base existente.
5. Hacer las migraciones idempotentes y documentar el rollback posible.
6. Implementar primero las siete columnas pendientes identificadas en el
   estado de partida.

## Fase 3 — Pruebas de bases

Preparar y automatizar tres escenarios:

1. SQLite nueva creada desde cero.
2. SQLite antigua equivalente a la base distribuida actualmente.
3. SQLite ya actualizada, para validar idempotencia.

En cada escenario comprobar:

- Integridad de empleados, turnos, marcaciones y asistencia procesada.
- Login, roles, cambio de contraseña y revocación de sesión.
- Terminales y `connection_params`.
- Justificaciones y aprobaciones.
- Importación, reproceso y reportes.
- Apertura posterior sin que la migración se ejecute nuevamente.

Ejecutar además pruebas de integración PostgreSQL con los mismos casos de
negocio para establecer paridad entre motores.

## Fase 4 — Alineación PySide6

Actualizar la interfaz Windows para exponer el mismo flujo funcional que web:

- Workers/QThread para importación, procesamiento, reproceso y exportación.
- Barra de progreso, resultado y errores sin bloquear la interfaz.
- Filtros, búsqueda y ordenamiento de movimientos.
- Gestión de roles, usuarios y validación de contraseñas.
- Justificación y aprobación según permisos.
- Mensajes y validaciones compartidos cuando la lógica sea de negocio.

La lógica debe permanecer en `services/`; PySide6 sólo debe coordinar y
presentar resultados.

## Fase 5 — Perfiles Windows

| Perfil | Motor | Uso |
|---|---|---|
| Desktop local | SQLite | Equipo único, uso offline o instalación simple. |
| Desktop centralizado | PostgreSQL | Varios equipos, datos centralizados y backups corporativos. |

SQLite es el valor por defecto del instalador Windows. PostgreSQL se configura
de forma explícita y nunca se incluyen sus credenciales en el ejecutable.

### Archivo de configuración de escritorio

La distribución incluye `attendance/.env.desktop.example`. El operador lo copia
como `attendance/.env` y comienza con `DB_ENGINE=sqlite` y
`SQLITE_DB_PATH=attendance.db`. No necesita servidor ni credenciales de base de
datos para el perfil local.

Si la edición Windows se conecta a un PostgreSQL corporativo, el operador cambia
explícitamente `DB_ENGINE=postgres` y completa `DB_HOST`, `DB_PORT`, `DB_USER`,
`DB_PASS` y `DB_NAME` en ese mismo `.env`. El archivo real está ignorado por Git;
el template no contiene secretos. Para SQLite, `migrate_sqlite.py` ahora usa
`SQLITE_DB_PATH`; para PostgreSQL se usa `alembic upgrade head`.

## Fase 6 — Nueva distribución Windows

1. Ejecutar pruebas SQLite y paridad antes de empaquetar.
2. Construir el ejecutable PySide6 con Nuitka.
3. Excluir `.env`, credenciales, bases de QA, logs y archivos biométricos del
   paquete.
4. Preparar instalador/upgrade que haga backup de `attendance.db` antes de
   migrar.
5. Verificar esquema e integridad tras el upgrade.
6. Conservar un procedimiento de restauración del backup ante error.
7. Probar instalación limpia y actualización en un Windows aislado.

## Criterios de salida

La distribución Windows se considera alineada cuando:

- Una SQLite antigua se actualiza sin pérdida de datos.
- Una SQLite nueva contiene el contrato funcional actual.
- Las pruebas de paridad SQLite/PostgreSQL pasan.
- Web y PySide6 cubren los mismos flujos críticos.
- El ejecutable Nuitka se valida en una PC Windows limpia.
- Se documentan instalación, upgrade, backup y rollback.

## Versión propuesta

La entrega debe identificarse como **`v0.9.0-beta.2`**: contiene cambios de
esquema y una distribución Windows distinta de `v0.9.0-beta.1`.
