"""Pruebas del diagnóstico del LLM local y del informe automático."""
from pathlib import Path

from app.diagnostico import a_markdown, hardware, probar_llm
from app.informe import generar
from app.llm import ClienteOllama
from app.mexc import ClienteMEXC
from app.modelo import Predictor
from app.replay import correr
from app.db import BD

from conftest import transporte_mexc, transporte_ollama


def test_diagnostico_registra_hardware_y_llm(cfg):
    hw = hardware()
    assert {"Sistema operativo", "Procesador", "RAM", "GPU"} <= set(hw)
    llm = probar_llm(cfg, ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, transport=transporte_ollama()))
    assert llm["URL local"] == "sí" and llm["Versión de Ollama"] == "0.9.0"
    assert llm["Propuesta de prueba"].startswith("válida")
    assert "Tiempo de respuesta" in a_markdown(hw, llm)


def test_diagnostico_con_ollama_apagado(cfg):
    llm = probar_llm(cfg, ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, transport=transporte_ollama(caido=True)))
    assert llm["Versión de Ollama"].startswith("sin respuesta")


def test_informe_con_replay(cfg, tmp_path):
    bd = BD(cfg.db_path)
    correr(cfg, ClienteMEXC(cfg.mexc_url, transport=transporte_mexc(), reintentos=0),
           ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, transport=transporte_ollama()),
           Predictor(nombre="cero"), bd, desde="2025-10-01", ciclos=22, aviso=lambda *_: None)
    (tmp_path / "capturas").mkdir()
    (tmp_path / "capturas" / "03_ollama_detenido.png").write_bytes(b"x")
    (tmp_path / "pruebas_automaticas.txt").write_text("==== 35 passed, 1 warning in 3.1s ====")
    texto = generar(cfg, bd, tmp_path)
    assert "Se alcanzan los 20 ciclos válidos" in texto and "| Replay | 22 |" in texto
    assert "captura 03_ollama_detenido.png" in texto and "35 passed" in texto
    assert "| Agente con LLM |" in texto and "pendiente (ejecuta `python -m app.validar`)" in texto


def test_informe_sin_datos(cfg, tmp_path):
    texto = generar(cfg, BD(cfg.db_path), tmp_path)
    assert "Aún no se alcanzan los 20 ciclos" in texto and "Todavía no hay ciclos" in texto


def test_provocar_los_nueve_errores(cfg, tmp_path, monkeypatch):
    import httpx
    import app.provocar as pv
    from conftest import AHORA

    class MEXCPrueba(ClienteMEXC):
        def __init__(self, base, timeout_s=10.0, reintentos=2, transport=None):
            falla = httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("dns")))
            super().__init__(base, timeout_s, 0, transport=falla if "invalid" in base else transporte_mexc())

    class OllamaPrueba(ClienteOllama):
        def __init__(self, url, modelo, timeout_s=120.0, transport=None):
            super().__init__(url, modelo, timeout_s, transport=transporte_ollama(caido=url.endswith(":9")))

    class AgenteReloj(pv.Agente):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); self.reloj_ms = lambda: AHORA

    monkeypatch.setattr(pv, "ClienteMEXC", MEXCPrueba)
    monkeypatch.setattr(pv, "ClienteOllama", OllamaPrueba)
    monkeypatch.setattr(pv, "Agente", AgenteReloj)
    monkeypatch.setattr(pv, "cargar", lambda: cfg)
    monkeypatch.setattr(pv, "CARPETA_BD", tmp_path / "bd")
    monkeypatch.setattr(pv, "CARPETA_DOCS", tmp_path / "docs")
    res = pv.correr(list(range(1, 10)))
    assert [ok for *_, ok in res] == [True] * 9, res
    assert len(list((tmp_path / "docs").glob("0*_*.md"))) == 9
