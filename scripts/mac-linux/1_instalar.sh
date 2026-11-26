#!/usr/bin/env bash
# Instala todo lo necesario (Mac/Linux). Uso: bash scripts/mac-linux/1_instalar.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
for p in python3 node ollama; do command -v "$p" >/dev/null || { echo "Falta $p. Instálalo y vuelve a correr."; exit 1; }; done
[ -d backend/.venv ] || python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip -q
backend/.venv/bin/python -m pip install -r backend/requirements.txt -q
(cd frontend && npm ci --no-audit --no-fund)
if [ ! -f .env ]; then
  backend/.venv/bin/python -c "import re,secrets,pathlib; t=pathlib.Path('.env.example').read_text(); pathlib.Path('.env').write_text(re.sub(r'(?m)^BOT_API_KEY=.*$', 'BOT_API_KEY='+secrets.token_urlsafe(32), t))"
  echo "Se creó .env con una BOT_API_KEY nueva."
fi
ollama pull "$(grep -E '^OLLAMA_MODELO=' .env | cut -d= -f2-)"
[ -f models/modelo_mlp.json ] || echo "Aviso: falta models/modelo_mlp.json (ver models/README.md)."
echo "Listo. Siguiente: bash scripts/mac-linux/2_iniciar.sh"
