# Enciende Ollama (si hace falta), el backend y el panel, y abre el navegador.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\windows\2_iniciar.ps1
$ErrorActionPreference = "Stop"
$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not (Test-Path (Join-Path $Raiz ".env"))) { Write-Host "Primero corre scripts\windows\1_instalar.ps1" -ForegroundColor Red; exit 1 }

try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 3 | Out-Null; Write-Host "Ollama ya está encendido." }
catch {
    Write-Host "Encendiendo Ollama..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
    Start-Sleep -Seconds 4
}

$Back = "Set-Location '$Raiz\backend'; `$env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000"
$Front = "Set-Location '$Raiz\frontend'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $Back
Start-Process powershell -ArgumentList "-NoExit", "-Command", $Front
Start-Sleep -Seconds 6
Start-Process "http://127.0.0.1:5173"
Write-Host "`nBackend: http://127.0.0.1:8000/docs   Panel: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "Para entrar al panel usa la BOT_API_KEY de tu archivo .env. Para apagar todo, cierra las dos ventanas de PowerShell."
