"""Valida el MLP con datos reales de MEXC (el modelo se entrenó con BTC-USD de Yahoo Finance).

Descarga hasta 1000 velas diarias del par configurado, arma las mismas ventanas de 20 rendimientos
y compara el pronóstico del MLP contra el pronóstico cero (referencia del cap. 7).

Uso (desde backend/):  python -m app.validar
Resultado: docs/validacion_mexc.md
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

from .config import RAIZ, cargar
from .mexc import ClienteMEXC
from .modelo import NUM_LAGS, cargar_predictor, variables


def evaluar(cierres: list[float], fechas: list[str], predictor) -> dict:
    if len(cierres) < NUM_LAGS + 30:
        raise ValueError(f"Se necesitan al menos {NUM_LAGS + 30} velas cerradas; hay {len(cierres)}.")
    reales, preds = [], []
    for t in range(NUM_LAGS, len(cierres) - 1):                    # pronóstico al cierre de t para t+1
        preds.append(predictor.predecir(variables(cierres[: t + 1])["lags"]))
        reales.append(cierres[t + 1] / cierres[t] - 1)
    n = len(reales)
    mae = lambda p: sum(abs(a - b) for a, b in zip(p, reales)) / n
    rmse = lambda p: math.sqrt(sum((a - b) ** 2 for a, b in zip(p, reales)) / n)
    pares = [(p, r) for p, r in zip(preds, reales) if p != 0 and r != 0]
    return dict(n=n, desde=fechas[NUM_LAGS + 1], hasta=fechas[-1], modelo=predictor.nombre,
                mae_modelo=mae(preds), rmse_modelo=rmse(preds), mae_cero=mae([0.0] * n), rmse_cero=rmse([0.0] * n),
                direccional=(sum((p > 0) == (r > 0) for p, r in pares) / len(pares)) if pares else None)


def a_markdown(r: dict, simbolo: str) -> str:
    mejora = 1 - r["rmse_modelo"] / r["rmse_cero"]
    veredicto = ("El MLP mejora al pronóstico cero con datos de MEXC." if mejora > 0
                 else "El MLP NO mejora al pronóstico cero con datos de MEXC: sus pronósticos deben tomarse con cautela.")
    d = "—" if r["direccional"] is None else f"{r['direccional']:.1%}"
    return (f"# Validación del modelo con datos de MEXC ({simbolo})\n\n"
            f"- Modelo: {r['modelo']}\n- Periodo evaluado: {r['desde']} a {r['hasta']} ({r['n']} pronósticos diarios)\n\n"
            "| Métrica | MLP | Pronóstico cero |\n|---|---|---|\n"
            f"| MAE | {r['mae_modelo']:.6f} | {r['mae_cero']:.6f} |\n| RMSE | {r['rmse_modelo']:.6f} | {r['rmse_cero']:.6f} |\n"
            f"| Precisión direccional | {d} | — |\n\n"
            f"Cambio de RMSE frente al pronóstico cero: {mejora:+.2%}. {veredicto}\n\n"
            "Nota: parte de este periodo puede coincidir con datos usados para entrenar el modelo en Colab "
            "(otra fuente, Yahoo Finance). Lo que se mide aquí es si el modelo se comporta igual con los precios de MEXC.\n\n"
            f"_Generado el {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC con `python -m app.validar`._\n")


def main() -> None:
    cfg = cargar()
    velas = ClienteMEXC(cfg.mexc_url).velas(cfg.simbolo, cfg.intervalo, limite=1000)
    ahora = int(datetime.now(timezone.utc).timestamp() * 1000)
    cerradas = [v for v in velas if v.cierre_ms < ahora]
    r = evaluar([v.close for v in cerradas], [v.fecha for v in cerradas], cargar_predictor(cfg.modelo_path))
    salida = Path(RAIZ) / "docs" / "validacion_mexc.md"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(a_markdown(r, cfg.simbolo), encoding="utf-8")
    print(a_markdown(r, cfg.simbolo) + f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
