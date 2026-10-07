# Create GitHub repo and push (requires: gh auth login OR pre-created empty repo).
param(
    [string]$Owner = "LingerDavid",
    [string]$Repo = "enterprise-scout-mcp",
    [switch]$CreateWithGh
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$Remote = "git@github.com:${Owner}/${Repo}.git"

if ($CreateWithGh) {
    gh auth status | Out-Null
    gh repo create "${Owner}/${Repo}" --public `
        --description "MCP orchestrator for enterprise registry intelligence (ENScan / aiqicha / Handaas)" `
        --source $Root --remote origin --push
    exit $LASTEXITCODE
}

git remote remove origin 2>$null
git remote add origin $Remote
git push -u origin master
exit $LASTEXITCODE
