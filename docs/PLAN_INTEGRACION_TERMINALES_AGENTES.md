# Plan de integración de terminales — modelo SRTime Agent

**Estado:** plan aprobado para implementación futura. No reemplaza todavía el
modo directo existente; define el destino arquitectónico recomendado.

## Objetivo

Separar la comunicación con relojes biométricos del backend central de SRTime.
El servidor de asistencia conserva su responsabilidad de validar, deduplicar y
guardar movimientos raw; cada sede controla localmente sus terminales mediante
un agente, de forma equivalente al patrón Odoo/IoT.

```text
Terminal ZKTeco ── pyzk ── SRTime Terminal Agent (sede)
                                  │ HTTPS + token
                                  ▼
                         API central SRTime
                                  │
                                  ▼
                   AttendanceLog → procesamiento existente
```

## Principios de diseño

- El backend central no abre conexiones `pyzk` ni ejecuta agendas de terminales.
- El agente sólo transporta movimientos normalizados; no procesa asistencias ni
  modifica `ProcessedAttendance`.
- Todos los orígenes convergen en `_ingest_rows()` y conservan la clave de
  deduplicación `(raw_identifier, date, time, mark_type)`.
- El agente puede estar en Windows o Linux y opera dentro de la LAN de su sede.
- El acceso entre sede y servidor central usa HTTPS y token revocable. No se
  expone el puerto de la terminal a Internet.
- La UI administra configuración y estado; no contiene claves de terminal.

## Responsabilidades

| Componente | Responsabilidad |
|---|---|
| Terminal biométrica | Registra marcaciones y expone protocolo del fabricante. |
| SRTime Terminal Agent | Usa pyzk, agenda descargas, reintenta, normaliza y entrega lotes. |
| API central | Autentica agentes, recibe lotes, valida, deduplica y persiste raw. |
| Motor de asistencia | Procesa raw cuando RRHH lo solicita, sin cambios. |
| UI Terminales | Alta de sede/agente/terminal, estado, descarga solicitada y agenda. |

## Flujo operativo

### Alta

1. Root registra una **sede** y genera un token de agente de un solo uso.
2. Se instala el agente en un equipo con acceso LAN a los relojes.
3. El agente se registra contra el servidor y recibe su identidad revocable.
4. Supervisor registra la terminal, vinculándola a ese agente y a su driver.
5. El agente prueba conectividad local y reporta serie, firmware y estado.

### Descarga on-demand

1. Supervisor selecciona una terminal y pulsa **Bajar registros**.
2. La API central crea un comando pendiente para el agente, sin conectarse al reloj.
3. El agente consulta comandos o mantiene un canal saliente seguro, descarga con pyzk y
   envía un lote normalizado.
4. La API confirma la ingesta; la card muestra cantidad, estado y fecha de descarga.
5. Los movimientos quedan en la tabla raw actual para el procesamiento habitual.

### Descarga automática

1. Supervisor define intervalo y franja horaria en la card de la terminal.
2. La configuración se entrega al agente correspondiente.
3. El scheduler del agente ejecuta la descarga local y publica el lote.
4. Si falla, aplica backoff local y reporta el error. El servidor central solo guarda el
   estado y no intenta comunicarse directamente con el reloj.

## Contratos de integración

El agente y el servidor usarán una API versionada bajo `/api/agents/v1`.

| Operación | Dirección | Propósito |
|---|---|---|
| `POST /register` | agente → central | Activación con token de un solo uso. |
| `POST /heartbeat` | agente → central | Estado, versión y conectividad. |
| `GET /commands` | agente → central | Descargas on-demand y cambios de agenda. |
| `POST /commands/{id}/result` | agente → central | Resultado técnico del comando. |
| `POST /terminals/{id}/logs` | agente → central | Lote de movimientos normalizados. |

Un movimiento transportado tiene el contrato canónico:

```json
{
  "identifier": "000000000000101",
  "occurred_at": "2026-07-26T06:03:00",
  "mark_type": 0,
  "flags": "0100100"
}
```

La API central convierte `occurred_at` a fecha/hora y lo ingesta usando el
servicio compartido. El agente no envía archivos ni rutas locales.

## Datos persistentes previstos

