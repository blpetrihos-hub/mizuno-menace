# Copy the built exe to the Desktop folder and create the launcher shortcut.
# Usage:  powershell -ExecutionPolicy Bypass -File deploy-desktop.ps1

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$distExe = Join-Path $root "dist\MizunoMenace.exe"
$desktopFolder = Join-Path ([Environment]::GetFolderPath("Desktop")) "Mizuno Menace"
$shortcutPath = Join-Path $desktopFolder "Click Me To Run.lnk"
$targetExe = Join-Path $desktopFolder "MizunoMenace.exe"

if (-not (Test-Path $distExe)) {
    Write-Host "Build first: powershell -ExecutionPolicy Bypass -File build.ps1" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $desktopFolder | Out-Null
Copy-Item -Force $distExe $targetExe

$envSrc = Join-Path $root ".env"
$envDst = Join-Path $desktopFolder ".env"
if (Test-Path $envSrc) {
    Copy-Item -Force $envSrc $envDst
}

$logoSrc = Join-Path $root "mizuno_menace\assets\logo.png"
if (Test-Path $logoSrc) {
    Copy-Item -Force $logoSrc (Join-Path $desktopFolder "logo.png")
}

Get-ChildItem $desktopFolder -Filter "*.lnk" | Remove-Item -Force

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetExe
$shortcut.WorkingDirectory = $desktopFolder
$shortcut.Description = "Mizuno Menace deal finder"
$shortcut.Save()

Write-Host "Desktop app updated:" -ForegroundColor Green
Write-Host "  $shortcutPath"
