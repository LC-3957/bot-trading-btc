"""Variables y pronóstico.

El pronóstico usa el MLP elegido en la práctica (avances 2–4), exportado desde Colab a
`models/modelo_mlp.json` con `scripts/exportar_modelo_colab.py`. El paso hacia adelante se hace
con NumPy, así que el backend no necesita PyTorch. Si el archivo no existe, se usa el pronóstico
cero (rendimiento esperado = 0) y la interfaz lo indica.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

NUM_LAGS = 20


class ModeloError(Exception):
    """Archivo de modelo inválido o entradas con forma incorrecta."""


def variables(closes: list[float]) -> dict:
    """Variables conocidas al cierre de t: 20 rendimientos, SMA20, distancia y volatilidad."""
    c = np.asarray(closes, dtype=float)
    if len(c) < NUM_LAGS + 1:
        raise ModeloError(f"Se necesitan al menos {NUM_LAGS + 1} cierres; hay {len(c)}.")
    if not np.all(np.isfinite(c)) or np.any(c <= 0):
        raise ModeloError("Hay cierres no válidos (NaN, infinitos o no positivos).")
    r = c[1:] / c[:-1] - 1
    lags = r[::-1][:NUM_LAGS]                                   # r_t, r_t-1, …, r_t-19
    sma20 = float(c[-20:].mean())
    return dict(lags=lags.tolist(), rend_ultimo=float(r[-1]), sma20=sma20,
                dist_sma20=float(c[-1] / sma20 - 1), vol20=float(r[-20:].std(ddof=1)), cierre=float(c[-1]))


@dataclass
class Predictor:
    nombre: str
    capas: list[tuple[np.ndarray, np.ndarray]] | None = None
    x_media: np.ndarray | None = None
    x_escala: np.ndarray | None = None
    y_media: float = 0.0
    y_desv: float = 1.0
    meta: dict | None = None

    @property
    def cargado(self) -> bool:
        return self.capas is not None

    def predecir(self, lags: list[float]) -> float:
        if not self.cargado:
            return 0.0                                          # pronóstico cero
        x = np.asarray(lags, dtype=float)
        if x.shape != (NUM_LAGS,):
            raise ModeloError(f"Forma esperada ({NUM_LAGS},); recibida {x.shape}")
        h = (x - self.x_media) / self.x_escala
        for i, (W, b) in enumerate(self.capas):
            h = h @ W.T + b
            if i < len(self.capas) - 1:
                h = np.maximum(h, 0.0)                          # ReLU en capas ocultas
        y = float(h[0]) * self.y_desv + self.y_media
        if not np.isfinite(y):
            raise ModeloError("Pronóstico no finito.")
        return y


def cargar_predictor(ruta: str) -> Predictor:
    p = Path(ruta)
    if not p.exists():
        return Predictor(nombre="Pronóstico cero (no hay models/modelo_mlp.json)")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        capas = [(np.asarray(c["W"], float), np.asarray(c["b"], float)) for c in d["capas"]]
        pred = Predictor(nombre=d.get("nombre", "MLP"), capas=capas,
                         x_media=np.asarray(d["escalador"]["media"], float),
                         x_escala=np.asarray(d["escalador"]["escala"], float),
                         y_media=float(d["objetivo"]["media"]), y_desv=float(d["objetivo"]["desv"]),
                         meta={k: v for k, v in d.items() if k not in ("capas", "escalador")})
    except (KeyError, TypeError, ValueError) as e:
        raise ModeloError(f"{ruta} no tiene el formato esperado: {e}") from e
    if pred.x_media.shape != (NUM_LAGS,) or capas[0][0].shape[1] != NUM_LAGS or capas[-1][0].shape[0] != 1:
        raise ModeloError("El modelo exportado no corresponde a 20 rezagos y 1 salida.")
    return pred
