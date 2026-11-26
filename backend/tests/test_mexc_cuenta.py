"""Conexión con la cuenta spot de MEXC: firma, órdenes de prueba y que nunca haya órdenes reales."""
import hashlib
import hmac
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.mexc_cuenta import ClienteCuentaMEXC, CuentaError, firmar

from conftest import CLAVE, crear_agente, transporte_ollama

KEY, SECRET = "mx0vglABCDEFGH123456", "secreto-de-prueba-0123456789"


def mexc_privado(registro, estado=200, cuerpo=None, hora_servidor=1_700_000_000_000):
    def h(req: httpx.Request):
        if req.url.path == "/api/v3/time":                   # pública, no se registra
            return httpx.Response(200, json={"serverTime": hora_servidor})
        registro.append(req)
        if req.url.path == "/api/v3/account":
            return httpx.Response(estado, json=cuerpo or {"canTrade": True, "permissions": ["SPOT"],
                                                          "balances": [{"asset": "USDT", "free": "12.5", "locked": "0"},
                                                                       {"asset": "BTC", "free": "0", "locked": "0"}]})
        if req.url.path == "/api/v3/order/test":
            return httpx.Response(estado, json=cuerpo if cuerpo is not None else {})
        return httpx.Response(404, json={"code": 404, "msg": "ruta no permitida en pruebas"})
    return httpx.MockTransport(h)


def cliente(registro, reloj=1_700_000_000_000, **kw):
    return ClienteCuentaMEXC("https://api.mexc.com", KEY, SECRET, transport=mexc_privado(registro, **kw),
                             reloj_ms=lambda: reloj)


def test_firma_hmac_y_cabecera():
    reg = []
    cliente(reg).cuenta()
    req = reg[0]
    q = req.url.query.decode()
    consulta, firma = q.rsplit("&signature=", 1)
    assert firma == hmac.new(SECRET.encode(), consulta.encode(), hashlib.sha256).hexdigest() == firmar(SECRET, consulta)
    assert req.headers["X-MEXC-APIKEY"] == KEY and "timestamp=1700000000000" in consulta
    assert SECRET not in str(req.url)


def test_lee_saldos_y_permisos():
    d = cliente([]).cuenta()
    assert d["puede_operar"] and d["saldos"] == [{"activo": "USDT", "libre": 12.5, "bloqueado": 0.0}]


def test_orden_de_prueba_compra_y_venta():
    reg = []
    c = cliente(reg)
    c.orden_prueba("BTCUSDT", "COMPRAR", 0.1, 5000.0, 6)
    c.orden_prueba("BTCUSDT", "VENDER", 0.123456789, 0, 6)
    compra, venta = (dict(parse_qsl(r.url.query.decode())) for r in reg)
    assert all(r.method == "POST" and r.url.path == "/api/v3/order/test" for r in reg)
    assert compra["side"] == "BUY" and compra["quoteOrderQty"] == "5000.00" and compra["type"] == "MARKET"
    assert venta["side"] == "SELL" and venta["quantity"] == "0.123457"


def test_error_de_mexc_se_reporta():
    with pytest.raises(CuentaError, match="Invalid api key"):
        cliente([], estado=401, cuerpo={"code": 10072, "msg": "Invalid api key"}).cuenta()


def test_el_codigo_no_tiene_ordenes_reales():
    fuente = Path(__file__).resolve().parents[1].joinpath("app", "mexc_cuenta.py").read_text(encoding="utf-8")
    rutas = {l.split("=")[1].strip().strip('"') for l in fuente.splitlines() if l.startswith("RUTA_")}
    assert rutas == {"/api/v3/account", "/api/v3/order/test", "/api/v3/time"}


def test_agente_envia_orden_de_prueba_y_la_registra(cfg):
    reg = []
    a = crear_agente(cfg)
    a.cuenta = cliente(reg)
    r = a.ciclo()
    assert r["accion_final"] == "COMPRAR" and r["mexc_prueba"].startswith("aceptada por MEXC")
    assert a.bd.ordenes(5)[0]["mexc_prueba"].startswith("aceptada por MEXC")
    assert reg[0].url.path == "/api/v3/order/test"


def test_rechazo_de_mexc_no_rompe_el_simulador(cfg):
    a = crear_agente(cfg)
    a.cuenta = cliente([], estado=400, cuerpo={"code": 30004, "msg": "Insufficient position"})
    r = a.ciclo()
    assert r["accion_final"] == "COMPRAR" and a.cartera.posicion == 1      # el Paper sigue igual
    assert "rechazada por MEXC" in r["mexc_prueba"]
    assert any(e["etapa"] == "mexc_prueba" for e in a.bd.errores())


def test_secretos_de_mexc_no_llegan_al_llm(cfg):
    capturado = []
    a = crear_agente(cfg, ollama=transporte_ollama(registro=capturado))
    a.cuenta = cliente([])
    a.ciclo()
    enviado = json.dumps(capturado)
    assert KEY not in enviado and SECRET not in enviado


def test_endpoint_mexc_enmascara_la_clave(cfg):
    a = crear_agente(cfg)
    h = {"X-API-Key": CLAVE}
    assert TestClient(create_app(cfg, a)).get("/api/mexc", headers=h).json()["configurada"] is False
    a.cuenta = cliente([])
    d = TestClient(create_app(cfg, a)).get("/api/mexc", headers=h).json()
    assert d["conectada"] and d["clave"] == "mx0v…3456" and KEY not in json.dumps(d) and SECRET not in json.dumps(d)


def test_config_no_muestra_secretos(cfg):
    from dataclasses import replace
    c = replace(cfg, mexc_api_key=KEY, mexc_api_secret=SECRET)
    assert KEY not in repr(c) and SECRET not in repr(c) and CLAVE not in repr(c)


def test_corrige_el_reloj_desfasado_de_la_compu():
    reg = []
    cliente(reg, reloj=1_700_000_000_000 - 40_000).cuenta()      # la compu va 40 s atrasada
    assert "timestamp=1700000000000" in reg[0].url.query.decode()


def test_reintenta_si_mexc_rechaza_por_recvwindow():
    llamadas = {"n": 0}

    def h(req):
        if req.url.path == "/api/v3/time":
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return httpx.Response(400, json={"code": 700003, "msg": "Timestamp for this request is outside of the recvWindow."})
        return httpx.Response(200, json={"canTrade": True, "permissions": ["SPOT"], "balances": []})

    c = ClienteCuentaMEXC("https://api.mexc.com", KEY, SECRET, transport=httpx.MockTransport(h),
                          reloj_ms=lambda: 1_700_000_000_000)
    assert c.cuenta()["puede_operar"] and llamadas["n"] == 2