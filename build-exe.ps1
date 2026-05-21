<#
  Build 'Claude Lifejacket.exe' - a single, double-clickable Windows app.

  Run:  powershell -ExecutionPolicy Bypass -File .\build-exe.ps1
  Output: dist\Claude Lifejacket.exe
#>

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Say($t, $c = "Gray") { Write-Host "  $t" -ForegroundColor $c }

Write-Host ""
Say "Building Claude Lifejacket.exe ..." "Cyan"
Write-Host ""

Say "Making sure the build tools are here (PyInstaller + PySide6)..."
python -m pip install --user --upgrade pyinstaller PySide6 | Out-Null

Say "Packaging (this takes a minute the first time)..."
python -m PyInstaller --noconfirm --onefile --windowed `
    --name "Claude Lifejacket" `
    --paths src `
    --collect-submodules claude_lifejacket `
    gui_launcher.py

Write-Host ""
if (Test-Path ".\dist\Claude Lifejacket.exe") {
    Say "Done! Your app is at  dist\Claude Lifejacket.exe" "Green"
    Say "Double-click it to run - no terminal needed." "DarkGray"
} else {
    Say "Hmm, the .exe didn't appear - the PyInstaller output above should say why." "Red"
}
Write-Host ""
