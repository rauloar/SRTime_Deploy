@echo off
setlocal enabledelayedexpansion
title SRTime Web - Windows Build (Nuitka + Next.js)

:: Directorios
set "PROJ_DIR=%~dp0..\.."
set "DIST_DIR=%PROJ_DIR%\deploy\dist\windows"
set "BUILD_DIR=%PROJ_DIR%\deploy\build\windows"

echo ==========================================
echo   🚀 INICIANDO BUILD WEB PROD PARA WINDOWS
echo ==========================================

:: 1. Compilar Backend con Nuitka
echo.
echo -^> [1/4] Compilando Backend API con Nuitka...
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
cd /d "%PROJ_DIR%"

python -m nuitka ^
    --standalone ^
    --output-dir="%BUILD_DIR%" ^
    --include-package=api ^
    --include-package=core ^
    --include-package=models ^
    --include-package=services ^
    --include-package=uvicorn ^
    --include-package=fastapi ^
    --include-package=sqlalchemy ^
    --include-package=passlib ^
    --include-package=jose ^
    --include-package=dotenv ^
    --include-package=alembic ^
    --include-package=bcrypt ^
    "%PROJ_DIR%\deploy\run_api.py"

:: 2. Build Frontend Next.js Standalone
echo.
echo -^> [2/4] Construyendo Frontend Next.js...
cd /d "%PROJ_DIR%\attendance\web"
call npm run build

:: 3. Empaquetar
echo.
echo -^> [3/4] Empaquetando para Produccion Web Windows...
if not exist "%DIST_DIR%\srtime\api" mkdir "%DIST_DIR%\srtime\api"
if not exist "%DIST_DIR%\srtime\web\.next\static" mkdir "%DIST_DIR%\srtime\web\.next\static"
if not exist "%DIST_DIR%\srtime\config" mkdir "%DIST_DIR%\srtime\config"

:: Copiar Binario del API
xcopy /Y /E /I "%BUILD_DIR%\run_api.dist\*" "%DIST_DIR%\srtime\api\" > NUL

:: Copiar Standalone Frontend Web
cd /d "%PROJ_DIR%\attendance\web"
xcopy /Y /E /I ".next\standalone\*" "%DIST_DIR%\srtime\web\" > NUL
xcopy /Y /E /I ".next\static\*" "%DIST_DIR%\srtime\web\.next\static\" > NUL
xcopy /Y /E /I "public\*" "%DIST_DIR%\srtime\web\public\" > NUL

:: Copiar configs
copy /Y "%PROJ_DIR%\deploy\.env.production.example" "%DIST_DIR%\srtime\config\.env.example" > NUL
copy /Y "%PROJ_DIR%\attendance\migrate_sqlite.py" "%DIST_DIR%\srtime\" > NUL

:: 4. Scripts de Inicio de Windows (Para Web)
echo @echo off > "%DIST_DIR%\srtime\start_web.bat"
echo pushd "%%~dp0api" >> "%DIST_DIR%\srtime\start_web.bat"
echo start cmd /k "run_api.exe" >> "%DIST_DIR%\srtime\start_web.bat"
echo popd >> "%DIST_DIR%\srtime\start_web.bat"
echo pushd "%%~dp0web" >> "%DIST_DIR%\srtime\start_web.bat"
echo start cmd /k "node server.js" >> "%DIST_DIR%\srtime\start_web.bat"
echo popd >> "%DIST_DIR%\srtime\start_web.bat"

echo.
echo ✅ BUILD COMPLETADO:
echo El paquete Windows Web Prod esta dentro de:
echo 📁 %DIST_DIR%\srtime
echo.
echo Nota: Para instalarlo usa NSSM si quieres convertirlos a servicios.
pause
