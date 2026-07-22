[CmdletBinding()]
param([switch]$RebuildWeb)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$attendanceDir = Join-Path $root 'attendance'
$envFile = Join-Path $attendanceDir '.env.qa'
$exampleEnv = Join-Path $attendanceDir '.env.qa.example'
$webDir = Join-Path $attendanceDir 'web'
$venvDir = Join-Path $root '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'

function Set-EnvSetting([string]$Path, [string]$Key, [string]$Value) {
    $escapedKey = [regex]::Escape($Key)
    $updated = (Get-Content -LiteralPath $Path) | ForEach-Object {
        if ($_ -match "^\s*$escapedKey\s*=") { "$Key=$Value" } else { $_ }
    }
    Set-Content -LiteralPath $Path -Value $updated -Encoding utf8
}

function Assert-LastExit([string]$Description) {
    if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit code $LASTEXITCODE)." }
}

if (-not (Test-Path -LiteralPath $envFile)) { Copy-Item -LiteralPath $exampleEnv -Destination $envFile }

# The internal JWT secret is generated locally. PostgreSQL and admin credentials
# are entered in the web installer on the first visit.
$secretLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^SECRET_KEY=' } | Select-Object -First 1
if (-not $secretLine -or $secretLine -match '=__') {
    $bytes = [byte[]]::new(32)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    Set-EnvSetting $envFile 'SECRET_KEY' (([BitConverter]::ToString($bytes) -replace '-', '').ToLowerInvariant())
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pythonLauncher) { & $pythonLauncher.Source -3 -m venv $venvDir }
    else { & (Get-Command python.exe -ErrorAction Stop).Source -m venv $venvDir }
    Assert-LastExit 'Python virtual environment creation'
}

if (-not (Test-Path -LiteralPath (Join-Path $venvDir 'Scripts\alembic.exe'))) {
    Write-Host 'Installing Python dependencies for the web/API...'
    & $venvPython -m pip install -r (Join-Path $attendanceDir 'requirements-web.txt') pytest pytest-cov
    Assert-LastExit 'Python dependency installation'
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { $npm = Get-Command npm -ErrorAction Stop }
if (-not (Test-Path -LiteralPath (Join-Path $webDir 'node_modules'))) {
    Push-Location $webDir
    try { & $npm.Source ci; Assert-LastExit 'Frontend dependency installation' }
    finally { Pop-Location }
}
if ($RebuildWeb -or -not (Test-Path -LiteralPath (Join-Path $webDir 'out\index.html'))) {
    Push-Location $webDir
    try {
        # QA runs frontend and API under the same FastAPI origin; do not bake a
        # localhost URL into the static bundle because 127.0.0.1 is also valid.
        $env:NEXT_PUBLIC_API_URL = ''
        & $npm.Source run build
        Assert-LastExit 'Static web build'
    }
    finally { Pop-Location }
}

Remove-Item Env:\NEXT_PUBLIC_API_URL -ErrorAction SilentlyContinue
Write-Host 'SRTime QA preparation completed.'
Write-Host 'Use deploy\start-local-qa-server.ps1 to start the server without reinstalling packages.'
