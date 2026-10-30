# Documentacion tecnica del instalador SRTime Web para Windows

## Alcance

Este documento describe el instalador Windows del artefacto Web de la suite
SRTime `v0.9.0-beta.4`. El instalador entrega la aplicacion Web compilada con
Nuitka, el frontend Next.js exportado como archivos estaticos, los scripts
operativos y el servicio Windows `SRTimeWeb`. El tag corresponde a la suite
completa, no solamente al artefacto Web.

La version Web usa PostgreSQL como motor de base de datos. No instala ni empaqueta la version de escritorio PySide6; esa version se distribuye por separado y se compila con PyInstaller.

## Artefactos

- Instalador: `C:\Proyectos\SRTime\deploy\web\dist\Instalador SRTime Web\SRTime-Web-Setup.exe`
- Paquete fuente del instalador: `C:\Proyectos\SRTime\deploy\web\dist\SRTime-Web`
- Script Inno Setup: `C:\Proyectos\SRTime\deploy\web\installer\SRTime-Web.iss`
- Script de compilacion del instalador: `C:\Proyectos\SRTime\deploy\web\installer\build-installer.ps1`
- Wrapper de servicio: `C:\Proyectos\SRTime\deploy\web\installer\vendor\WinSW-x64.exe`

## Requisitos del host

- Windows de 64 bits.
- Permisos de administrador para instalar.
- Al menos 1 GB libre en `C:`.
- Puerto TCP `8000` libre.
- PostgreSQL instalado localmente o accesible por red.
- Credenciales PostgreSQL con permisos suficientes para crear o usar la base configurada.

El instalador bloquea la instalacion en Windows x86, si falta PowerShell, si no hay espacio minimo o si el puerto `8000` ya esta en uso en una instalacion nueva. Si detecta una instalacion existente en `C:\Service Reloj\SRTime_web`, permite continuar el modo mantenimiento para reparar, reinstalar/actualizar o desinstalar.

## Ruta de instalacion

La ruta acordada para SRTime Web es:

```text
C:\Service Reloj\SRTime_web
```

Estructura esperada:

```text
C:\Service Reloj\SRTime_web\
├── app\
│   ├── srtime-web-api.exe
│   ├── web\
│   ├── alembic\
│   └── runtime Nuitka / DLLs
├── config\
│   ├── .env
│   └── .env.example
├── logs\
├── scripts\
├── service\
├── docs\
├── README.md
└── SHA256SUMS.txt
```

## Seleccion de drivers

El instalador incluye ambos drivers, pero permite elegir cuales quedan habilitados inicialmente:

- `sundial`: relojes Sundial ERTeckno por red (modulo Tibbo) e importacion del archivo TM-MR001.
- `zkteco`: terminales ZKTeco por red e importacion del archivo `att.dat`.
- `sundial,zkteco`: habilita ambos.

La pestana Terminales aparece solo si hay al menos un driver habilitado.

La seleccion se guarda en:

```env
SRTIME_ENABLED_ADDONS=sundial,zkteco
```

El archivo generado es `C:\Service Reloj\SRTime_web\config\.env`. En una
actualización, la elección explícita del asistente actualiza únicamente
`SRTIME_ENABLED_ADDONS`; conserva credenciales, conexión PostgreSQL, secretos,
logs y backups. El nuevo perfil se aplica al reiniciar el servicio `SRTimeWeb`.

## Configuracion local

El instalador no incluye credenciales reales. Durante la instalacion ejecuta `initialize-local-config.ps1`, que crea `config\.env` desde `config\.env.example`, genera secretos internos unicos y aplica el perfil de drivers seleccionado.

Valores base:

```env
DB_ENGINE=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=srtime_db
DB_USER=
DB_PASS=
API_HOST=0.0.0.0
API_PORT=8000
SRTIME_SETUP_ALLOWED_IPS=127.0.0.1,::1,private
```

Las credenciales PostgreSQL se ingresan en el wizard inicial de la aplicacion, no quedan embebidas en el instalador.

## Servicio Windows

El instalador registra el servicio:

```text
SRTimeWeb
```

El servicio usa WinSW y ejecuta:

