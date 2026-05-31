# Zip Desktop\Mizuno Menace to send to someone (same 3 files, no readme).
# Usage:  powershell -ExecutionPolicy Bypass -File package-share.ps1

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$desktopFolder = Join-Path ([Environment]::GetFolderPath("Desktop")) "Mizuno Menace"
$zipPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Mizuno Menace.zip"

& (Join-Path $root "deploy-desktop.ps1")

if (-not (Test-Path (Join-Path $desktopFolder "MizunoMenace.exe"))) {
    exit 1
}

if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path (Join-Path $desktopFolder "*") -DestinationPath $zipPath -Force

Write-Host "Share zip:" -ForegroundColor Green
Write-Host "  $zipPath"
