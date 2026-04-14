@echo off
setlocal
title SRTime Web - Windows Setup (NSSM Services)

echo ========================================================
echo   SRTime Web -- Instalacion de Servicios en Windows
echo ========================================================
echo.

:: Verificar permisos de Administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Este script debe ejecutarse como Administrador.
    echo Haz clic derecho en el archivo y selecciona "Ejecutar como administrador".
    pause
    exit /b 1
)

:: Verificar si NSSM esta instalado en el PATH
where nssm >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] NSSM no se encuentra en el PATH.
    echo Por favor descarga NSSM (http://nssm.cc) y agregalo a las Variables de Entorno de Windows.
    pause
    exit /b 1
)

set "APP_DIR=%~dp0"
set "API_EXE=%APP_DIR%api\run_api.exe"
set "WEB_JS=%APP_DIR%web\server.js"

:: Obtener ruta de NodeJS
for /f "delims=" %%I in ('where node') do set "NODE_EXE=%%I"

if not exist "%API_EXE%" (
    echo [ERROR] No se encontro el binario de la API en: %API_EXE%
    pause
    exit /b 1
)

if not exist "%WEB_JS%" (
    echo [ERROR] No se encontro el frontend NextJS en: %WEB_JS%
    pause
    exit /b 1
)

echo [1/3] Configurando variables de entorno (.env)...
if not exist "%APP_DIR%config\.env" (
    copy "%APP_DIR%config\.env.example" "%APP_DIR%config\.env" > NUL
    echo   [!] Se ha creado el archivo .env a partir de .env.example
    echo       Recuerda editar %APP_DIR%config\.env con las credenciales correctas.
)

echo [2/3] Instalando SRTimeAPI Service...
nssm install SRTimeAPI "%API_EXE%"
nssm set SRTimeAPI AppDirectory "%APP_DIR%api"
nssm set SRTimeAPI Description "SRTime FastAPI Backend Service"
nssm start SRTimeAPI

echo [3/3] Instalando SRTimeWeb Service...
nssm install SRTimeWeb "%NODE_EXE%" "%WEB_JS%"
nssm set SRTimeWeb AppDirectory "%APP_DIR%web"
nssm set SRTimeWeb Description "SRTime Next.js Web Frontend"
nssm start SRTimeWeb

echo.
echo ========================================================
echo   ✅ Setup Completado
echo ========================================================
echo Los servicios de Windows "SRTimeAPI" y "SRTimeWeb" han sido instalados e iniciados.
echo Puedes manejarlos usando el comando: services.msc
pause
