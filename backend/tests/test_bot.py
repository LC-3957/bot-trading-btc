import json

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Config, ConfigError
from app.db import BD
from app.llm import PropuestaInvalida, construir_prompt, validar_propuesta
from app.main import create_app
from app.mexc import ClienteMEXC, DatoAtrasadoError, MercadoError, ReglasPar, separar_velas
from app.modelo import cargar_predictor, variables
from app.paper import Cartera, SaldoInsuficienteError, ejecutar, revisar_riesgo

from conftest import AHORA, CLAVE, DIA, crear_agente, transporte_mexc, transporte_ollama


# ---------- configuración ----------
def test_rechaza_modo_real(cfg):
    with pytest.raises(ConfigError, match="PAPER"):
        Config(modo="REAL", api_key=CLAVE).validar()


def test_rechaza_ollama_remoto():
    with pytest.raises(ConfigError, match="local"):
        Config(api_key=CLAVE, ollama_url="https://api.ejemplo.com").validar()


def test_rechaza_clave_corta():
    with pytest.raises(ConfigError, match="BOT_API_KEY"):
        Config(api_key="corta").validar()


# ---------- datos de mercado ----------
def test_mexc_limite_de_solicitudes():
    c = ClienteMEXC("https://api.mexc.com", transport=transporte_mexc(estado=429), reintentos=0)
    with pytest.raises(MercadoError, match="429"):
        c.velas("BTCUSDT")


def test_mexc_sin_respuesta():
    def caido(req):
        raise httpx.ConnectTimeout("timeout")
    c = ClienteMEXC("https://api.mexc.com", transport=httpx.MockTransport(caido), reintentos=0)
    with pytest.raises(MercadoError, match="sin respuesta"):
        c.velas("BTCUSDT")


def test_dato_atrasado():
    c = ClienteMEXC("https://api.mexc.com", transport=transporte_mexc(), reintentos=0)
    velas = c.velas("BTCUSDT")
    with pytest.raises(DatoAtrasadoError):
        separar_velas(velas, AHORA + 5 * DIA, antiguedad_max_h=26)


def test_separa_vela_en_curso():
    c = ClienteMEXC("https://api.mexc.com", transport=transporte_mexc(), reintentos=0)
    cerradas, en_curso = separar_velas(c.velas("BTCUSDT"), AHORA, 26)
    assert en_curso is not None and all(v.cierre_ms < AHORA for v in cerradas)


# ---------- LLM ----------
def test_json_invalido():
    with pytest.raises(PropuestaInvalida, match="JSON"):
        validar_propuesta("esto no es json", "BTCUSDT", "2025-11-16")


def test_propuesta_de_otra_vela():
    t = json.dumps({"accion": "COMPRAR", "simbolo": "BTCUSDT", "fecha_vela": "2020-01-01", "justificacion": "texto ok"})
    with pytest.raises(PropuestaInvalida, match="otra vela"):
        validar_propuesta(t, "BTCUSDT", "2025-11-16")


def test_accion_fuera_de_catalogo():
    t = json.dumps({"accion": "APALANCAR", "simbolo": "BTCUSDT", "fecha_vela": "2025-11-16", "justificacion": "texto ok"})
    with pytest.raises(PropuestaInvalida):
        validar_propuesta(t, "BTCUSDT", "2025-11-16")


def test_prompt_sin_secretos(cfg):
    registro = []
    a = crear_agente(cfg, ollama=transporte_ollama(registro=registro))
    a.iniciar(); a.ciclo(); a.detener()
    enviado = json.dumps(registro)
    assert registro and CLAVE not in enviado and "api_key" not in enviado.lower()
    with pytest.raises(ValueError):
        construir_prompt({"simbolo": "BTCUSDT", "api_key": CLAVE})


# ---------- Paper y riesgo ----------
def test_compra_y_venta(cfg):
    c = Cartera(efectivo=50_000)
    r = ejecutar("COMPRAR", c, 100_000.0, ReglasPar(6, 2, 1.0), cfg)
    assert r.aprobada and c.posicion == 1 and c.efectivo >= 0
    assert round(r.cantidad, 6) == r.cantidad                          # precisión del par
    assert r.precio == pytest.approx(100_000 * 1.0005)                 # deslizamiento
    r2 = ejecutar("VENDER", c, 100_000.0, ReglasPar(), cfg)
    assert r2.aprobada and c.posicion == 0


def test_sin_cortos_ni_doble_compra(cfg):
    c = Cartera(efectivo=50_000)
    assert ejecutar("VENDER", c, 100_000.0, ReglasPar(), cfg).accion_final == "MANTENER"
    ejecutar("COMPRAR", c, 100_000.0, ReglasPar(), cfg)
    r = ejecutar("COMPRAR", c, 100_000.0, ReglasPar(), cfg)
    assert not r.aprobada and "posición abierta" in r.motivo


