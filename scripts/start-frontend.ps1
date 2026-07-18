$ErrorActionPreference = "Stop"
Set-Location "D:\Grok\Futu\frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing npm packages..." -ForegroundColor Cyan
    npm install
}

Write-Host "Starting Vue dev server on http://127.0.0.1:5173 ..." -ForegroundColor Green
npm run dev
