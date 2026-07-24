[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$attendanceDir = Join-Path $root 'attendance'
$envFile = Join-Path $attendanceDir '.env.pseudo_pro'
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$webIndex = Join-Path $attendanceDir 'web\out\index.html'

function Get-EnvSetting([string]$Key) {
    $line = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    return (($line -split '=', 2)[1]).Trim()
}

if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'Missing attendance/.env.pseudo_pro. Run deploy\install-pseudo-pro.ps1 once to prepare pseudo-production.'
}
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Missing .venv. Run deploy\install-pseudo-pro.ps1 once to install the local runtime.'
}
if (-not (Test-Path -LiteralPath $webIndex)) {
    throw 'Missing attendance/web/out. Run deploy\install-pseudo-pro.ps1 once to build the web interface.'
}

$env:SRTIME_ENV_FILE = $envFile
$apiHost = Get-EnvSetting 'API_HOST'
$apiPort = Get-EnvSetting 'API_PORT'
if ([string]::IsNullOrWhiteSpace($apiHost) -or [string]::IsNullOrWhiteSpace($apiPort)) {
    throw 'API_HOST and API_PORT must be configured in attendance/.env.pseudo_pro.'
}
$addressPattern = [regex]::Escape("$apiHost`:$apiPort")
$listenerLine = netstat -ano -p tcp |
    Where-Object { $_ -match "^\s*TCP\s+$addressPattern\s+\S+\s+LISTENING\s+\d+\s*$" } |
    Select-Object -First 1
if ($listenerLine) {
    $ownerId = [int]([regex]::Match($listenerLine, "\d+\s*$").Value)
    $owner = Get-Process -Id $ownerId -ErrorAction SilentlyContinue
    $ownerName = if ($owner) { $owner.ProcessName } else { 'unknown' }
    throw "SRTime cannot start because $apiHost`:$apiPort is already in use by PID $ownerId ($ownerName). Stop the existing manual server with Ctrl+C in its original terminal."
}
Write-Host 'SRTime pseudo-production is running at http://127.0.0.1:8000/'
Write-Host 'Press Ctrl+C to stop the server.'
try {
    & $venvPython (Join-Path $root 'deploy\run_api.py')
    if ($LASTEXITCODE -ne 0) { throw "SRTime pseudo-production server failed (exit code $LASTEXITCODE)." }
}
finally {
    Remove-Item Env:\SRTIME_ENV_FILE -ErrorAction SilentlyContinue
}
