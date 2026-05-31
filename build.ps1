# Build the self-contained Mizuno Menace executable (Windows).
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"

Write-Host "Installing build dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements-dev.txt

Write-Host "Building MizunoMenace.exe with PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean MizunoMenace.spec

$exe = Join-Path $PSScriptRoot "dist\MizunoMenace.exe"
if (Test-Path $exe) {
    Write-Host "`nDone. Standalone exe at:" -ForegroundColor Green
    Write-Host "  $exe"
    Write-Host "`nShip this single file. Optionally place a products.json and/or .env next to it."
} else {
    Write-Host "Build failed: $exe not found." -ForegroundColor Red
    exit 1
}