```text
C:\Service Reloj\SRTime_web\app\srtime-web-api.exe
```

Variables del servicio:

- `SRTIME_ENV_FILE=%BASE%\..\config\.env`
- `SRTIME_WEB_DIR=%BASE%\..\app\web`

Logs:

```text
C:\Service Reloj\SRTime_web\logs
```

Comandos de administracion:

```powershell
Get-Service SRTimeWeb
Start-Service SRTimeWeb
Stop-Service SRTimeWeb
Restart-Service SRTimeWeb
```

Durante reparacion o reinstalacion, el instalador detiene y desregistra el servicio anterior antes de registrar nuevamente `SRTimeWeb`. Luego inicia el servicio, pero no abre el navegador; muestra una recomendacion de reiniciar Windows antes del primer setup o validacion QA.

## Acceso local y LAN

El acceso directo del escritorio abre:

```text
http://127.0.0.1:8000
```

Desde otras PCs de la misma red se usa:

```text
http://IP_DEL_SERVIDOR:8000
```

El instalador ejecuta `configure-lan-firewall.ps1`, que crea o actualiza la regla `SRTime Web LAN` para permitir TCP `8000` desde la subred IPv4 activa.

## Flujo QA recomendado

1. Ejecutar `SRTime-Web-Setup.exe` como administrador.
2. Elegir driver o drivers de ingesta.
3. Confirmar instalacion en `C:\Service Reloj\SRTime_web`.
4. Confirmar que el servicio queda iniciado, que el instalador recomienda reiniciar y que no abre la aplicacion automaticamente.
5. Reiniciar Windows.
6. Confirmar que `SRTimeWeb` queda en ejecucion tras el reboot.
7. Abrir `http://127.0.0.1:8000`.
8. Completar el wizard inicial con PostgreSQL.
9. Crear el usuario administrador.
10. Validar login y visibilidad de tabs segun drivers elegidos.
11. Probar acceso LAN desde otra PC con `http://IP_DEL_SERVIDOR:8000`.

## Base de testing evolutiva

Para desarrollo, QA destructivo controlado y cambios solicitados por cliente, la base PostgreSQL local de referencia es:

```text
srtime_db_test
```

Esta base conserva el esquema SRTime actualizado y es la unica base local que debe modificarse en futuras pruebas evolutivas. Las bases temporales antiguas de SRTime deben eliminarse para evitar confusiones entre entornos.

## Actualizacion, preflight de esquema y desinstalacion

El instalador conserva `config\.env`, `logs` y `backups`. Una actualizacion no debe sobrescribir credenciales locales ni evidencia operativa. Si se ejecuta nuevamente sobre una instalacion existente, Inno Setup muestra el flujo de mantenimiento con opciones de reparar, reinstalar/actualizar o desinstalar.

La desinstalacion detiene y elimina el servicio `SRTimeWeb`. Los datos PostgreSQL no se eliminan automaticamente.

En modo **Actualizar**, el instalador sigue dos fases. Primero genera y verifica
un dump PostgreSQL con SHA-256 mientras el servicio anterior continúa operativo.
Después detiene el servicio, ejecuta el preflight de solo lectura y aplica
Alembic; solamente si ambas comprobaciones resultan satisfactorias registra e
inicia el servicio con los binarios nuevos. El preflight acepta únicamente una
base vacía, una base SRTime completa creada por el wizard pero aún sin metadata
Alembic, o una revisión Alembic reconocida por el paquete. Bloquea una base
parcial sin versionar, una revisión desconocida y una base que declara estar en
`head` pero no contiene las tablas o columnas actuales. El diagnóstico no expone
credenciales: queda en `logs\database-update.log` y el popup indica el estado
funcional. En caso de fallo se conserva el dump verificado y se debe restaurar o
preparar una migración controlada según [el contrato de migración](PLAN_CONTRATO_MIGRACION_CLIENTES.md).

## Seguridad y gitignore

La carpeta `deploy` permanece fuera del repositorio fuente. No se versionan binarios, instaladores, `.env` reales, logs, backups ni credenciales. El repositorio conserva solamente ejemplos seguros como `config/.env.example` o plantillas equivalentes.
