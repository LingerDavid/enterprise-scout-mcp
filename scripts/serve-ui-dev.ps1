# Fine UI — dev: escout serve (:8790) + vite (:5179, /api proxied).
param(
    [string]$ApiHost = '127.0.0.1',
    [int]$ApiPort = 8790,
    [int]$UiPort = 5179,
    [string]$Config = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib\repo.ps1')
$Root = Get-RepoRoot
Set-Location $Root

Get-VenvPython -Root $Root | Out-Null
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm not found; install Node.js for ui dev mode'
}

$ui = Join-Path $Root 'ui'
if (-not (Test-Path (Join-Path $ui 'node_modules'))) {
    Push-Location $ui
    Write-Host '>> npm install (ui)' -ForegroundColor Cyan
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Pop-Location
}

$serveArgs = @('serve', '--host', $ApiHost, '--port', "$ApiPort")
if ($Config) { $serveArgs += @('-c', $Config) }

Write-Host ">> API  http://${ApiHost}:$ApiPort" -ForegroundColor Green
Write-Host ">> UI   http://127.0.0.1:$UiPort  (proxy /api -> $ApiPort)" -ForegroundColor Green
Write-Host '   Ctrl+C stops both' -ForegroundColor DarkGray

$apiJob = Start-Job -ScriptBlock {
    param($ScriptRoot, $Root, $ServeArgs)
    . (Join-Path $ScriptRoot 'lib\repo.ps1')
    Set-Location $Root
    Invoke-Escout -Root $Root -EscoutArgs $ServeArgs
} -ArgumentList $PSScriptRoot, $Root, $serveArgs

Start-Sleep -Seconds 2

Push-Location $ui
try {
    $env:VITE_API_PORT = "$ApiPort"
    npm run dev -- --port $UiPort --host 127.0.0.1
    $code = $LASTEXITCODE
} finally {
    Pop-Location
    Stop-Job $apiJob -ErrorAction SilentlyContinue
    Remove-Job $apiJob -Force -ErrorAction SilentlyContinue
}
exit $code
