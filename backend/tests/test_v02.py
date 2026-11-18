"""Pruebas de la v0.2: comparación del protocolo, modo replay, métricas y exportación."""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.comparacion import a_markdown, comparar
from app.db import BD
from app.llm import ClienteOllama
from app.main import create_app
from app.mexc import ClienteMEXC, ReglasPar
from app.modelo import Predictor
from app.replay import correr

from conftest import CLAVE, crear_agente, transporte_mexc, transporte_ollama


def decision(fecha, precio, pron, accion, aprobada=1, latencia=2.0, propuesta="COMPRAR"):
    return dict(fecha_vela=fecha, precio_ejecucion=precio, pronostico=pron, accion_final=accion,
                aprobada=aprobada, latencia_s=latencia, accion_propuesta=propuesta)


DECISIONES = [decision("2026-01-01", 100.0, 0.01, "COMPRAR"),
              decision("2026-01-02", 110.0, -0.01, "MANTENER", propuesta=None, aprobada=0),
              decision("2026-01-03", 121.0, 0.01, "MANTENER")]


def test_comprar_y_mantener_a_mano(cfg):
    res = comparar(DECISIONES, cfg, umbral=0.0)
    bh = res["estrategias"][0]
    esperado = 121 * (1 - cfg.deslizamiento) / (100 * (1 + cfg.deslizamiento)) - 1
    assert bh["rendimiento_neto"] == pytest.approx(esperado, rel=1e-4)
    assert bh["operaciones"] == 2 and bh["win_rate"] == 1.0


def test_modelo_sin_llm_sigue_el_pronostico(cfg):
    modelo = comparar(DECISIONES, cfg, umbral=0.0)["estrategias"][1]
    assert modelo["operaciones"] == 4                                   # compra, venta, compra, liquidación
    assert modelo["operaciones_cerradas"] == 2


def test_agente_sigue_acciones_finales_y_reporta_rechazos(cfg):
    agente = comparar(DECISIONES, cfg, umbral=0.0)["estrategias"][2]
    bh = comparar(DECISIONES, cfg, umbral=0.0)["estrategias"][0]
    assert agente["rendimiento_neto"] == pytest.approx(bh["rendimiento_neto"])
    assert agente["rechazadas"] == 1 and agente["propuestas_invalidas"] == 1
    assert agente["latencia_media_s"] == pytest.approx(2.0)
    assert "| Agente con LLM |" in a_markdown(comparar(DECISIONES, cfg), "replay")


def test_comparacion_sin_ciclos(cfg):
    assert comparar([], cfg)["ciclos"] == 0


def test_replay_marca_origen_y_no_toca_vivo(cfg):
    bd = BD(cfg.db_path)
    vivo = crear_agente(cfg, bd=bd)
    vivo.ciclo()                                                        # un ciclo en vivo
    res = correr(cfg, ClienteMEXC(cfg.mexc_url, transport=transporte_mexc(), reintentos=0),
                 ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, transport=transporte_ollama()),
                 Predictor(nombre="cero"), bd, desde="2025-10-01", ciclos=20, aviso=lambda *_: None)
    assert res["ciclos"] == 20 and len(res["estrategias"]) == 3
    assert bd.metricas("replay")["ciclos"] == 20
    assert bd.metricas("vivo")["ciclos"] == 1                           # el replay no mezcla datos
    fechas = [d["fecha_vela"] for d in bd.decisiones_cronologicas("replay")]
    assert fechas == sorted(set(fechas))                                # una decisión por vela, en orden
    precios = [d["precio_ejecucion"] for d in bd.decisiones_cronologicas("replay")]
    assert all(p > 0 for p in precios)


def test_replay_se_puede_repetir(cfg):
    bd = BD(cfg.db_path)
    args = dict(desde="2025-10-01", ciclos=5, aviso=lambda *_: None)
    for _ in range(2):
        correr(cfg, ClienteMEXC(cfg.mexc_url, transport=transporte_mexc(), reintentos=0),
               ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, transport=transporte_ollama()),
               Predictor(nombre="cero"), bd, **args)
    assert bd.metricas("replay")["ciclos"] == 5


def test_metricas_y_exportacion(cfg):
    a = crear_agente(cfg, ollama=transporte_ollama(contenido="{roto"))
    a.ciclo()
    m = a.bd.metricas("vivo")
    assert m["ciclos"] == 1 and m["sin_propuesta_valida"] == 1 and m["pct_rechazadas"] == 1.0
    filas = list(csv.reader(io.StringIO(a.bd.exportar_csv("decisiones", "vivo"))))
    assert filas[0][:3] == ["id", "origen", "simbolo"] and len(filas) == 2


def test_endpoints_v02(cfg):
    a = crear_agente(cfg)
    a.ciclo()
    cli = TestClient(create_app(cfg, a))
    h = {"X-API-Key": CLAVE}
    assert cli.get("/api/metricas", headers=h).json()["ciclos"] == 1
    assert cli.get("/api/comparacion", headers=h).json()["ciclos"] == 1
    g = cli.get("/api/grafica", headers=h).json()
    assert g["velas"] and g["ordenes"][0]["accion"] == "COMPRAR"
    r = cli.get("/api/exportar/ordenes?origen=vivo", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert cli.get("/api/exportar/estado", headers=h).status_code == 404
    assert cli.get("/api/decisiones?origen=otro", headers=h).status_code == 422
    assert cli.get("/api/metricas").status_code == 401


def test_validacion_con_mexc():
    from app.validar import a_markdown, evaluar
    cierres = [90000 * (1.002 ** i) * (1.01 if i % 2 else 0.995) for i in range(80)]
    fechas = [f"2026-01-{(i % 28) + 1:02d}" for i in range(80)]
    r = evaluar(cierres, fechas, Predictor(nombre="cero"))
    assert r["n"] == 80 - 20 - 1 and r["rmse_modelo"] == pytest.approx(r["rmse_cero"])
    assert "| RMSE |" in a_markdown(r, "BTCUSDT")
