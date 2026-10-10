# Fine UI — production: escout serve on :8790 (serves ui/dist when built).
param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8790,
    [string]$Config = '',
    [switch]$SkipBuild,
    [switch]$Rebuild
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib\repo.ps1')
$Root = Get-RepoRoot
Set-Location $Root

Get-VenvPython -Root $Root | Out-Null

if (-not $SkipBuild) {
    Ensure-UiBuilt -Root $Root -Force:$Rebuild
}

$escoutArgs = @('serve', '--host', $BindHost, '--port', "$Port")
if ($Config) { $escoutArgs += @('-c', $Config) }

Write-Host ">> escout serve http://${BindHost}:$Port" -ForegroundColor Green
Write-Host "   (API + ui/dist; Ctrl+C to stop)" -ForegroundColor DarkGray
Invoke-Escout -Root $Root -EscoutArgs $escoutArgs
exit $LASTEXITCODE
