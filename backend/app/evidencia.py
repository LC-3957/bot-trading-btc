"""Corre toda la evidencia del proyecto en orden y deja los resultados en docs/.

1. Pruebas automáticas (pytest -v)       → docs/pruebas_automaticas.txt
2. Diagnóstico del LLM local             → docs/entorno_llm.md
3. Validación del MLP con datos de MEXC  → docs/validacion_mexc.md
4. Los 9 errores provocados              → docs/errores/
5. Replay de 25 ciclos y comparación     → docs/comparacion_replay.md
6. Informe con las cifras reales         → docs/informe.md

Uso (desde backend/, con Ollama encendido):
    python -m app.evidencia                         # replay desde hace 40 días, 25 ciclos
    python -m app.evidencia --desde 2026-09-15 --ciclos 30
    python -m app.evidencia --sin-replay            # todo menos el replay (es el paso más lento)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DOCS = BACKEND.parent / "docs"


def paso(titulo: str, args: list[str], guardar: Path | None = None) -> bool:
    print(f"\n=== {titulo} ===", flush=True)
    env = os.environ | {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, *args], cwd=BACKEND, env=env, text=True, encoding="utf-8",
                       capture_output=guardar is not None)
    if guardar is not None:
        guardar.write_text(r.stdout + r.stderr, encoding="utf-8")
        print("\n".join((r.stdout + r.stderr).strip().splitlines()[-3:]))
    print(f"--> {'OK' if r.returncode == 0 else f'FALLÓ (código {r.returncode})'}", flush=True)
    return r.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera toda la evidencia del agente en docs/.")
    ap.add_argument("--desde", default=(date.today() - timedelta(days=40)).isoformat(), help="Primera vela del replay")
    ap.add_argument("--ciclos", type=int, default=25)
    ap.add_argument("--sin-replay", action="store_true")
    a = ap.parse_args()
    DOCS.mkdir(exist_ok=True)

    resultados = {
        "Pruebas automáticas": paso("1/6 Pruebas automáticas", ["-m", "pytest", "-v", "tests"], DOCS / "pruebas_automaticas.txt"),
        "Diagnóstico del LLM local": paso("2/6 Diagnóstico del LLM local", ["-m", "app.diagnostico"]),
        "Validación con MEXC": paso("3/6 Validación del MLP con datos de MEXC", ["-m", "app.validar"]),
        "Errores provocados": paso("4/6 Errores provocados", ["-m", "app.provocar", "todos"]),
    }
    if not a.sin_replay:
        resultados["Replay y comparación"] = paso(f"5/6 Replay desde {a.desde} ({a.ciclos} ciclos)",
                                                  ["-m", "app.replay", "--desde", a.desde, "--ciclos", str(a.ciclos)])
    resultados["Informe"] = paso("6/6 Informe", ["-m", "app.informe"])

    print("\n=== Resumen ===")
    for nombre, ok in resultados.items():
        print(f"  [{'OK' if ok else '!!'}] {nombre}")
    print(f"\nRevisa docs/informe.md, completa la sección 10 (Conclusiones) y sube la carpeta docs/ al repositorio.")
    sys.exit(0 if all(resultados.values()) else 1)


if __name__ == "__main__":
    main()
