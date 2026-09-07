# SRTime — Plan de implementación del contrato de migración de clientes

**Estado:** plan de arquitectura; no autoriza todavía cambios de datos ni de código.  
**Ámbito:** actualizaciones de la suite SRTime y mejoras particulares por cliente.

## 1. Decisiones de versión

1. Un tag Git identifica la **suite SRTime completa**, nunca solamente Web o
   Desktop. Ejemplo: `v0.9.0-beta.4` cubre el núcleo compartido, PySide6,
   FastAPI/Web, modelos, migraciones y documentación.
2. Nuitka Web y PyInstaller Windows son artefactos de distribución de ese mismo
   tag. Pueden construirse o validarse en fechas distintas, pero no reciben una
   versión de producto diferente.
3. Una mejora particular no debe convertirse en un fork permanente. Se entrega
   como una extensión versionada y compatible con una versión base de la suite.

## 2. Objetivo del contrato

Toda actualización debe poder responder, antes de tocar una instalación:

| Pregunta | Evidencia requerida |
|---|---|
| ¿Desde qué versión se actualiza? | Tag de suite, hash de build y revisión Alembic/SQLite. |
| ¿A qué versión se actualiza? | Tag objetivo y manifiesto de distribución. |
| ¿Qué datos cambian? | Esquema, tablas, columnas, transformación e impacto. |
| ¿Cómo se recupera? | Backup verificado y procedimiento de rollback. |
| ¿Quién lo autorizó? | Responsable técnico y responsable del cliente. |
| ¿Cómo se validó? | Checklist firmado con resultados antes/después. |

El contrato protege tanto datos raw como configuración, usuarios, turnos,
terminales, justificaciones y asistencia procesada.

## 3. Inventario obligatorio por instalación

Antes de una migración se genera un manifiesto local, sin exponer secretos:

```text
cliente_id / instalación_id
tag de suite actual
hash del artefacto instalado
motor: postgres | sqlite
revisión Alembic (PostgreSQL) o versión de esquema SQLite
addons habilitados
cantidad de empleados, logs raw y movimientos procesados
fecha de backup y checksum
```

El manifiesto se almacena junto al backup con permisos restringidos. No incluye
`DB_PASS`, claves Fernet, JWT, contraseñas de terminal ni datos biométricos.

## 4. Tipos de actualización

| Tipo | Ejemplo | Tratamiento |
|---|---|---|
| Sin datos | CSS, texto, mejora de UI | Reemplazo de artefacto + smoke test. |
| Aditiva | Nueva columna nullable/default, nuevo addon | Migración versionada, compatible hacia atrás. |
| Transformación | Normalizar identificadores o migrar horarios | Script idempotente, reporte antes/después y backup obligatorio. |
| Riesgosa | Eliminar/combinar columnas, cambiar semántica de asistencia | Fase temporal de convivencia, aprobación explícita y rollback probado. |
| Personalizada | Regla de un cliente, reporte o integración propia | Módulo/extensión versionado, sin modificar el núcleo salvo aprobación de producto. |

## 5. Preflight de esquema implementado para Web/PostgreSQL

Desde la siguiente compilación del instalador Web, el modo **Actualizar**
ejecuta `RUN_DB_SCHEMA_CHECK=true` antes de crear el backup o ejecutar Alembic.
La comprobación es de solo lectura y no expone credenciales: produce estado,
revisión actual y destino, tablas detectadas y faltantes de forma controlada.

| Estado detectado | Acción del instalador |
| --- | --- |
| Base vacía | Permitida: se crea el esquema actual y se registra la revisión Alembic. |
| SRTime completo sin tabla `alembic_version` | Permitida: se valida contra el modelo actual y se registra la revisión sin alterar datos. |
| Revisión Alembic reconocida anterior | Permitida: backup verificado y `alembic upgrade head`. |
| Revisión Alembic actual y esquema completo | Permitida: verificación y actualización de binarios; Alembic no aplica cambios. |
| Base SRTime parcial sin metadata Alembic | **Bloqueada**: no se marca como actual ni se ejecuta migración. |
| Revisión Alembic desconocida o metadata inválida | **Bloqueada**: requiere análisis de la versión origen. |
| Revisión en `head` con columnas/tablas faltantes | **Bloqueada**: se considera inconsistencia física del esquema. |
| Base no-SRTime no vacía | **Bloqueada**: no se reutiliza ni modifica. |

Para una revisión Alembic anterior conocida, Alembic conserva la autoridad sobre
el camino incremental. Al finalizar, SRTime verifica que todas las tablas y
columnas definidas por el modelo actual estén presentes. Si la validación falla,
el proceso informa error y el backup previo queda disponible para restaurar.

El instalador no inicia el servicio nuevo si el script de actualización devuelve
error. Los binarios pueden haber sido copiados, pero la base no queda sellada
como versión nueva; se debe resolver el diagnóstico y reintentar la instalación
o recuperar el backup según corresponda.

