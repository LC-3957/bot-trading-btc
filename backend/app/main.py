"""API del bot (FastAPI). Documentación interactiva en /docs.

Arranque: uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

Todas las rutas, salvo /api/salud, exigen el encabezado X-API-Key con BOT_API_KEY.
La clave vive solo en el servidor (.env) y nunca se envía al LLM.
"""
from __future__ import annotations

import secrets

from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import __version__
from .agente import Agente
from .comparacion import comparar
from .config import Config, cargar
from .db import BD, EXPORTABLES
from .llm import ClienteOllama, OllamaError
from .mexc import ClienteMEXC
from .modelo import cargar_predictor

Origen = Literal["vivo", "replay"]


def construir_agente(cfg: Config) -> Agente:
    return Agente(cfg, BD(cfg.db_path), ClienteMEXC(cfg.mexc_url),
                  ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, cfg.ollama_timeout_s),
                  cargar_predictor(cfg.modelo_path))


def create_app(cfg: Config | None = None, agente: Agente | None = None) -> FastAPI:
    cfg = cfg or cargar()
    agente = agente or construir_agente(cfg)
    app = FastAPI(title="Bot de trading BTC/USDT con LLM local", version=__version__,
                  description="Agente académico en modo Paper: MEXC (datos públicos) + MLP + Ollama local.")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["GET", "POST"], allow_headers=["X-API-Key", "Content-Type"])
    app.state.agente = agente

    def verificar_clave(x_api_key: str = Header(default="")) -> None:
        if not secrets.compare_digest(x_api_key.encode(), cfg.api_key.encode()):
            agente.bd.error("api", "Clave incorrecta o ausente en X-API-Key")
            raise HTTPException(status_code=401, detail="Clave incorrecta")

    auth = [Depends(verificar_clave)]

    @app.get("/api/salud")
    def salud():
        return {"ok": True, "version": __version__, "modo": cfg.modo}

    @app.get("/api/estado", dependencies=auth)
    def estado():
        return agente.resumen()

    @app.post("/api/control/{accion}", dependencies=auth)
    def control(accion: str):
        acciones = {"iniciar": agente.iniciar, "pausar": agente.pausar, "detener": agente.detener}
        if accion not in acciones:
            raise HTTPException(status_code=400, detail=f"Acción no válida: {accion}")
        return {"estado": acciones[accion]()}

    @app.post("/api/ciclo", dependencies=auth)
    def ciclo():
        if agente.estado == "DETENIDO":
            raise HTTPException(status_code=409, detail="El bot está detenido: inícialo antes de ejecutar un ciclo.")
        return agente.ciclo()

    @app.get("/api/llm", dependencies=auth)
    def llm():
        try:
            return agente.llm.info()
        except OllamaError as e:
            agente.bd.error("llm", e)
            raise HTTPException(status_code=503, detail=str(e))

    @app.get("/api/decisiones", dependencies=auth)
    def decisiones(n: int = Query(30, ge=1, le=500), origen: Origen = "vivo"):
        return agente.bd.decisiones(n, origen)

    @app.get("/api/ordenes", dependencies=auth)
    def ordenes(n: int = Query(30, ge=1, le=500), origen: Origen = "vivo"):
        return agente.bd.ordenes(n, origen)

    @app.get("/api/errores", dependencies=auth)
    def errores(n: int = Query(30, ge=1, le=500), origen: Origen = "vivo"):
        return agente.bd.errores(n, origen)

    @app.get("/api/patrimonio", dependencies=auth)
    def patrimonio(n: int = Query(365, ge=1, le=5000), origen: Origen = "vivo"):
        return agente.bd.curva_patrimonio(n, origen)

    @app.get("/api/metricas", dependencies=auth)
    def metricas(origen: Origen = "vivo"):
        return agente.bd.metricas(origen)

    @app.get("/api/comparacion", dependencies=auth)
    def comparacion(origen: Origen = "vivo"):
        return comparar(agente.bd.decisiones_cronologicas(origen), cfg)

    @app.get("/api/grafica", dependencies=auth)
    def grafica(origen: Origen = "vivo", n: int = Query(120, ge=10, le=1000)):
        """Velas guardadas y las órdenes de ese origen, para dibujar precio con marcas de compra y venta."""
        return {"velas": agente.bd.velas_guardadas(cfg.simbolo, n), "ordenes": agente.bd.ordenes(1000, origen)}

    @app.get("/api/exportar/{tabla}", dependencies=auth, response_class=PlainTextResponse)
    def exportar(tabla: str, origen: Origen = "vivo"):
        if tabla not in EXPORTABLES:
            raise HTTPException(status_code=404, detail=f"Tabla no exportable: {tabla}")
        return PlainTextResponse(agente.bd.exportar_csv(tabla, origen), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{tabla}_{origen}.csv"'})

    return app
