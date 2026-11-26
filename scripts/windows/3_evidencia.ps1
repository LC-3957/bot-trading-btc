# Genera toda la evidencia en docs\: pruebas, diagnóstico del LLM, validación con MEXC,
# 9 errores provocados, replay de 25 ciclos con comparación e informe.
# Requiere Ollama encendido. Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\3_evidencia.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\windows\3_evidencia.ps1 -Desde 2026-09-15 -Ciclos 30
param([string]$Desde = (Get-Date).AddDays(-40).ToString("yyyy-MM-dd"), [int]$Ciclos = 25)
$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONUTF8 = "1"
Set-Location (Join-Path $Raiz "backend")
& .\.venv\Scripts\python.exe -m app.evidencia --desde $Desde --ciclos $Ciclos
