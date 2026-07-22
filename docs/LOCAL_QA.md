# SRTime: arranque local de QA

El entorno de QA usa PostgreSQL y **no** toca `attendance/.env` ni la base de
trabajo. La configuración local está en `attendance/.env.qa`, que Git ignora.
La plantilla versionada es `attendance/.env.qa.example`.

## Credenciales y responsabilidad

SRTime no crea ni conoce una contraseña administrativa de PostgreSQL antes del
primer inicio. Esa cuenta pertenece a la instalación de PostgreSQL, no al
proyecto. En esta máquina el servidor esperado es `localhost:5432`; el nombre
habitual de la cuenta administrativa es `postgres`, pero su contraseña debe
conocerse o restablecerse desde PostgreSQL/pgAdmin.

| Cuenta | Uso | Dónde queda la contraseña |
|---|---|---|
| Administrador PostgreSQL (por ejemplo `postgres`) | Conexión inicial y creación de la base | Instalación de PostgreSQL; SRTime no la documenta ni la genera. |
| Usuario PostgreSQL configurado (por defecto, `postgres`) | Conexión cotidiana de SRTime a su base QA | `attendance/.env.qa`, archivo local ignorado por Git. |
| `admin` de SRTime | Inicio de sesión en la aplicación | Hash en la tabla `auth_user`; no se guarda como texto plano. |

Nunca se agregan contraseñas reales a `.env.qa.example`, documentación ni Git.

## Primer inicio

1. Verificar que PostgreSQL y Node.js LTS estén instalados.
2. Hacer doble clic en `Iniciar-SRTime-QA.cmd`. Este paso crea `.venv`, instala
   dependencias Python y Node, genera el frontend estático y luego inicia SRTime.
   Se realiza una vez por instalación o cuando se decide reconstruir dependencias.

   También puede ejecutarse la preparación sola:

   ```powershell
   .\deploy\start-local-qa.ps1
   ```

3. Abrir `http://127.0.0.1:8000/`. El primer paso usa los valores por defecto
   `localhost`, `5432`, usuario `postgres` y base `srtime_qa`. Ingresar la
   contraseña existente de PostgreSQL y presionar **Crear base de datos**.
4. Una vez creada la conexión, se habilita la contraseña del primer usuario
   `admin` de SRTime. La conexión PostgreSQL indicada queda guardada sólo en
   `.env.qa`.

Al finalizar, el asistente redirige al inicio de sesión; ingresar con la cuenta
`admin` recién creada.

## Reinicios posteriores

Para iniciar SRTime sin instalar paquetes, crear el entorno virtual ni compilar
la web, ejecutar:

```powershell
.\deploy\start-local-qa-server.ps1
```

## Reconstruir la interfaz

Después de modificar código del frontend, iniciar con:

```powershell
.\deploy\start-local-qa.ps1 -RebuildWeb
```

La base `srtime_qa` conserva sus datos entre arranques. No usar este iniciador
contra una base productiva ni cambiar `DB_NAME` a una base de trabajo.
