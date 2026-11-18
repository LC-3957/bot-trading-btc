import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agente import Agente  # noqa: E402
from app.config import Config  # noqa: E402
from app.db import BD  # noqa: E402
from app.llm import ClienteOllama  # noqa: E402
from app.mexc import ClienteMEXC  # noqa: E402
from app.modelo import Predictor  # noqa: E402

DIA = 86_400_000
AHORA = 1_763_380_800_000 + 15 * 3_600_000          # 2025-11-18 03:00 UTC (reloj fijo)
CLAVE = "clave-de-prueba-123456"


def velas_mexc(n=60, ahora=AHORA):
    hoy = ahora - ahora % DIA
    filas, precio = [], 90_000.0
    for i in range(n, -1, -1):                      # n velas cerradas + la vela en curso
        ap = hoy - i * DIA
        o, c = precio, precio * (1.01 if i % 3 else 0.995)
        filas.append([ap, f"{o:.2f}", f"{max(o, c) * 1.002:.2f}", f"{min(o, c) * 0.998:.2f}", f"{c:.2f}", "123.4", ap + DIA - 1, "1"])
        precio = c
    return filas


def transporte_mexc(estado=200, cuerpo=None):
    def h(req: httpx.Request):
        if req.url.path.endswith("/klines"):
            return httpx.Response(estado, json=cuerpo if cuerpo is not None else velas_mexc())
        if req.url.path.endswith("/exchangeInfo"):
            return httpx.Response(200, json={"symbols": [{"symbol": "BTCUSDT", "baseAssetPrecision": 6,
                                                          "quotePrecision": 2, "quoteAmountPrecision": "1"}]})
        return httpx.Response(404)
    return httpx.MockTransport(h)


def transporte_ollama(contenido=None, caido=False, registro=None):
    def h(req: httpx.Request):
        if caido:
            raise httpx.ConnectError("conexión rechazada")
        if req.url.path == "/api/chat":
            cuerpo = json.loads(req.content)
            if registro is not None:
                registro.append(cuerpo)
            fecha = json.loads(cuerpo["messages"][1]["content"].split("\n", 1)[1])["fecha_vela"]
            txt = contenido if contenido is not None else json.dumps(
                {"accion": "COMPRAR", "simbolo": "BTCUSDT", "fecha_vela": fecha, "justificacion": "Pronóstico positivo."})
            return httpx.Response(200, json={"message": {"content": txt}})
        if req.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.9.0"})
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        return httpx.Response(404)
    return httpx.MockTransport(h)


@pytest.fixture
def cfg(tmp_path):
    return Config(modo="PAPER", api_key=CLAVE, db_path=str(tmp_path / "bot.sqlite"),
                  modelo_path=str(tmp_path / "no_existe.json"), costo=0.0, deslizamiento=0.0005,
                  revisar_cada_s=0.05).validar()


def crear_agente(cfg, ollama=None, mexc=None, bd=None):
    return Agente(cfg, bd or BD(cfg.db_path), ClienteMEXC(cfg.mexc_url, transport=mexc or transporte_mexc(), reintentos=0),
                  ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, transport=ollama or transporte_ollama()),
                  Predictor(nombre="Pronóstico cero"), reloj_ms=lambda: AHORA)
