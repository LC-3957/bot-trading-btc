"""Comparación exigida por el protocolo, en el mismo periodo y con los mismos costos:

1. Comprar y mantener: compra en la primera ejecución y no vuelve a operar.
2. Modelo sin LLM: comprado si el pronóstico del MLP supera UMBRAL_MODELO; en efectivo si no.
3. Agente con LLM: sigue la acción final registrada (COMPRAR, VENDER o MANTENER) después de la validación y el riesgo.

Las tres usan las mismas reglas del simulador Paper (exposición, costo, deslizamiento, precisión) y
el mismo precio: la apertura de la vela siguiente a cada decisión. Al final se liquida la posición
abierta con su costo de venta, para que el rendimiento sea neto.
"""
from __future__ import annotations

import math

from .mexc import ReglasPar
from .paper import Cartera, SaldoInsuficienteError, ejecutar


def _simular(decisiones: list[dict], objetivo, cfg, reglas: ReglasPar) -> dict:
    c = Cartera(efectivo=cfg.capital_inicial)
    curva, cerradas, ops, entrada = [cfg.capital_inicial], [], 0, None
    for i, d in enumerate(decisiones):
        precio = d["precio_ejecucion"]
        quiere = objetivo(i, d, c.posicion)
        accion = "COMPRAR" if quiere and not c.posicion else "VENDER" if (not quiere and c.posicion) else "MANTENER"
        if accion != "MANTENER":
            antes = c.patrimonio(precio)
            try:
                r = ejecutar(accion, c, precio, reglas, cfg)
            except SaldoInsuficienteError:
                r = None
            if r and r.accion_final != "MANTENER":
                ops += 1
                if accion == "COMPRAR":
                    entrada = antes
                else:
                    cerradas.append(c.efectivo - entrada)
        curva.append(c.patrimonio(precio))
    if c.posicion and decisiones:                                   # liquidación final con costo
        ejecutar("VENDER", c, decisiones[-1]["precio_ejecucion"], reglas, cfg)
        ops += 1
        cerradas.append(c.efectivo - entrada)
        curva[-1] = c.efectivo
    pico, dd = -math.inf, 0.0
    for v in curva:
        pico = max(pico, v); dd = min(dd, v / pico - 1)
    return dict(rendimiento_neto=curva[-1] / cfg.capital_inicial - 1, max_drawdown=dd, operaciones=ops,
                operaciones_cerradas=len(cerradas),
                win_rate=(sum(x > 0 for x in cerradas) / len(cerradas)) if cerradas else None,
                patrimonio_final=curva[-1])


def comparar(decisiones: list[dict], cfg, umbral: float | None = None, reglas: ReglasPar | None = None) -> dict:
    decisiones = [d for d in sorted(decisiones, key=lambda d: d["fecha_vela"]) if d.get("precio_ejecucion")]
    reglas = reglas or ReglasPar()
    umbral = cfg.umbral_modelo if umbral is None else umbral
    if not decisiones:
        return {"periodo": None, "ciclos": 0, "estrategias": []}

    def agente(i, d, pos):
        return {"COMPRAR": True, "VENDER": False}.get(d["accion_final"], bool(pos))

    filas = [
        {"estrategia": "Comprar y mantener", **_simular(decisiones, lambda i, d, p: True, cfg, reglas)},
        {"estrategia": f"Modelo sin LLM (pronóstico > {umbral:.2%})",
         **_simular(decisiones, lambda i, d, p: (d["pronostico"] or 0) > umbral, cfg, reglas)},
        {"estrategia": "Agente con LLM", **_simular(decisiones, agente, cfg, reglas)},
    ]
    lat = [d["latencia_s"] for d in decisiones if d.get("latencia_s") is not None]
    filas[2]["latencia_media_s"] = sum(lat) / len(lat) if lat else None
    filas[2]["rechazadas"] = sum(1 for d in decisiones if not d["aprobada"])
    filas[2]["propuestas_invalidas"] = sum(1 for d in decisiones if d["accion_propuesta"] is None)
    return {"periodo": [decisiones[0]["fecha_vela"], decisiones[-1]["fecha_vela"]], "ciclos": len(decisiones),
            "costo": cfg.costo, "deslizamiento": cfg.deslizamiento, "umbral_modelo": umbral, "estrategias": filas}


def a_markdown(res: dict, origen: str) -> str:
    if not res["ciclos"]:
        return f"# Comparación ({origen})\n\nNo hay ciclos registrados.\n"
    pct = lambda v: "—" if v is None else f"{v:.2%}"
    lineas = [f"# Comparación de estrategias ({origen})", "",
              f"- Periodo: {res['periodo'][0]} a {res['periodo'][1]} ({res['ciclos']} ciclos diarios)",
              f"- Costo por operación: {res['costo']:.2%} · deslizamiento: {res['deslizamiento']:.2%}",
              f"- Umbral del modelo sin LLM: {res['umbral_modelo']:.2%}", "",
              "| Estrategia | Rendimiento neto | Máx. drawdown | Operaciones | Win Rate | Latencia media | Rechazadas |",
              "|---|---|---|---|---|---|---|"]
    for f in res["estrategias"]:
        lat = f.get("latencia_media_s")
        lineas.append(f"| {f['estrategia']} | {pct(f['rendimiento_neto'])} | {pct(f['max_drawdown'])} | {f['operaciones']} | "
                      f"{pct(f['win_rate'])} | {'—' if lat is None else f'{lat:.1f} s'} | {f.get('rechazadas', '—')} |")
    return "\n".join(lineas) + "\n"
