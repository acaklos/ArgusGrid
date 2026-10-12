<#
.SYNOPSIS
  ArgusGrid setup (DEP-030 to DEP-035). Checks prerequisites, installs the runtime into .venv, prepares the
  database and creates the initial administrator with a random password.

.PARAMETER CheckOnly   Report only, change nothing.
.PARAMETER DryRun      Show what would be done, change nothing.
.PARAMETER AssumeYes   Unattended: no questions (the database URL must then be given).
.PARAMETER WithDemo    Load the fictional demonstration site (only offered by the demo package).
.PARAMETER DatabaseUrl PostgreSQL 16 URL of an existing, empty database, for example
                       postgresql+psycopg://argusgrid:<password>@localhost:5432/argusgrid

  After a fully successful setup this script and setup.bat delete themselves. Download the package again to run
  the setup once more. Nothing is deleted after a failed or partial run, -CheckOnly or -DryRun.
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$DryRun,
    [switch]$AssumeYes,
    [switch]$WithDemo,
    [string]$DatabaseUrl = ''
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$Venv = Join-Path $Root '.venv'
$VenvPy = Join-Path $Venv 'Scripts\python.exe'
$DataDir = Join-Path $Backend 'data'
$ConfigDir = Join-Path $Backend 'config'
$Marker = Join-Path $Root '.setup-done'
$blockers = New-Object System.Collections.Generic.List[string]

function Say([string]$text) { Write-Host $text }
function Step([string]$text) { Write-Host ('  - ' + $text) }

# -- prerequisites ------------------------------------------------------------------------------------
Say 'ArgusGrid setup'
Say ''
$python = $null
foreach ($candidate in @(@('py', '-3.12'), @('python'), @('python3'))) {
    try {
        $exe = $candidate[0]
        $extra = @($candidate | Select-Object -Skip 1)
        # one number, no quotes inside the code (Windows PowerShell 5.1 mangles embedded quotes): 312 = 3.12
        $code = & $exe @extra -c 'import sys; print(sys.version_info[0] * 100 + sys.version_info[1])' 2>$null
        if ($LASTEXITCODE -eq 0 -and "$code" -match '^\d+$' -and [int]"$code" -ge 312) {
            $python = @{ Exe = $exe; Args = $extra; Version = ('{0}.{1}' -f [math]::Floor([int]"$code" / 100), ([int]"$code" % 100)) }
            break
        }
    } catch { }
}
if ($python) { Step ('Python ' + $python.Version + ' found') } else { Step 'Python 3.12 or newer: MISSING'; $blockers.Add('Install Python 3.12 or newer from python.org and run setup again.') }

if (-not $DatabaseUrl) { $DatabaseUrl = $env:ARGUS_DATABASE_URL }
$urlFile = Join-Path $DataDir 'database.url'
if (-not $DatabaseUrl -and (Test-Path $urlFile)) { $DatabaseUrl = (Get-Content $urlFile -Raw).Trim() }
if (-not $DatabaseUrl -and -not $CheckOnly -and -not $DryRun -and -not $AssumeYes) {
    Say ''
    Say 'PostgreSQL 16 is required. Create an empty database and a role for it first, then enter the URL.'
    Say 'Example: postgresql+psycopg://argusgrid:<password>@localhost:5432/argusgrid'
    $DatabaseUrl = (Read-Host 'Database URL').Trim()
}
if ($DatabaseUrl -match '^postgresql(\+psycopg)?://') { Step 'Database URL given' }
else { Step 'Database URL: MISSING or not a PostgreSQL URL'; $blockers.Add('Provide -DatabaseUrl (PostgreSQL 16, existing empty database).') }
if ($DatabaseUrl -match '^postgresql://') { $DatabaseUrl = $DatabaseUrl -replace '^postgresql://', 'postgresql+psycopg://' }

