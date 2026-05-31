# Build the self-contained Mizuno Menace executable (Windows).
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"

Write-Host "Installing build dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements-dev.txt

Write-Host "Building MizunoMenace.exe with PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean MizunoMenace.spec

$dist = Join-Path $PSScriptRoot "dist"
$exe = Join-Path $dist "MizunoMenace.exe"
$envExample = Join-Path $PSScriptRoot ".env.example"
$distEnvExample = Join-Path $dist ".env.example"

if (Test-Path $exe) {
    Copy-Item -Force $envExample $distEnvExample
    Write-Host "`nDone. Standalone exe at:" -ForegroundColor Green
    Write-Host "  $exe"
    Write-Host "`nFinalize (one-time):" -ForegroundColor Cyan
    Write-Host "  1. Copy dist\.env.example to dist\.env (or %LOCALAPPDATA%\MizunoMenace\.env)"
    Write-Host "  2. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET from https://developer.ebay.com/"
    Write-Host "  3. Run MizunoMenace.exe"
} else {
    Write-Host "Build failed: $exe not found." -ForegroundColor Red
    exit 1
}
