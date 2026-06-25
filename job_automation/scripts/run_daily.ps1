# Daily incremental scrape for Windows Task Scheduler.
# Runs the free stack and exports only postings not seen in a previous run.
#
# Register it to run every day at 08:00 (adjust as you like):
#   schtasks /Create /SC DAILY /TN "AI Job Scrape" /ST 08:00 ^
#     /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"%CD%\scripts\run_daily.ps1\""
# Remove it again with:
#   schtasks /Delete /TN "AI Job Scrape" /F

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot   # ...\job_automation
Set-Location -Path $ProjectDir

$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }  # fall back to PATH

& $Python main.py --region europe --remote true --min-score 60 --new-only true --export all
