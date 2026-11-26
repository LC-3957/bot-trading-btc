"""Provoca los 9 errores del protocolo contra MEXC y Ollama reales y guarda la evidencia.

Cada escenario usa una base de datos temporal propia (data/errores/), así no ensucia la operación
en vivo ni el replay. Cuando una falla no se puede producir de forma natural en el momento
(por ejemplo, que el LLM devuelva JSON roto), se inyecta y el archivo de evidencia lo dice.

Uso (desde backend/, con Ollama encendido):
    python -m app.provocar todos        # los 9 escenarios
    python -m app.provocar 3            # solo uno (1–9)
Resultado: docs/errores/NN_*.md y docs/errores/resumen.md
"""
from __future__ import annotations

import argparse
import dataclasses
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from .agente import Agente
from .config import RAIZ, cargar
from .db import BD
from .llm import ClienteOllama
from .main import create_app
from .mexc import ClienteMEXC
from .modelo import cargar_predictor

CARPETA_BD = Path(RAIZ) / "data" / "errores"
CARPETA_DOCS = Path(RAIZ) / "docs" / "errores"


class LLMInyectado(ClienteOllama):
    """Envuelve al cliente real y reemplaza su respuesta (solo para los escenarios que lo indican)."""

    def __init__(self, real: ClienteOllama, respuesta):
        self.modelo, self._real, self._respuesta = real.modelo, real, respuesta

    def info(self):
        return self._real.info()

    def proponer(self, contexto):
        return self._respuesta(contexto), 0.0


def _agente(cfg, nombre: str, mercado=None, llm=None, nueva=True) -> Agente:
    ruta = CARPETA_BD / f"{nombre}.sqlite"
    if nueva and ruta.exists():
        ruta.unlink()
    cfg = dataclasses.replace(cfg, db_path=str(ruta))
    return Agente(cfg, BD(cfg.db_path), mercado or ClienteMEXC(cfg.mexc_url),
                  llm or ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, cfg.ollama_timeout_s),
                  cargar_predictor(cfg.modelo_path))


def _errores(a: Agente) -> list[dict]:
    return a.bd.errores(10)


# ---------------- escenarios ----------------
def e1_mexc(cfg):
    a = _agente(cfg, "01", mercado=ClienteMEXC("https://api.mexc.invalid", timeout_s=3, reintentos=0))
    r = a.ciclo()
    ok = r["resultado"] == "sin datos válidos" and not a.bd.decisiones(5)
    return ok, "Se apuntó el cliente a un dominio inexistente (`api.mexc.invalid`).", r, _errores(a)


def e2_atrasado(cfg):
    a = _agente(dataclasses.replace(cfg, antiguedad_max_h=0.01), "02")
    r = a.ciclo()
    ok = r["resultado"] == "sin datos válidos" and "tiene" in r.get("error", "")
    return ok, "Se bajó ANTIGUEDAD_MAX_H a 0.01 h: la última vela cerrada real de MEXC queda fuera del límite.", r, _errores(a)


def e3_ollama(cfg):
    a = _agente(cfg, "03", llm=ClienteOllama("http://127.0.0.1:9", cfg.ollama_modelo, timeout_s=3))
    r = a.ciclo()
    ok = r.get("accion_final") == "MANTENER" and any(e["etapa"] == "llm" for e in _errores(a))
    return ok, ("El agente apuntó a un puerto local donde no hay Ollama (equivale a Ollama detenido). "
                "También puedes cerrar Ollama y presionar «Revisar vela ahora» en el panel."), r, _errores(a)


def e4_json(cfg):
    real = ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, cfg.ollama_timeout_s)
    a = _agente(cfg, "04", llm=LLMInyectado(real, lambda c: '{"accion": "COMPRAR", "simbolo": '))
    r = a.ciclo()
    ok = r.get("accion_final") == "MANTENER" and any(e["etapa"] == "validacion" for e in _errores(a))
    return ok, "Falla inyectada: se reemplazó la respuesta del LLM por un JSON cortado.", r, _errores(a)


def e5_clave(cfg):
    a = _agente(cfg, "05")
    with TestClient(create_app(cfg, a)) as cli:
        codigo = cli.get("/api/estado", headers={"X-API-Key": "clave-equivocada-123456"}).status_code
        sin = cli.get("/api/estado").status_code
    ok = codigo == 401 and sin == 401 and any(e["etapa"] == "api" for e in _errores(a))
    return ok, "Se consultó la API con una clave equivocada y sin clave.", {"con_clave_equivocada": codigo, "sin_clave": sin}, _errores(a)


def e6_saldo(cfg):
    real = ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, cfg.ollama_timeout_s)
    import json
    compra = lambda c: json.dumps({"accion": "COMPRAR", "simbolo": c["simbolo"], "fecha_vela": c["fecha_vela"],
                                   "justificacion": "Compra forzada para la prueba de saldo."})
    a = _agente(dataclasses.replace(cfg, capital_inicial=0.5), "06", llm=LLMInyectado(real, compra))
    r = a.ciclo()
    ok = r.get("accion_final") == "MANTENER" and not a.bd.ordenes(5) and any(e["etapa"] == "riesgo" for e in _errores(a))
    return ok, "Capital de 0.5 USDT (menor al mínimo de MEXC) y propuesta de compra inyectada.", r, _errores(a)