def test_saldo_insuficiente(cfg):
    with pytest.raises(SaldoInsuficienteError):
        ejecutar("COMPRAR", Cartera(efectivo=0.5), 100_000.0, ReglasPar(6, 2, 1.0), cfg)


def test_perdida_diaria_bloquea_compras(cfg):
    c = Cartera(efectivo=40_000, patrimonio_inicio_dia=50_000)
    ok, motivo = revisar_riesgo("COMPRAR", c, 100_000.0, cfg)
    assert not ok and "pérdida diaria" in motivo


# ---------- ciclo completo ----------
def test_ciclo_compra_y_no_duplica(cfg):
    a = crear_agente(cfg)
    a.iniciar()
    r1 = a.ciclo(); r2 = a.ciclo()
    a.detener()
    assert r1["resultado"] == "decision registrada" and r1["accion_final"] == "COMPRAR"
    assert r2["resultado"] == "vela ya procesada"
    assert len(a.bd.ordenes()) == 1 and len(a.bd.decisiones()) == 1


def test_ollama_detenido_mantiene(cfg):
    a = crear_agente(cfg, ollama=transporte_ollama(caido=True))
    r = a.ciclo()
    assert r["accion_final"] == "MANTENER" and not r["aprobada"]
    assert any(e["etapa"] == "llm" for e in a.bd.errores())


def test_json_invalido_en_ciclo(cfg):
    a = crear_agente(cfg, ollama=transporte_ollama(contenido="{mal"))
    r = a.ciclo()
    assert r["accion_final"] == "MANTENER" and any(e["etapa"] == "validacion" for e in a.bd.errores())


def test_reinicio_recupera_estado(cfg):
    a = crear_agente(cfg); a.ciclo()
    efectivo, cantidad = a.cartera.efectivo, a.cartera.cantidad
    b = crear_agente(cfg, bd=BD(cfg.db_path))                          # "reinicio" del backend
    assert (b.cartera.efectivo, b.cartera.cantidad) == (efectivo, cantidad)
    assert b.ciclo()["resultado"] == "vela ya procesada" and len(b.bd.ordenes()) == 1


def test_detener_para_el_hilo(cfg):
    a = crear_agente(cfg)
    a.iniciar(); assert a.estado == "CORRIENDO"
    a.pausar(); assert a.estado == "PAUSADO"
    a.detener(); a._hilo.join(timeout=2)
    assert a.estado == "DETENIDO" and not a._hilo.is_alive()


# ---------- modelo ----------
def test_predictor_numpy(tmp_path):
    rng = np.random.default_rng(0)
    W1, b1 = rng.normal(size=(4, 20)), rng.normal(size=4)
    W2, b2 = rng.normal(size=(4, 4)), rng.normal(size=4)
    W3, b3 = rng.normal(size=(1, 4)), rng.normal(size=1)
    d = {"nombre": "MLP4", "capas": [{"W": W.tolist(), "b": b.tolist()} for W, b in [(W1, b1), (W2, b2), (W3, b3)]],
         "escalador": {"media": [0.0] * 20, "escala": [1.0] * 20}, "objetivo": {"media": 0.001, "desv": 0.03}}
    p = tmp_path / "m.json"; p.write_text(json.dumps(d))
    x = rng.normal(size=20)
    manual = (np.maximum(np.maximum(x @ W1.T + b1, 0) @ W2.T + b2, 0) @ W3.T + b3)[0] * 0.03 + 0.001
    assert cargar_predictor(str(p)).predecir(x.tolist()) == pytest.approx(manual)
    assert not cargar_predictor(str(tmp_path / "nada.json")).cargado


def test_variables_orden_rezagos():
    v = variables([100 + i for i in range(30)])
    assert v["lags"][0] == pytest.approx(129 / 128 - 1)                # lag_0 = rendimiento más reciente


# ---------- API ----------
def test_api_clave(cfg):
    cli = TestClient(create_app(cfg, crear_agente(cfg)))
    assert cli.get("/api/salud").status_code == 200
    assert cli.get("/api/estado").status_code == 401
    assert cli.get("/api/estado", headers={"X-API-Key": "otra-clave-incorrecta"}).status_code == 401
    h = {"X-API-Key": CLAVE}
    assert cli.post("/api/ciclo", headers=h).status_code == 409        # detenido
    assert cli.post("/api/control/iniciar", headers=h).json()["estado"] == "CORRIENDO"
    assert cli.get("/api/estado", headers=h).json()["modo"] == "PAPER"
    assert cli.post("/api/control/detener", headers=h).json()["estado"] == "DETENIDO"
