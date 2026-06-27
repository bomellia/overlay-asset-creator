param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name build_assets `
    --distpath dist `
    --workpath build\build_assets `
    --specpath build `
    build_assets.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host "Built: $Root\dist\build_assets.exe"
