# Validación del modelo con datos de MEXC (BTCUSDT)

- Modelo: MLP16
- Periodo evaluado: 2025-08-04 a 2026-11-24 (478 pronósticos diarios)

| Métrica | MLP | Pronóstico cero |
|---|---|---|
| MAE | 0.016021 | 0.015769 |
| RMSE | 0.022692 | 0.022425 |
| Precisión direccional | 47.9% | — |

Cambio de RMSE frente al pronóstico cero: -1.19%. El MLP NO mejora al pronóstico cero con datos de MEXC: sus pronósticos deben tomarse con cautela.

Nota: parte de este periodo puede coincidir con datos usados para entrenar el modelo en Colab (otra fuente, Yahoo Finance). Lo que se mide aquí es si el modelo se comporta igual con los precios de MEXC.

_Generado el 2026-11-25 23:09 UTC con `python -m app.validar`._
