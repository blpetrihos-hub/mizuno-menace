# Copy the built exe to Desktop\Mizuno Menace (exe, .env, shortcut only).
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

# Keep the folder minimal: remove extras from older deploys.
foreach ($extra in @("logo.png", "START-HERE.txt", "START HERE.txt", "Mizuno Menace.lnk")) {
    $path = Join-Path $desktopFolder $extra
    if (Test-Path $path) { Remove-Item -Force $path }
}

Get-ChildItem $desktopFolder -Filter "*.lnk" | Remove-Item -Force

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetExe
$shortcut.WorkingDirectory = $desktopFolder
$shortcut.Description = "Mizuno Menace deal finder"
$shortcut.Save()

Write-Host "Desktop app ready:" -ForegroundColor Green
Write-Host "  $desktopFolder"
Write-Host "  Click Me To Run.lnk, MizunoMenace.exe, .env"
