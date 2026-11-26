#!/usr/bin/env bash
# Genera toda la evidencia en docs/. Uso: bash scripts/mac-linux/3_evidencia.sh [--desde AAAA-MM-DD] [--ciclos N]
set -euo pipefail
cd "$(dirname "$0")/../../backend"
.venv/bin/python -m app.evidencia "$@"
