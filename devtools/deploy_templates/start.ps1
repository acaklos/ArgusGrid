<#
.SYNOPSIS  Start ArgusGrid (DEP-040): prepare the database, start the server, wait for it, open the browser.
#>
[CmdletBinding()]
param([switch]$NoBrowser, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$DataDir = Join-Path $Backend 'data'
$PidFile = Join-Path $DataDir 'server.pid'
if (-not (Test-Path $Py)) { throw 'The application is not set up. Run setup.bat first.' }

# configuration: backend\config\app.env (KEY=VALUE), already set environment variables win
$envFile = Join-Path $Backend 'config\app.env'
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$' -and -not (Test-Path ('Env:' + $Matches[1]))) {
            Set-Item -Path ('Env:' + $Matches[1]) -Value $Matches[2]
        }
    }
}
$env:PYTHONDONTWRITEBYTECODE = '1'
$bind = if ($env:ARGUS_BIND_HOST) { $env:ARGUS_BIND_HOST } else { '127.0.0.1' }

if (Test-Path $PidFile) {
    $existing = [int](Get-Content $PidFile -Raw)
    if (Get-Process -Id $existing -ErrorAction SilentlyContinue) { throw "ArgusGrid already runs (process $existing). Use stop.bat first." }
    Remove-Item $PidFile -Force
}

Push-Location $Backend
try {
    & $Py -m app.tools.prepare_database
    if ($LASTEXITCODE -ne 0) { throw 'preparing the database failed' }
} finally { Pop-Location }

$logDir = Join-Path $DataDir 'logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$server = Start-Process -FilePath $Py -WorkingDirectory $Backend -WindowStyle Hidden -PassThru `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app_factory', '--factory', '--host', $bind, '--port', $Port) `
    -RedirectStandardOutput (Join-Path $logDir 'server.out.log') -RedirectStandardError (Join-Path $logDir 'server.err.log')
[System.IO.File]::WriteAllText($PidFile, [string]$server.Id)

$url = "http://${bind}:$Port"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    if ($server.HasExited) { break }
    try {
        $r = Invoke-RestMethod "$url/api/v1/health" -TimeoutSec 2
        if ($r.status -eq 'ok') { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) {
    Write-Host 'The server did not become ready. See backend\data\logs\server.err.log'
    exit 1
}
Write-Host "ArgusGrid is running: $url   (process $($server.Id))"
if (-not $NoBrowser) { Start-Process $url }
