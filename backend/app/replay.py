"""Modo replay: recorre velas diarias históricas de MEXC con el mismo ciclo del agente.

- Cada ciclo corresponde a UNA vela diaria (no se cambia la frecuencia de decisión).
- Todo se guarda con origen = "replay", separado de la operación en vivo.
- El reloj se coloca 1 hora después del cierre de cada vela: el agente solo ve las velas cerradas
  hasta ese momento y ejecuta en la apertura de la vela siguiente, igual que en vivo.

Uso (desde backend/):
    python -m app.replay --desde 2026-09-01 --ciclos 25
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from .agente import Agente
from .comparacion import a_markdown, comparar
from .config import RAIZ, cargar
from .db import BD
from .llm import ClienteOllama
from .mexc import ClienteMEXC, ReglasPar, Vela
from .modelo import cargar_predictor

UNA_HORA = 3_600_000


class MercadoReplay:
    """Sirve al agente las velas históricas como si fuera la API en vivo, según un reloj simulado."""

    def __init__(self, historial: list[Vela], reglas: ReglasPar, reloj):
        self.historial, self._reglas, self.reloj = historial, reglas, reloj

    def velas(self, simbolo: str, intervalo: str = "1d", limite: int = 60) -> list[Vela]:
        ahora = self.reloj()
        return [v for v in self.historial if v.apertura_ms <= ahora][-limite:]

    def reglas(self, simbolo: str) -> ReglasPar:
        return self._reglas


def correr(cfg, mercado_real: ClienteMEXC, llm: ClienteOllama, predictor, bd: BD, desde: str, ciclos: int,
           pausa_s: float = 0.0, reiniciar: bool = True, aviso=print) -> dict:
    historial = mercado_real.velas(cfg.simbolo, cfg.intervalo, limite=1000)
    try:
        reglas = mercado_real.reglas(cfg.simbolo)
    except Exception:
        reglas = ReglasPar()
    candidatas = [i for i, v in enumerate(historial) if v.fecha >= desde and i + 1 < len(historial) and i >= 25]
    if not candidatas:
        raise ValueError(f"No hay velas desde {desde} con historia suficiente (se requieren 25 previas y 1 posterior).")
    if reiniciar:
        bd.borrar_origen("replay")
    reloj = {"t": 0}
    agente = Agente(cfg, bd, MercadoReplay(historial, reglas, lambda: reloj["t"]), llm, predictor,
                    reloj_ms=lambda: reloj["t"], origen="replay")
    for n, i in enumerate(candidatas[:ciclos], 1):
        reloj["t"] = historial[i].cierre_ms + UNA_HORA
        r = agente.ciclo()
        aviso(f"[replay {n:>3}/{min(ciclos, len(candidatas))}] {historial[i].fecha} → "
              f"{r.get('accion_final', r['resultado'])} ({r.get('motivo', '')})")
        if pausa_s:
            time.sleep(pausa_s)
    return comparar(bd.decisiones_cronologicas("replay"), cfg, reglas=reglas)


def main() -> None:
    ap = argparse.ArgumentParser(description="Replay histórico del agente (origen = replay).")
    ap.add_argument("--desde", required=True, help="Primera vela a evaluar, AAAA-MM-DD")
    ap.add_argument("--ciclos", type=int, default=25)
    ap.add_argument("--pausa", type=float, default=0.0, help="Segundos de espera entre ciclos")
    ap.add_argument("--conservar", action="store_true", help="No borrar el replay anterior")
    a = ap.parse_args()
    datetime.strptime(a.desde, "%Y-%m-%d")
    cfg = cargar()
    res = correr(cfg, ClienteMEXC(cfg.mexc_url), ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, cfg.ollama_timeout_s),
                 cargar_predictor(cfg.modelo_path), BD(cfg.db_path), a.desde, a.ciclos, a.pausa, not a.conservar)
    salida = Path(RAIZ) / "docs" / "comparacion_replay.md"
    salida.parent.mkdir(exist_ok=True)
    texto = a_markdown(res, "replay") + f"\n_Generado el {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC con `python -m app.replay`._\n"
    salida.write_text(texto, encoding="utf-8")
    print("\n" + texto + f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
