<#
.SYNOPSIS  Stop ArgusGrid (DEP-041): only the process this package started, found by its recorded process id and
           checked by its command line. The database server is never touched.
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root 'backend\data\server.pid'
if (-not (Test-Path $PidFile)) { Write-Host 'ArgusGrid is not running (no process file).'; exit 0 }
$id = [int](Get-Content $PidFile -Raw)
$proc = Get-CimInstance Win32_Process -Filter "ProcessId = $id" -ErrorAction SilentlyContinue
if (-not $proc) {
    Remove-Item $PidFile -Force
    Write-Host 'ArgusGrid was not running; the stale process file was removed.'
    exit 0
}
# narrow filter: our server module AND our own folder in the command line
if ($proc.CommandLine -notlike '*app.main:app_factory*' -or $proc.CommandLine -notlike ('*' + $Root + '*')) {
    Write-Host "Process $id is not the ArgusGrid server of this folder. Nothing was stopped."
    exit 1
}
Stop-Process -Id $id -Force
Remove-Item $PidFile -Force
Write-Host "ArgusGrid stopped (process $id)."
