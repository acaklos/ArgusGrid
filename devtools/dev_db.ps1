# Development database helper (portable PostgreSQL, local only).
# Usage: powershell -File devtools\dev_db.ps1 -Action init|start|stop|status
# Development only: not part of any deploy package.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('init', 'start', 'stop', 'status')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Tools = Join-Path $Root '.devtools'
$Bin = Join-Path $Tools 'pgsql\bin'
$DataDir = Join-Path $Tools 'pgdata'
$LogFile = Join-Path $Tools 'pg.log'
$SuperPwFile = Join-Path $Tools 'pg.superuser.pw'
$UrlFile = Join-Path $Root 'backend\data\database.url'
$Port = 54329
$DbName = 'argusgrid'
$AppRole = 'argusgrid_app'

function New-RandomSecret([int]$Length = 32) {
    $chars = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

function Test-Running {
    & (Join-Path $Bin 'pg_ctl.exe') -D $DataDir status *> $null
    return ($LASTEXITCODE -eq 0)
}

function Start-Db {
    if (Test-Running) { Write-Host 'PostgreSQL already running.'; return }
    # Redirect pg_ctl output to files so the server does not keep the caller's pipes open.
    $opts = "-p $Port -c listen_addresses=127.0.0.1"
    $argList = @('-D', "`"$DataDir`"", '-l', "`"$LogFile`"", '-o', "`"$opts`"", '-w', 'start')
    $p = Start-Process -FilePath (Join-Path $Bin 'pg_ctl.exe') -ArgumentList $argList -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput (Join-Path $Tools 'pg_ctl.out') -RedirectStandardError (Join-Path $Tools 'pg_ctl.err')
    if ($p.ExitCode -ne 0) { throw 'pg_ctl start failed' }
}

switch ($Action) {
    'init' {
        if (-not (Test-Path (Join-Path $Bin 'initdb.exe'))) { throw "PostgreSQL binaries not found in $Bin" }
        if (Test-Path (Join-Path $DataDir 'PG_VERSION')) { Write-Host 'Cluster already initialised.'; break }
        $superPw = New-RandomSecret
        [System.IO.File]::WriteAllText($SuperPwFile, $superPw)
        & (Join-Path $Bin 'initdb.exe') -D $DataDir -U argus_super --auth=scram-sha-256 --pwfile=$SuperPwFile -E UTF8 --locale=C
        if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
        Start-Db
        $appPw = New-RandomSecret
        $env:PGPASSWORD = $superPw
        $psql = Join-Path $Bin 'psql.exe'
        & $psql -h 127.0.0.1 -p $Port -U argus_super -d postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE $AppRole LOGIN PASSWORD '$appPw'"
        & $psql -h 127.0.0.1 -p $Port -U argus_super -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DbName OWNER $AppRole"
        & $psql -h 127.0.0.1 -p $Port -U argus_super -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DbName}_test OWNER $AppRole"
        Remove-Item Env:\PGPASSWORD
        New-Item -ItemType Directory -Force (Split-Path -Parent $UrlFile) | Out-Null
        $url = "postgresql+psycopg://${AppRole}:${appPw}@127.0.0.1:${Port}/${DbName}"
        [System.IO.File]::WriteAllText($UrlFile, $url)
        Write-Host "Database URL saved to $UrlFile (ignored by Git)."
    }
    'start' { Start-Db }
    'stop' {
        if (Test-Running) { & (Join-Path $Bin 'pg_ctl.exe') -D $DataDir -m fast -w stop } else { Write-Host 'Not running.' }
    }
    'status' {
        if (Test-Running) { Write-Host "running on 127.0.0.1:$Port" } else { Write-Host 'stopped' }
    }
}
