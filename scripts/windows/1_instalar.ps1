# Instala todo lo necesario para correr el bot en Windows.
# Uso (desde la carpeta del repo):  powershell -ExecutionPolicy Bypass -File scripts\windows\1_instalar.ps1
$ErrorActionPreference = "Stop"
$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Raiz
$env:PYTHONUTF8 = "1"

function Revisar($paso) {
    if ($LASTEXITCODE -ne 0) { Write-Host "Falló: $paso (código $LASTEXITCODE). Revisa el mensaje de arriba." -ForegroundColor Red; exit 1 }
}

function Falta($programa, $donde) {
    Write-Host "Falta $programa. Instálalo desde $donde y vuelve a correr este script." -ForegroundColor Red
    exit 1
}

Write-Host "== Revisando programas ==" -ForegroundColor Cyan
if (Get-Command py -ErrorAction SilentlyContinue) { $PyExe = "py"; $PyArgs = @("-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $PyExe = "python"; $PyArgs = @() }
else { Falta "Python 3.11 o superior" "https://www.python.org/downloads/ (marca 'Add python.exe to PATH')" }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Falta "Node.js 20 LTS" "https://nodejs.org" }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { Falta "Ollama" "https://ollama.com/download" }
& $PyExe @PyArgs --version
node --version
ollama --version

Write-Host "`n== Backend: entorno virtual y dependencias ==" -ForegroundColor Cyan
if (-not (Test-Path "backend\.venv")) { & $PyExe @PyArgs -m venv backend\.venv; Revisar "crear el entorno virtual" }
$VPy = Join-Path $Raiz "backend\.venv\Scripts\python.exe"
& $VPy -m pip install --upgrade pip --quiet
& $VPy -m pip install -r backend\requirements.txt --quiet; Revisar "instalar dependencias de Python"

Write-Host "`n== Interfaz: dependencias ==" -ForegroundColor Cyan
Push-Location frontend
npm ci --no-audit --no-fund; Revisar "instalar dependencias de la interfaz"
Pop-Location

Write-Host "`n== Configuración (.env) ==" -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
    & $VPy -c "import re,secrets,pathlib; t=pathlib.Path('.env.example').read_text(encoding='utf-8'); pathlib.Path('.env').write_text(re.sub(r'(?m)^BOT_API_KEY=.*$', 'BOT_API_KEY='+secrets.token_urlsafe(32), t), encoding='utf-8')"
    Write-Host "Se creó .env con una BOT_API_KEY nueva (ábrelo para copiarla al entrar al panel)."
} else { Write-Host ".env ya existe: no se modificó." }

Write-Host "`n== LLM local ==" -ForegroundColor Cyan
$Modelo = & $VPy -c "import re,pathlib; m=re.search(r'(?m)^OLLAMA_MODELO=(.+)$', pathlib.Path('.env').read_text(encoding='utf-8')); print(m.group(1).strip() if m else 'qwen2.5:7b')"
Write-Host "Descargando el modelo $Modelo (solo la primera vez tarda)..."
ollama pull $Modelo; Revisar "descargar el modelo $Modelo en Ollama (¿está abierta la app de Ollama?)"

if (-not (Test-Path "models\modelo_mlp.json")) {
    Write-Host "`nAviso: falta models\modelo_mlp.json. El bot funciona con el pronóstico cero hasta que lo exportes desde Colab (ver models\README.md)." -ForegroundColor Yellow
}
Write-Host "`nListo. Siguiente paso: scripts\windows\2_iniciar.ps1" -ForegroundColor Green