def e7_duplicado(cfg):
    a = _agente(cfg, "07")
    r1, r2 = a.ciclo(), a.ciclo()
    ok = r2["resultado"] == "vela ya procesada" and len(a.bd.decisiones(5)) == 1
    return ok, "Se ejecutó dos veces el ciclo sobre la misma vela real.", {"primer_ciclo": r1.get("resultado"),
                                                                          "segundo_ciclo": r2["resultado"]}, _errores(a)


def e8_reinicio(cfg):
    a = _agente(cfg, "08")
    a.ciclo()
    b = _agente(cfg, "08", nueva=False)                 # nuevo proceso sobre la misma base
    r = b.ciclo()
    ok = (b.cartera.efectivo, b.cartera.cantidad) == (a.cartera.efectivo, a.cartera.cantidad) \
        and r["resultado"] == "vela ya procesada" and len(b.bd.decisiones(5)) == 1
    return ok, "Se creó un segundo agente sobre la misma base (equivale a reiniciar el backend).", \
        {"cartera_antes": a.cartera.dict(), "cartera_despues": b.cartera.dict(), "ciclo_tras_reinicio": r["resultado"]}, _errores(b)


def e9_detener(cfg):
    a = _agente(dataclasses.replace(cfg, revisar_cada_s=0.5), "09")
    a.iniciar(); time.sleep(1.0)
    a.detener(); a._hilo.join(timeout=cfg.ollama_timeout_s + 30)   # espera a que termine el ciclo en curso
    vivo = a._hilo.is_alive()
    n = len(a.bd.decisiones(5)); time.sleep(1.5)
    ok = a.estado == "DETENIDO" and not vivo and len(a.bd.decisiones(5)) == n
    return ok, "Se inició el bucle y se presionó Detener (mismo método que el botón del panel).", \
        {"estado": a.estado, "hilo_activo": vivo, "decisiones": n}, _errores(a)


ESCENARIOS = {1: ("mexc_sin_respuesta", "API de MEXC sin respuesta", e1_mexc),
              2: ("dato_atrasado", "Dato atrasado", e2_atrasado),
              3: ("ollama_detenido", "Ollama detenido", e3_ollama),
              4: ("json_invalido", "JSON inválido del LLM", e4_json),
              5: ("clave_incorrecta", "Clave incorrecta", e5_clave),
              6: ("saldo_insuficiente", "Saldo insuficiente", e6_saldo),
              7: ("evento_duplicado", "Evento duplicado", e7_duplicado),
              8: ("reinicio_backend", "Reinicio del backend", e8_reinicio),
              9: ("boton_detener", "Botón de detener", e9_detener)}


def _md(n, titulo, ok, como, resultado, errores) -> str:
    filas = "\n".join(f"| {e['creado']} | {e['etapa']} | {e['tipo']} | {e['mensaje'][:160]} |" for e in errores) \
        or "| — | — | — | sin registros |"
    return (f"# Error {n}: {titulo}\n\n**Resultado:** {'✔ comportamiento correcto' if ok else '✘ revisar'}\n\n"
            f"**Cómo se provocó:** {como}\n\n**Respuesta del agente:**\n\n```\n{resultado}\n```\n\n"
            f"**Registros en la tabla de errores:**\n\n| Hora (UTC) | Etapa | Tipo | Mensaje |\n|---|---|---|---|\n{filas}\n\n"
            f"_Generado el {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC con `python -m app.provocar {n}`._\n")


def correr(numeros: list[int]) -> list[tuple[int, str, bool]]:
    cfg = cargar()
    CARPETA_BD.mkdir(parents=True, exist_ok=True); CARPETA_DOCS.mkdir(parents=True, exist_ok=True)
    salida = []
    for n in numeros:
        clave, titulo, fn = ESCENARIOS[n]
        try:
            ok, como, res, errs = fn(cfg)
        except Exception as e:                                # el escenario mismo falló: se reporta
            ok, como, res, errs = False, "El escenario no pudo completarse.", f"{type(e).__name__}: {e}", []
        (CARPETA_DOCS / f"{n:02d}_{clave}.md").write_text(_md(n, titulo, ok, como, res, errs), encoding="utf-8")
        print(f"[{'✔' if ok else '✘'}] {n}. {titulo}")
        salida.append((n, titulo, ok))
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description="Provoca los errores del protocolo y guarda la evidencia.")
    ap.add_argument("escenario", help="'todos' o un número del 1 al 9")
    a = ap.parse_args()
    numeros = list(ESCENARIOS) if a.escenario == "todos" else [int(a.escenario)]
    res = correr(numeros)
    if a.escenario == "todos":
        lineas = ["# Errores provocados: resumen", "", "| # | Error | Resultado | Evidencia |", "|---|---|---|---|"]
        lineas += [f"| {n} | {t} | {'✔' if ok else '✘ revisar'} | [{n:02d}_{ESCENARIOS[n][0]}.md]({n:02d}_{ESCENARIOS[n][0]}.md) |"
                   for n, t, ok in res]
        (CARPETA_DOCS / "resumen.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    if all(ok for *_, ok in res):
        shutil.rmtree(CARPETA_BD, ignore_errors=True)        # las bases temporales solo se conservan si algo falló
    else:
        print("\nAlgún escenario no se comportó como se esperaba: revisa su archivo en docs/errores/.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
