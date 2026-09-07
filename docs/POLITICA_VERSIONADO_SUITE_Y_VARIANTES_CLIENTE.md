# Política de versionado de la suite y variantes de cliente

## Objetivo

SRTime se entrega como una única suite: Web/FastAPI/PostgreSQL y Desktop/PySide6/SQLite comparten una versión funcional, aunque sus artefactos de instalación sean distintos. Esta política evita que una mejora puntual para un cliente se transforme en un fork permanente y difícil de actualizar.

## Fuente de verdad de la versión

- El tag Git de la suite es la referencia oficial de una entrega.
- Se usa SemVer: `vMAYOR.MENOR.PARCHE`, con el sufijo de pre-lanzamiento cuando corresponda, por ejemplo `v0.9.0-beta.4`.
- Web y Desktop no reciben números de producto independientes. Sus instaladores llevan el mismo número de la suite y un nombre de artefacto por plataforma.
- Cada entrega debe registrar el tag, commit, fecha, estado de QA, migraciones, addons habilitados y hash SHA-256 del artefacto en el registro de versiones.

Ejemplo:

| Elemento | Identificador |
| --- | --- |
| Suite fuente | `v0.9.0-beta.4` |
| Instalador Web | `SRTime-Web-Setup.exe` asociado a `v0.9.0-beta.4` |
| Instalador Desktop | `SRTime-Desktop-Setup.exe` asociado a `v0.9.0-beta.4` |

El nombre del instalador no sustituye al tag: el manifiesto de entrega y su checksum determinan exactamente qué se instaló.

## Cuándo cambia cada parte de la versión

| Cambio | Versión |
| --- | --- |
| Corrección compatible, seguridad o documentación | `PARCHE` |
| Funcionalidad compatible, addon, endpoint o UI nueva | `MENOR` |
| Cambio incompatible de API, datos, permisos o instalación | `MAYOR` |
| Trabajo aún no aprobado para entrega | sufijo `alpha`, `beta` o `rc` |

Una migración de base de datos compatible no obliga por sí sola a un cambio mayor, pero debe estar declarada, probada contra una copia de datos y documentada en la entrega.

## Regla para personalizaciones de clientes

Antes de desarrollar una necesidad específica se debe decidir, en este orden:

1. Configuración existente (`.env` o parámetros administrables), sin código específico.
2. Addon configurable y reutilizable por otros clientes.
3. Integración o extensión aislada del cliente, con contrato de compatibilidad.
4. Fork solo como última alternativa, con aprobación explícita y un plan de mantenimiento.

Las mejoras que sean genéricas deben volver al núcleo de SRTime. Una extensión de cliente no debe alterar silenciosamente el comportamiento global ni introducir credenciales, rutas, IPs, nombres de base de datos o datos del cliente en el repositorio de la suite.

## Identificación de extensiones de cliente

Una extensión se versiona separadamente del núcleo. No se modifica el tag oficial de la suite para representar una entrega particular.

Ejemplo de identificación:

```text
suite_tag: v0.9.0-beta.4
extension_id: acme-export
extension_version: 1.0.0
supported_suite: >=0.9.0-beta.4,<0.10.0
```

Si se necesita un tag Git privado para la extensión, se usa un espacio de nombres separado, por ejemplo `customer/acme/v0.9.0-beta.4-export.1`. Ese tag no reemplaza ni adelanta los tags oficiales `v*` de la suite.

Toda extensión debe tener un manifiesto técnico con:

- Identificador, responsable, cliente y propósito.
- Tag y commit base de la suite.
- Rango de versiones de suite compatibles.
- Addons, flags de configuración y dependencias adicionales.
- Migraciones de datos requeridas, estrategia de backup y reversión.
- Pruebas de QA mínimas y criterio de aceptación.
- Estado: activa, reemplazada, retirada o integrada al núcleo.

Los datos de clientes, credenciales y valores específicos viven fuera de Git, en la configuración protegida del despliegue.

## Migraciones y datos de cliente

Se aplica el contrato de [migración de datos](PLAN_CONTRATO_MIGRACION_CLIENTES.md): backup verificable, migración identificada e idempotente cuando sea posible, validación posterior y plan de reversión. Las migraciones específicas deben ser aditivas y tener propietario; no deben modificar logs raw ni eliminar datos como parte de una actualización automática.

Antes de actualizar un cliente personalizado se compara el manifiesto instalado con la nueva entrega. Si la extensión no declara compatibilidad con la nueva versión de suite, la actualización se detiene hasta validarla.

## Flujo de release

1. Congelar alcance y clasificar los cambios: núcleo, addon reutilizable o extensión de cliente.
2. Ejecutar pruebas de código, seguridad, migraciones y QA de las plataformas afectadas.
3. Actualizar documentación, registro de versiones y manifiestos de extensiones.
4. Revisar diferencias, `.gitignore`, secretos y artefactos antes de publicar.
5. Obtener la aprobación explícita de QA/release manager.
6. Crear el tag anotado de la suite.
7. Generar los artefactos desde ese tag, calcular SHA-256 y registrarlos.

No se etiqueta ni se publica un release mientras existan cambios funcionales sin verificar. Los builds de QA se identifican como tales y no se consideran una release, aunque su binario funcione.

## Ramas recomendadas

- `feature/<tema>` para trabajo reutilizable de la suite.
- `fix/<tema>` para correcciones.
- `customer/<cliente>/<extension>` únicamente para una extensión aislada.
- Las ramas de cliente no reciben cambios genéricos de forma exclusiva: dichos cambios se integran primero en la rama principal de producto y luego se consumen desde allí.

No se mantienen forks de larga vida salvo que exista contrato de soporte, responsable y calendario de sincronización con el núcleo.

## Estado operativo actual

La referencia vigente de la suite es `v0.9.0-beta.4`. El estado detallado y el historial se mantienen en [ESTADO_VERSION.md](ESTADO_VERSION.md) y [REGISTRO_VERSIONES_SUITE.md](REGISTRO_VERSIONES_SUITE.md).
