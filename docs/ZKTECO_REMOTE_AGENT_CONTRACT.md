# ZKTeco Remote Agent — contrato transitorio de integración

> Este contrato describe el adaptador remoto actual. El diseño objetivo con
> agente autónomo por sede y comandos salientes está definido en
> [PLAN_INTEGRACION_TERMINALES_AGENTES.md](PLAN_INTEGRACION_TERMINALES_AGENTES.md).
> El contrato `/api/agents/v1` de dicho plan será el definitivo; no ampliar este
> adaptador transitorio para nuevas instalaciones.

SRTime usa el addon **ZKTeco Remote Agent** cuando la terminal no es alcanzable
desde el servidor central. El agente se instala dentro de la sede y es el único
componente que usa `pyzk` y conoce la red local de los relojes.

El servidor central no recibe ni persiste archivos. El agente responde registros
normalizados y SRTime los ingresa mediante el mismo `import_from_driver` usado
por ZKTeco embebido.

## Requisitos del agente

- HTTPS obligatorio, con certificado válido o una CA privada instalada en SRTime.
- Autenticación `Authorization: Bearer <token>`.
- El agente no debe exponer su puerto a Internet: VPN, reverse proxy privado o
  firewall limitado a la IP del servidor SRTime.
- El token se configura como secreto del terminal y nunca se devuelve por API.

## API v1 mínima

`POST /v1/terminals/{id}/health` devuelve metadatos no sensibles:

```json
{"name":"Puerta Norte","serial_number":"ABC123","mac":"00:11:22:33:44:55"}
```

`POST /v1/terminals/{id}/attendance` devuelve:

```json
{"logs":[{"identifier":"101","occurred_at":"2026-07-26T06:02:00","mark_type":0,"flags":"0100100"}]}
```

El agente puede descargar todos los eventos disponibles: SRTime deduplica por
identificador, fecha, hora y tipo de marca antes de guardar en `AttendanceLog`.
La descarga manual y la programada usan exactamente este contrato.