if ($WithDemo -and -not (Test-Path (Join-Path $Backend 'app\tools\demo_data.py'))) { $blockers.Add('-WithDemo: this package has no demonstration data (production package).') }
if (-not (Test-Path (Join-Path $Backend 'app\main.py'))) { $blockers.Add('backend\app is missing: the package is incomplete.') }
if (-not (Test-Path (Join-Path $Root 'frontend\dist\index.html'))) { $blockers.Add('frontend\dist is missing: the package is incomplete.') }

Say ''
if ($blockers.Count -gt 0) {
    Say 'Blocking problems:'
    $blockers | ForEach-Object { Say ('  * ' + $_) }
    if ($CheckOnly -or $DryRun) { exit 1 }
    exit 1
}
if ($CheckOnly) { Say 'Check finished: all prerequisites are present.'; exit 0 }

# -- plan ---------------------------------------------------------------------------------------------
$pyDisplay = ($python.Exe + ' ' + ($python.Args -join ' ')).Trim()
$plan = @(
    "$pyDisplay -m venv `"$Venv`"",
    "`"$VenvPy`" -m pip install --disable-pip-version-check -r backend\requirements.txt",
    'write backend\data\database.url (database URL, not shown again)',
    'write backend\config\app.env if missing (production defaults)',
    "`"$VenvPy`" -m app.tools.prepare_database   (schema, roles, initial administrator)"
)
if ($WithDemo) { $plan += "`"$VenvPy`" -m app.tools.demo_data create   (fictional demonstration site)" }
Say 'Plan:'
$plan | ForEach-Object { Step $_ }
if ($DryRun) { Say ''; Say 'Dry run: nothing was changed.'; exit 0 }
if (-not $AssumeYes) {
    $answer = Read-Host 'Continue? (y/N)'
    if ($answer -notmatch '^(y|yes|a|ano)$') { Say 'Cancelled. Nothing was changed.'; exit 1 }
}

# -- run ----------------------------------------------------------------------------------------------
try {
    if (-not (Test-Path $VenvPy)) {
        & $python.Exe @($python.Args) -m venv $Venv
        if ($LASTEXITCODE -ne 0) { throw 'creating the virtual environment failed' }
    }
    & $VenvPy -m pip install --disable-pip-version-check -r (Join-Path $Backend 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'installing the requirements failed' }

    New-Item -ItemType Directory -Force $DataDir, $ConfigDir | Out-Null
    if (-not (Test-Path $urlFile)) {
        [System.IO.File]::WriteAllText($urlFile, $DatabaseUrl)
        # only the current user may read the file with the database password
        & icacls $urlFile /inheritance:r /grant:r ($env:USERNAME + ':(R,W)') | Out-Null
    }
    $envFile = Join-Path $ConfigDir 'app.env'
    if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $Root 'backend\config\app.env.template') $envFile }

    $env:PYTHONDONTWRITEBYTECODE = '1'
    Push-Location $Backend
    try {
        & $VenvPy -m app.tools.prepare_database
        if ($LASTEXITCODE -ne 0) { throw 'preparing the database failed' }
        if ($WithDemo) {
            & $VenvPy -m app.tools.demo_data create
            if ($LASTEXITCODE -ne 0) { throw 'loading the demonstration data failed' }
        }
    } finally { Pop-Location }
} catch {
    Say ''
    Say ('Setup FAILED: ' + $_.Exception.Message)
    Say 'Nothing was deleted. Fix the problem and run setup again; it is safe to repeat (DEP-035).'
    exit 1
}

Say ''
Say 'Setup finished.'
Say ('Start the application with start.bat. The initial administrator is in ' + (Join-Path $DataDir 'accounts.txt'))
Say 'The password must be changed at the first login. Move the file out of the folder after you have read it.'
Say 'This setup script now removes itself (to run it again, download the package again).'

# -- self removal (D-13): the marker lets setup.bat remove itself as its last step ----------------------
[System.IO.File]::WriteAllText($Marker, 'ok')
Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force
exit 0
