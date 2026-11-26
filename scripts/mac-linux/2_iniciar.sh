#!/usr/bin/env bash
# Enciende Ollama (si hace falta), backend y panel. Ctrl+C apaga todo. Uso: bash scripts/mac-linux/2_iniciar.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -f .env ] || { echo "Primero corre scripts/mac-linux/1_instalar.sh"; exit 1; }
curl -s --max-time 3 http://127.0.0.1:11434/api/version >/dev/null || { (ollama serve >/dev/null 2>&1 &); sleep 4; }
(cd backend && .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000) &
BACK=$!
(cd frontend && npm run dev) &
FRONT=$!
trap 'kill $BACK $FRONT 2>/dev/null' EXIT
echo "Panel: http://127.0.0.1:5173  ·  API: http://127.0.0.1:8000/docs  (clave: BOT_API_KEY de .env)"
wait
