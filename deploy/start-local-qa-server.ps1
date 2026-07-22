[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$attendanceDir = Join-Path $root 'attendance'
$envFile = Join-Path $attendanceDir '.env.qa'
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$webIndex = Join-Path $attendanceDir 'web\out\index.html'

if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'Missing attendance/.env.qa. Run Iniciar-SRTime-QA.cmd once to prepare SRTime QA.'
}
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Missing .venv. Run Iniciar-SRTime-QA.cmd once to install the local runtime.'
}
if (-not (Test-Path -LiteralPath $webIndex)) {
    throw 'Missing attendance/web/out. Run Iniciar-SRTime-QA.cmd once to build the web interface.'
}

$env:SRTIME_ENV_FILE = $envFile
Write-Host 'SRTime QA is running at http://127.0.0.1:8000/'
Write-Host 'Press Ctrl+C to stop the server.'
try {
    & $venvPython (Join-Path $root 'deploy\run_api.py')
    if ($LASTEXITCODE -ne 0) { throw "SRTime QA server failed (exit code $LASTEXITCODE)." }
}
finally {
    Remove-Item Env:\SRTIME_ENV_FILE -ErrorAction SilentlyContinue
}
