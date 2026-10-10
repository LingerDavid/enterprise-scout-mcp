# Shared helpers for enterprise-scout-mcp launch scripts.

function Get-RepoRoot {
    $dir = $PSScriptRoot
    while ($true) {
        if (Test-Path (Join-Path $dir 'pyproject.toml')) {
            return (Resolve-Path $dir).Path
        }
        $parent = Split-Path $dir -Parent
        if (-not $parent -or $parent -eq $dir) {
            throw "Could not find repo root (pyproject.toml) from $PSScriptRoot"
        }
        $dir = $parent
    }
}

function Get-VenvPython {
    param([string]$Root = (Get-RepoRoot))
    $py = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path $py) { return $py }
    throw @"
.venv not found at $Root\.venv
Create it:
  cd $Root
  .\setup-venv.ps1 -Ui

If 'Unable to copy venvlauncher.exe': .venv already exists or escout is running.
  .\serve-ui.ps1 -SkipBuild    # use existing venv
  # or stop serve, then:
  .\setup-venv.ps1 -Force -Ui
"@
}

function Get-EscoutExe {
    param([string]$Root = (Get-RepoRoot))
    $exe = Join-Path $Root '.venv\Scripts\escout.exe'
    if (Test-Path $exe) { return $exe }
    # Fallback when console_scripts not on PATH but module is installed.
    return $null
}

function Invoke-Escout {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$EscoutArgs,
        [string]$Root = (Get-RepoRoot)
    )
    $exe = Get-EscoutExe -Root $Root
    if ($exe) {
        & $exe @EscoutArgs
        return
    }
    $py = Get-VenvPython -Root $Root
    & $py -m enterprise_scout_mcp.cli @EscoutArgs
}

function Ensure-UiBuilt {
    param(
        [string]$Root = (Get-RepoRoot),
        [switch]$Force
    )
    $dist = Join-Path $Root 'ui\dist\index.html'
    if ((Test-Path $dist) -and -not $Force) { return }
    $ui = Join-Path $Root 'ui'
    if (-not (Test-Path (Join-Path $ui 'package.json'))) {
        throw "ui/package.json missing"
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm not found; install Node.js or run: cd ui && npm run build"
    }
    Push-Location $ui
    try {
        if (-not (Test-Path 'node_modules')) {
            Write-Host '>> npm install (ui)' -ForegroundColor Cyan
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install failed ($LASTEXITCODE)" }
        }
        Write-Host '>> npm run build (ui)' -ForegroundColor Cyan
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed ($LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
}
