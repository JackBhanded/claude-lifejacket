<#
  Claude Lifejacket - friendly Windows installer.

  Run it one of these ways:
    - Right-click this file -> "Run with PowerShell", OR
    - In a terminal:  powershell -ExecutionPolicy Bypass -File .\install.ps1

  No admin rights needed - it installs just for you.
#>

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Say($text, $color = "Gray") { Write-Host "  $text" -ForegroundColor $color }

Write-Host ""
Say "Claude Lifejacket - let's get you set up" "Cyan"
Write-Host ""

# 1. Find a Python.
$py = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) {
    Say "I couldn't find Python on this machine." "Red"
    Say "Grab it from https://www.python.org/downloads/ (tick 'Add Python to PATH'" "Red"
    Say "during setup), then run me again. I'll be right here." "Red"
    exit 1
}
Say "Found Python. Installing Lifejacket (just for you, no admin needed)..."

# 2. Install the package so both 'python -m claude_lifejacket' and the
#    SessionStart hook work reliably.
& $py -m pip install --user . | Out-Null
if ($LASTEXITCODE -ne 0) {
    Say "The install hit a snag - the pip output above should say why." "Red"
    exit 1
}
Say "Installed cleanly." "Green"

# 3. Create the logbook.
& $py -m claude_lifejacket init | Out-Null

Write-Host ""
Say "All set - your lifejacket is on. A few friendly next steps:" "Green"
Write-Host ""
Say "  1. Find your projects:   $py -m claude_lifejacket discover"
Say "  2. Share them around:    $py -m claude_lifejacket sync"
Say "  3. See the dashboard:    $py -m claude_lifejacket dashboard"
Say "  4. Make it automatic:    $py -m claude_lifejacket install-hook"
Write-Host ""
Say "Tip: from this folder you can also just type  .\lifejacket discover  etc." "DarkGray"
Write-Host ""