No se agregan tablas para duplicar movimientos raw. Se agregarán entidades
técnicas separadas de asistencia:

- `terminal_site`: nombre, zona horaria y estado.
- `terminal_agent`: sede, identidad pública, token hasheado, última señal, versión y estado.
- `device_terminal`: referencia a sede/agente y configuración de agenda declarativa.
- `agent_command`: comando, terminal, estado, solicitante, fecha y resultado resumido.

Los tokens se guardan hasheados; las contraseñas Com de ZKTeco se almacenan
solamente en el agente de la sede, cifradas con una clave local. No viajan de
vuelta ni quedan disponibles para la UI central.

## Plan por fases

### Fase 0 — Consolidación del modo directo

1. Validar addon y campos obligatorios al registrar terminales.
2. Unificar los dos endpoints actuales de pull en uno canónico.
3. Normalizar las excepciones de driver como errores operativos 400.
4. Conservar modo directo únicamente como opción de instalación simple/LAN.

**Criterio de salida:** alta, prueba y pull directo con logs auditables y sin endpoints duplicados.

### Fase 1 — Contrato y recepción central

1. Crear modelos, migraciones y RBAC para sede, agente y comando.
2. Implementar autenticación de agente con tokens revocables y rotación.
3. Crear endpoint de recepción de lotes que reutilice `_ingest_rows()`.
4. Agregar auditoría de agente, lote, comando y usuario solicitante.

**Criterio de salida:** un cliente simulado puede registrar agente, enviar logs y producir el
mismo resultado raw que una importación de archivo.

### Fase 2 — SRTime Terminal Agent

1. Crear paquete ejecutable independiente, sin UI web y con configuración local mínima.
2. Implementar adaptador pyzk y almacenamiento local temporal para reintentos.
3. Implementar heartbeat, consulta de comandos y publicación idempotente de lotes.
4. Implementar scheduler local con intervalo/franja y backoff exponencial.
5. Empaquetar para Windows y Debian; documentar instalación por sede.

**Criterio de salida:** el agente sigue descargando tras una caída temporal del servidor y
publica registros sin duplicarlos cuando se restablece la conexión.

### Fase 3 — UI Web y PySide6

1. Reemplazar la card actual por el modelo Sede → Agente → Terminal.
2. Mostrar salud del agente, última señal, estado de comando y última ingesta.
3. El botón on-demand crea un comando; no llama pyzk desde FastAPI.
4. Configurar la agenda y mostrar que la ejecución ocurre en la sede.
5. Replicar el mismo flujo en PySide6 después de la aprobación Web.

**Criterio de salida:** QA puede administrar una sede remota sin acceso de red directo del
servidor central a la terminal.

### Fase 4 — Migración y retirada controlada

1. Migrar terminales directas, una sede por vez, sin borrar configuraciones existentes.
2. Comparar cantidades de logs raw y deduplicados durante un período de convivencia.
3. Desactivar scheduler central para terminales migradas.
4. Mantener modo directo como compatibilidad hasta la decisión explícita de retirarlo.

## Seguridad y operación

- TLS obligatorio entre agente y central; preferir VPN de sitio a sitio cuando exista.
- Tokens por agente, con expiración, revocación y rotación por root.
- Límites de tamaño de lote, rate limit y validación estricta de esquema.
- Idempotencia por la clave raw existente; el agente reintenta sin temor a duplicar.
- No registrar secretos, payloads completos ni rutas de equipos en logs centrales.
- Métricas: última señal, terminales activas, edad de última descarga, errores consecutivos y cola de comandos.

## Estrategia de pruebas

1. Unitarios: validación, token, transformación a tupla canónica y deduplicación.
2. Integración: agente simulado, caída/reintento y comando on-demand.
3. Hardware: ZKTeco real en LAN de prueba, reloj desincronizado y desconexión de red.
4. Carga: lote grande, reenvío idempotente y múltiples sedes.
5. QA funcional: alta, estado, descarga manual, agenda, errores y recuperación.

## Decisiones pendientes

- Transporte del agente: polling saliente inicial (recomendado) o WebSocket posterior.
- Base local del agente: SQLite para cola y reintentos (recomendado).
- Administración de sedes: tabla propia o extensión futura de una entidad organizacional.
- Política de retención de comandos y telemetría.
