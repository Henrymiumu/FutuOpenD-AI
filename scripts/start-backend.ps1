$ErrorActionPreference = "Stop"
Set-Location "D:\Grok\Futu\backend"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating venv..." -ForegroundColor Cyan
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Write-Host "Starting API on http://127.0.0.1:8000 ..." -ForegroundColor Green
python run.py
