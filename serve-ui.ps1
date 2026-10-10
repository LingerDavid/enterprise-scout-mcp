# Launcher at repo root (escout not required on PATH).
& (Join-Path $PSScriptRoot 'scripts\serve-ui.ps1') @args
exit $LASTEXITCODE
