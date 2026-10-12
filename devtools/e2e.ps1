# Run the browser tests against the real backend and a real PostgreSQL database.
# Development only: not part of any package. Usage: powershell -File devtools\e2e.ps1 [-Spec e2e\identity.spec.ts]
param([string]$Spec = '')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Work = Join-Path $Root '.devtools\e2e'
$Port = 8000

# Database: the test database next to the development one (never the development data).
$devUrl = (Get-Content (Join-Path $Backend 'data\database.url') -Raw).Trim()
$testUrl = $devUrl -replace '/argusgrid$', '/argusgrid_test'
if ($testUrl -eq $devUrl) { throw 'Could not derive the test database URL.' }

if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
New-Item -ItemType Directory -Force (Join-Path $Work 'data'), (Join-Path $Work 'config') | Out-Null

$env:ARGUS_ENV = 'production'
$env:ARGUS_DATABASE_URL = $testUrl
$env:ARGUS_DATA_DIR = Join-Path $Work 'data'
$env:ARGUS_CONFIG_DIR = Join-Path $Work 'config'
$env:ARGUS_DEV_LOGINLESS = '0'
$env:ARGUS_WORKERS = '1'
$env:ARGUS_WORKER_SECONDS = '2'
$MailDir = Join-Path $Work 'mail'
$SmtpPort = 1025

# Empty the test database, then migrate and seed.
$clean = @"
import psycopg, os
url = os.environ['ARGUS_DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://')
with psycopg.connect(url, autocommit=True) as c:
    names = [r[0] for r in c.execute("select tablename from pg_tables where schemaname='public'")]
    if names:
        c.execute('DROP TABLE IF EXISTS ' + ', '.join('"%s"' % n for n in names) + ' CASCADE')
"@
$cleanFile = Join-Path $Work 'clean.py'
[System.IO.File]::WriteAllText($cleanFile, $clean)
& $Py -I $cleanFile
if ($LASTEXITCODE -ne 0) { throw 'cleaning the test database failed' }

Push-Location $Backend
& $Py -m app.tools.prepare_database | Out-Null
if ($LASTEXITCODE -ne 0) { Pop-Location; throw 'prepare_database failed' }
Pop-Location
& $Py (Join-Path $PSScriptRoot 'e2e_prepare.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'e2e_prepare failed' }
Push-Location $Backend
& $Py -m app.tools.demo_data create | Out-Null
if ($LASTEXITCODE -ne 0) { Pop-Location; throw 'demo data failed' }
Pop-Location

$ownerOut = & $Py (Join-Path $PSScriptRoot 'owner_tool.py') --config-dir (Join-Path $Work 'config') --force
$ownerId = ($ownerOut | Select-String 'identifier:\s+(\S+)').Matches[0].Groups[1].Value
$ownerSecret = ($ownerOut | Select-String 'secret:\s+(\S+)').Matches[0].Groups[1].Value

$accounts = Get-Content (Join-Path $Work 'data\accounts.txt')
$line = $accounts | Where-Object { $_ -like 'sysadmin:*' } | Select-Object -First 1
$env:E2E_ADMIN_USER = 'sysadmin'
$env:E2E_ADMIN_PASSWORD = ($line -replace '^sysadmin:\s*', '').Trim()
$env:E2E_OWNER_ID = $ownerId
$env:E2E_OWNER_SECRET = $ownerSecret
$env:E2E_BASE_URL = "http://127.0.0.1:$Port"
$env:E2E_MAIL_DIR = $MailDir
$env:E2E_SMTP_PORT = "$SmtpPort"
$env:E2E_PY = $Py
$env:E2E_BACKEND = $Backend
$env:E2E_DEMO_CREDS = Join-Path $Work 'data\demo-devices.txt'

# SMTP sink: stores messages as files so the tests can read what the application really sent.
$sink = Start-Process -FilePath $Py -PassThru -WindowStyle Hidden `
    -ArgumentList @((Join-Path $PSScriptRoot 'smtp_sink.py'), '--port', "$SmtpPort", '--out', $MailDir) `
    -RedirectStandardOutput (Join-Path $Work 'sink.out') -RedirectStandardError (Join-Path $Work 'sink.err')

# Start the server and remember only its own process id (DEP-041: narrow stop).
$server = Start-Process -FilePath $Py -WorkingDirectory $Backend -PassThru -WindowStyle Hidden `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app_factory', '--factory', '--host', '127.0.0.1', '--port', "$Port") `
    -RedirectStandardOutput (Join-Path $Work 'server.out') -RedirectStandardError (Join-Path $Work 'server.err')
try {
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $r = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 2
            if ($r.status -eq 'ok') { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'server did not become ready' }

    Push-Location $Frontend
    if ($Spec) { & npx playwright test $Spec } else { & npx playwright test }
    $code = $LASTEXITCODE
    Pop-Location
    exit $code
}
finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    if ($sink -and -not $sink.HasExited) { Stop-Process -Id $sink.Id -Force }
}
