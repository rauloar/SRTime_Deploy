# Instalación de SRTime_Web en Windows

Esta guía corresponde al instalador `SRTime_Web-Setup.exe`, que entrega
SRTime_Web como un servicio Windows con sus dependencias compiladas. No
requiere Python ni Node.js en el equipo cliente. Incluye PostgreSQL 18.6 para
los equipos que todavía no lo tienen.

## Requisitos previos

- Windows de 64 bits y una cuenta con permisos de administrador.
- Al menos 2 GB libres en la unidad `C:`.
- Puertos TCP 8000 (SRTime_Web) y 5432 (PostgreSQL) disponibles.

PostgreSQL es obligatorio. El instalador lo detecta y, si no está, lo instala;
no hace falta instalarlo a mano. Si ya existe, debe ser versión 14 o superior
e incluir las herramientas de línea de comandos (`pg_dump`).

## 1. Verificar el instalador

Transportar juntos `SRTime_Web-Setup.exe` y `SHA256SUMS.txt`. En PowerShell:

```powershell
Get-FileHash .\SRTime_Web-Setup.exe -Algorithm SHA256
```

Comparar el resultado con la línea de `SHA256SUMS.txt` antes de ejecutarlo.

## 2. Ejecutar la instalación

1. Clic derecho en `SRTime_Web-Setup.exe` → **Ejecutar como administrador**.
2. Página **PostgreSQL**:
   - Si ya está instalado, se muestran versión, carpeta, servicio y puerto, y
     SRTime_Web lo reutiliza. Si el servicio está detenido, se ofrece iniciarlo.
   - Si no está instalado, definir la contraseña del usuario `postgres`
     (mínimo 8 caracteres, sin espacios, comillas, `#` ni `=`) y **guardarla**:
     la configuración inicial la va a pedir.
3. Aceptar la ubicación `C:\Service Reloj\SRTime_Web`.
4. Elegir los drivers de ingesta: **Sundial / TM-MR001**, **ZKTeco** o ambos.
5. Esperar. Si faltaba PostgreSQL, primero se instala PostgreSQL 18.6 (puede
   tardar varios minutos y muestra su propia barra de progreso). Luego se
   copian los archivos, se crea `config\.env`, se protegen los permisos, se
   configura el firewall y se inicia el servicio `SRTimeWeb`.
6. El instalador espera a que SRTime_Web responda y avisa cuando está listo.
   No hace falta reiniciar Windows.

`config\.env` se crea con claves internas únicas de cada PC, el puerto de
PostgreSQL y la ruta de `pg_dump.exe`. Sólo administradores y SYSTEM pueden
leerlo.

## 3. Primera configuración de SRTime_Web

1. Abrir el acceso directo **SRTime_Web** o navegar a `http://127.0.0.1:8000`.
2. Paso 1 — Base de datos: el formulario viene precargado desde `config\.env`
   con el servidor, el puerto detectado por el instalador, el usuario `postgres`
   y el nombre de base propuesto (`srtime_db`). Completar la contraseña de
   PostgreSQL y revisar el nombre: si ya existe una base con ese nombre,
   SRTime_Web se conecta a ella. SRTime_Web crea la base y su esquema.
3. Paso 2 — Administrador: definir la contraseña del usuario `admin`. La sesión
   se inicia automáticamente.
4. Verificar el estado desde **Control Center**.

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

Los logs se encuentran en `C:\Service Reloj\SRTime_Web\logs`. La revisión previa
del instalador queda registrada como `installer-preflight.log`.

## 6. Actualización o desinstalación

Para actualizar, ejecutar el nuevo instalador como administrador sobre la
instalación existente. El instalador conserva `config\.env`, logs y backups.
Si ya existe una instalación con el mismo `AppId`, el asistente entra en modo
mantenimiento y ofrece reparar, reinstalar/actualizar o desinstalar. Durante
una reparación o reinstalación detiene y vuelve a registrar `SRTimeWeb`.

Antes de desinstalar o actualizar una instalación con datos, crear y comprobar
un backup PostgreSQL. La desinstalación quita el servicio y los binarios, pero
no desinstala PostgreSQL ni borra sus bases, `config\.env`, logs ni backups.

En una actualización, SRTime primero crea un dump verificable sin interrumpir el
servicio actual. Luego lo detiene, comprueba que el esquema sea compatible y
aplica la migración antes de iniciar la versión nueva. Si detecta una base
parcial, una revisión desconocida o una estructura que declara estar actualizada
pero no lo está, detiene la actualización de la base; no la rellena ni la marca
como nueva. El motivo queda en `logs\database-update.log`. Resolver el caso con
el backup y el plan de migración controlada antes de reintentar.
