# Create or repair .venv (stops escout/serve using the venv first).
param(
    [switch]$Force,
    [switch]$Ui
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib\repo.ps1')
$Root = Get-RepoRoot
Set-Location $Root

$venvPy = Join-Path $Root '.venv\Scripts\python.exe'
if ((Test-Path $venvPy) -and -not $Force) {
    $ver = & $venvPy --version 2>&1
    Write-Host "OK: .venv already exists ($ver)" -ForegroundColor Green
    Write-Host "Use: .\serve-ui.ps1" -ForegroundColor Cyan
    Write-Host "To recreate: .\scripts\setup-venv.ps1 -Force" -ForegroundColor DarkGray
    exit 0
}

# Stop processes that lock .venv\Scripts\python.exe or escout.exe
$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.ExecutablePath -and (
            $_.ExecutablePath -like "$Root\.venv\Scripts\*" -or
            $_.CommandLine -like "*enterprise-scout-mcp*serve*"
        )
    }
foreach ($p in $procs) {
    Write-Host ">> Stopping PID $($p.ProcessId) $($p.Name)" -ForegroundColor Yellow
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

if (Test-Path (Join-Path $Root '.venv')) {
    Write-Host '>> Removing old .venv' -ForegroundColor Yellow
    Remove-Item -Recurse -Force (Join-Path $Root '.venv')
}

Write-Host '>> python -m venv .venv' -ForegroundColor Cyan
python -m venv .venv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$extras = @('warehouse', 'graph')
if ($Ui) { $extras += 'ui' }
$spec = '.[' + ($extras -join ',') + ']'

Write-Host ">> pip install -e $spec" -ForegroundColor Cyan
& (Join-Path $Root '.venv\Scripts\pip.exe') install -e $spec
exit $LASTEXITCODE
