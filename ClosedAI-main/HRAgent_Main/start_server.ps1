# Start the HRAgents agent server in UTF-8 mode.
#
# PYTHONUTF8=1 is REQUIRED on Windows: without it, Python defaults to the
# cp1252 codec and the server crashes with UnicodeEncodeError when it persists
# any event/text containing non-Latin1 characters (emojis, em-dashes, etc.),
# which silently aborts the agent run. Always launch the backend via this script.
#
# Usage:  .\start_server.ps1            (defaults to port 8001)
#         .\start_server.ps1 -Port 8010

param(
    [int]$Port = 8001
)

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Error "venv python not found at $python. Create the venv first (uv sync)."
    exit 1
}

Write-Host "Starting HRAgents backend on port $Port (UTF-8 mode)..."
& $python -m runtime.server --port $Port