## 6. Flujo operativo propuesto

```text
Solicitud → análisis de impacto → diseño de migración → prueba clonada
→ aprobación → backup verificable → preflight → migración → validación
→ monitoreo → cierre documentado
```

### Fase A — Análisis y diseño

1. Registrar solicitud, alcance, cliente, responsable y versión base.
2. Clasificar el cambio según la tabla anterior.
3. Definir migración de esquema, transformación de datos, compatibilidad y
   estrategia de reversión.
4. Añadir pruebas de regresión al repositorio principal.
5. Si es personalizado, definir el módulo de extensión y su compatibilidad:

   ```text
   extension_id
   customer_id
   suite_version_min / suite_version_max
   schema_revision_min
   feature_flags requeridos
   ```

### Fase B — Validación en copia controlada

1. Restaurar un backup anonimizado o una copia autorizada en un entorno aislado.
2. Ejecutar migración más transformación dos veces: la segunda debe ser segura
   e idempotente.
3. Comparar conteos y hashes lógicos de datos críticos:
   empleados, terminales, turnos, logs raw, asistencia procesada y cuentas.
4. Ejecutar pruebas de importación, reproceso y login según addons habilitados.
5. Medir duración, espacio requerido y ventana de mantenimiento.

### Fase C — Preflight en cliente

1. Confirmar tag/artefacto actual y motor de base.
2. Verificar espacio libre, conectividad, permisos, versión PostgreSQL o
   integridad de SQLite.
3. Detener el servicio o impedir escrituras durante la ventana, según motor.
4. Crear backup consistente y verificar restauración o checksum antes de
   continuar.
5. Generar manifiesto de inicio y obtener aprobación del cliente.

### Fase D — Ejecución

1. Instalar el artefacto de la suite con el tag objetivo.
2. Aplicar Alembic en PostgreSQL con `alembic upgrade head`, o el migrador
   SQLite idempotente para Desktop.
3. Ejecutar la transformación específica, si existe, bajo una transacción o
   lotes auditables.
4. Guardar reporte: filas leídas, creadas, actualizadas, omitidas y errores.
5. No borrar datos raw. Cualquier limpieza requiere una autorización separada
   y un backup recuperable.

### Fase E — Validación y cierre

1. Verificar revisión de esquema y arranque del servicio/aplicación.
2. Hacer smoke test: login, empleados, terminales, importación, movimientos y
   procesamiento.
3. Para ZKTeco, verificar conexión, descarga y que `punch` produzca
   Entrada/Salida correctamente.
4. Guardar manifiesto final, evidencia de pruebas y aceptación del cliente.
5. Mantener monitoreo reforzado y un canal de rollback durante el período
   acordado.

## 7. Reglas por motor de base de datos

### PostgreSQL

- Es el contrato de producción Web.
- Todo cambio de modelo requiere migración Alembic explícita.
- Realizar backup con `pg_dump --format=custom`; verificar que se puede listar o
  restaurar antes de migrar.
- Las transformaciones masivas deben usar transacción, batches y logs de avance.

### SQLite

- Es el modo normal Desktop y debe conservar el mismo modelo lógico.
- Antes de actualizar, copiar el archivo `.db` cerrado y calcular checksum.
- `migrate_sqlite.py` debe ser idempotente y cubrir bases históricas soportadas.
- Nunca reemplazar una SQLite existente por una vacía durante una actualización.

## 8. Implementación técnica futura

1. Crear `services/migrations/` con un contrato común:
   `preflight()`, `apply()`, `verify()`, `rollback_instructions()` y `report()`.
2. Crear un manifiesto JSON con esquema versionado y sin secretos.
3. Extender el comando de solo lectura de preflight ya implementado para que
   genere también el manifiesto de inventario por instalación.
4. Añadir un comando de backup/verificación por motor, sin ejecutar migraciones.
5. Registrar transformaciones como módulos idempotentes identificados por versión.
6. Añadir una tabla o archivo de auditoría de migración por instalación, sólo
   después de definir política de retención y protección de datos.
7. Incorporar un modo de mantenimiento para impedir importaciones y reprocesos
   durante cambios de datos.

## 9. Criterios de aceptación

- La migración identifica sin ambigüedad versión origen y destino.
- Un backup restaurable existe antes de cualquier cambio.
- El proceso no incluye secretos en logs, manifiestos ni soporte.
- Repetir el proceso no duplica ni degrada datos.
- Los logs raw mantienen conteo e identidad; cualquier diferencia es explicada
  y aprobada.
- La mejora de cliente se puede actualizar o deshabilitar sin bifurcar el core.
- Web y PySide6 continúan leyendo el mismo contrato de datos.

## 10. Decisiones pendientes antes de implementar

1. Retención de backups y reportes por tipo de cliente.
2. Ventana máxima de mantenimiento y política de rollback.
3. Catálogo de extensiones permitidas y mecanismo de firma/aprobación.
4. Responsable autorizado para ejecutar migraciones en cada cliente.
