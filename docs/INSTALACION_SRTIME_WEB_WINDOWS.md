# Instalación de SRTime Web en Windows

Esta guía corresponde al instalador `SRTime-Web-Setup.exe` de la versión
`v0.9.0-beta.4`, que entrega SRTime Web como un servicio Windows y conserva sus dependencias compiladas en una
estructura de carpetas. No requiere Python ni Node.js en el equipo cliente.

## Requisitos previos

- Windows de 64 bits y una cuenta con permisos de administrador.
- Al menos 1 GB libre en la unidad `C:`.
- Puerto TCP 8000 disponible.
- PostgreSQL accesible desde el servidor. Puede estar instalado en la misma PC
  o en un servidor de base de datos de la organización.
- Credenciales PostgreSQL autorizadas para crear o usar la base definida por
  la organización.

El instalador comprueba automáticamente arquitectura, privilegios, espacio,
PowerShell y disponibilidad del puerto. También registra si PostgreSQL
responde en el host por defecto; esta última comprobación es informativa porque
la conexión puede configurarse contra otro servidor durante el wizard.

## 1. Verificar el instalador

Transportar juntos `SRTime-Web-Setup.exe` y `SHA256SUMS.txt`. En PowerShell:

```powershell
Get-FileHash .\SRTime-Web-Setup.exe -Algorithm SHA256
```

Comparar el resultado con la línea correspondiente de `SHA256SUMS.txt` antes
de ejecutar el instalador.

## 2. Ejecutar la instalación

1. Hacer clic derecho en `SRTime-Web-Setup.exe` y seleccionar **Ejecutar como
   administrador**.
2. Aceptar la ubicación propuesta:

   ```text
   C:\Service Reloj\SRTime_web
   ```

3. Seleccionar los drivers de ingesta iniciales: **Sundial / TM-MR001**,
   **ZKTeco** o **Sundial + ZKTeco**. Ambos drivers se instalan; esta opción
   define `SRTIME_ENABLED_ADDONS` en `config\.env`. En una actualización, la
   selección reemplaza ese único valor y conserva las credenciales existentes.
4. Esperar a que finalice la verificación del host, la copia del paquete, el
   registro y el inicio del servicio Windows `SRTimeWeb`.
5. El instalador crea un acceso directo de escritorio que abre
   `http://127.0.0.1:8000`.
6. Al finalizar, el instalador no abre el navegador. Reiniciar Windows antes
   del primer setup para probar el arranque real del servicio.

La instalación crea `config\.env` localmente. Propone PostgreSQL en
`127.0.0.1:5432`, base `srtime_db`, y deja vacíos `DB_USER` y `DB_PASS`.
SQLite permanece comentado como alternativa excepcional. Las claves internas
son generadas de forma única en cada PC; ninguna contraseña o base de datos se
incluye en el instalador.

## 3. Primera configuración de SRTime

1. Después del reinicio, abrir el acceso directo **SRTime Web** o navegar a
   `http://127.0.0.1:8000`.
2. En el wizard, ingresar host, puerto, usuario, contraseña y nombre de base
   PostgreSQL que correspondan a la instalación.
3. Crear o seleccionar la base de datos. El nombre propuesto es `srtime_db`,
   pero el operador puede elegir otro nombre autorizado.
4. Crear la cuenta inicial `admin` y definir su contraseña.
5. Iniciar sesión y verificar el estado desde **Control Center**.

No editar ni compartir `config\.env`: contiene las credenciales PostgreSQL
una vez completado el wizard.

## 4. Acceso desde la LAN

El instalador configura una regla de Windows Firewall para TCP 8000, limitada
a la subred IPv4 activa detectada durante la instalación. Para obtener la URL
de red del servidor:

```powershell
ipconfig
```

Desde otra PC de la misma subred, abrir:

```text
http://<IP_DEL_SERVIDOR>:8000
```

Si la red, IP o subred del servidor cambia, actualizar la regla según
`docs/ACCESO_LAN_WINDOWS.md` y reiniciar el servicio si fuera necesario.

## 5. Operación del servicio

Abrir PowerShell como administrador:

```powershell
Get-Service SRTimeWeb
Restart-Service SRTimeWeb
Stop-Service SRTimeWeb
Start-Service SRTimeWeb
```

Los logs se encuentran en `C:\Service Reloj\SRTime_web\logs`. La revisión previa
del instalador queda registrada como `installer-preflight.log`.

## 6. Actualización o desinstalación

Para actualizar, ejecutar el nuevo instalador como administrador sobre la
instalación existente. El instalador conserva `config\.env`, logs y backups.
Si ya existe una instalación con el mismo `AppId`, el asistente entra en modo
mantenimiento y ofrece reparar, reinstalar/actualizar o desinstalar. Durante
una reparación o reinstalación detiene y vuelve a registrar `SRTimeWeb`.

Antes de desinstalar o actualizar una instalación con datos, crear y comprobar
un backup PostgreSQL. La desinstalación quita el servicio y los binarios, pero
no elimina automáticamente configuración ni evidencia operativa local.

En una actualización, SRTime primero crea un dump verificable sin interrumpir el
servicio actual. Luego lo detiene, comprueba que el esquema sea compatible y
aplica la migración antes de iniciar la versión nueva. Si detecta una base
parcial, una revisión desconocida o una estructura que declara estar actualizada
pero no lo está, detiene la actualización de la base; no la rellena ni la marca
como nueva. El motivo queda en `logs\database-update.log`. Resolver el caso con
el backup y el plan de migración controlada antes de reintentar.
