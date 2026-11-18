"""Ciclo del agente: datos → variables → pronóstico → propuesta del LLM → validación → riesgo → Paper → registro.

Frecuencia diaria: el bot revisa cada REVISAR_CADA_S segundos si ya cerró una vela nueva y
decide una sola vez por vela. La señal de la vela cerrada en t se ejecuta al precio de
apertura de la vela en curso (t+1), con deslizamiento.
"""
from __future__ import annotations

import copy
import threading
import time
from typing import Callable

from . import __version__
from .db import BD, ahora
from .llm import ClienteOllama, OllamaError, PropuestaInvalida, validar_propuesta
from .mexc import ClienteMEXC, DatoAtrasadoError, MercadoError, ReglasPar, separar_velas
from .modelo import ModeloError, Predictor, variables
from .paper import Cartera, Resultado, SaldoInsuficienteError, ejecutar

ESTADOS = ("DETENIDO", "CORRIENDO", "PAUSADO")


class Agente:
    def __init__(self, cfg, bd: BD, mercado: ClienteMEXC, llm: ClienteOllama, predictor: Predictor,
                 reloj_ms: Callable[[], int] = lambda: int(time.time() * 1000), origen: str = "vivo"):
        self.cfg, self.bd, self.mercado, self.llm, self.predictor = cfg, bd, mercado, llm, predictor
        self.reloj_ms = reloj_ms
        self.origen = origen                                 # "vivo" o "replay": separa la evidencia en la BD
        self.estado = "DETENIDO"
        self._hilo: threading.Thread | None = None
        self._parar = threading.Event()
        self._lock = threading.Lock()
        self._reglas: ReglasPar | None = None
        self.ultimo: dict | None = None
        guardada = bd.leer_estado(f"cartera_{origen}")       # recuperar tras reinicio
        self.cartera = Cartera(**{k: v for k, v in guardada.items() if k != "posicion"}) if guardada \
            else Cartera(efectivo=cfg.capital_inicial)

    # ---------- control ----------
    def iniciar(self) -> str:
        with self._lock:
            if self.estado == "CORRIENDO":
                return self.estado
            self.estado = "CORRIENDO"
            if self._hilo is None or not self._hilo.is_alive():
                self._parar.clear()
                self._hilo = threading.Thread(target=self._bucle, daemon=True, name="agente")
                self._hilo.start()
        return self.estado

    def pausar(self) -> str:
        with self._lock:
            if self.estado == "CORRIENDO":
                self.estado = "PAUSADO"
        return self.estado

    def detener(self) -> str:
        with self._lock:
            self.estado = "DETENIDO"
            self._parar.set()
        return self.estado

    def _bucle(self) -> None:
        while not self._parar.is_set():
            if self.estado == "CORRIENDO":
                try:
                    self.ciclo()
                except Exception as e:                       # el hilo nunca muere en silencio
                    self.bd.error("bucle", e, self.origen)
            self._parar.wait(self.cfg.revisar_cada_s)

    # ---------- ciclo ----------
    def reglas(self) -> ReglasPar:
        if self._reglas is None:
            try:
                self._reglas = self.mercado.reglas(self.cfg.simbolo)
            except MercadoError as e:
                self.bd.error("reglas", e, self.origen)
                return ReglasPar()                           # valores conservadores por defecto
        return self._reglas

    def ciclo(self) -> dict:
        """Ejecuta un ciclo. Es idempotente por vela: si ya se decidió esa vela, no hace nada."""
        with self._lock:
            return self._ciclo()

    def _ciclo(self) -> dict:
        sim = self.cfg.simbolo
        try:
            velas = self.mercado.velas(sim, self.cfg.intervalo, limite=60)
            cerradas, en_curso = separar_velas(velas, self.reloj_ms(), self.cfg.antiguedad_max_h)
        except (MercadoError, DatoAtrasadoError) as e:
            self.bd.error("datos", e, self.origen)
            return {"resultado": "sin datos válidos", "error": str(e)}
        self.bd.guardar_velas(sim, cerradas[-60:])
        ultima = cerradas[-1]; fecha = ultima.fecha
        if self.bd.existe_decision(sim, fecha, self.origen):
            return {"resultado": "vela ya procesada", "fecha_vela": fecha}

        try:
            var = variables([v.close for v in cerradas])
            pron = self.predictor.predecir(var["lags"])
        except ModeloError as e:
            self.bd.error("modelo", e, self.origen)
            return {"resultado": "error de modelo", "error": str(e)}

        c = copy.deepcopy(self.cartera)                      # se confirma solo si la decisión se registra
        if c.dia != fecha:
            c.dia, c.patrimonio_inicio_dia = fecha, c.patrimonio(ultima.close)
        contexto = dict(simbolo=sim, fecha_vela=fecha, cierre=ultima.close, rend_ultimo=round(var["rend_ultimo"], 6),
                        pronostico=round(pron, 6), dist_sma20=round(var["dist_sma20"], 6), vol20=round(var["vol20"], 6),
                        posicion=c.posicion, efectivo=round(c.efectivo, 2),
                        patrimonio=round(c.patrimonio(ultima.close), 2), modelo=self.predictor.nombre)

        texto, lat, propuesta, just = None, None, None, None
        try:
            texto, lat = self.llm.proponer(contexto)
            p = validar_propuesta(texto, sim, fecha)
            propuesta, just = p.accion, p.justificacion
        except OllamaError as e:
            self.bd.error("llm", e, self.origen)
            just = "LLM no disponible: se mantiene sin operar"
        except PropuestaInvalida as e:
            self.bd.error("validacion", e, self.origen)
            just = f"Propuesta rechazada: {e}"

        precio_exec = en_curso.open if en_curso else ultima.close
        try:
            res = ejecutar(propuesta or "MANTENER", c, precio_exec, self.reglas(), self.cfg) if propuesta \
                else Resultado("MANTENER", False, just or "sin propuesta válida")
        except SaldoInsuficienteError as e:
            self.bd.error("riesgo", e, self.origen)
            res = Resultado("MANTENER", False, str(e))

        did = self.bd.guardar_decision(dict(
            origen=self.origen, simbolo=sim, fecha_vela=fecha, cierre=ultima.close, precio_ejecucion=precio_exec, pronostico=pron, variables={k: v for k, v in var.items() if k != "lags"},
            respuesta_llm=texto, latencia_s=lat, modelo_llm=self.llm.modelo, accion_propuesta=propuesta,
            justificacion=just, accion_final=res.accion_final, aprobada=int(res.aprobada), motivo=res.motivo))
        if did is None:                                      # evento duplicado: no se toca la cartera
            self.bd.error("duplicado", f"Decisión para {fecha} ya existía; no se ejecuta otra vez", self.origen)
            return {"resultado": "vela ya procesada", "fecha_vela": fecha}

        self.cartera = c
        if res.accion_final in ("COMPRAR", "VENDER"):
            self.bd.guardar_orden(did, fecha, res.accion_final, res.precio, res.cantidad, res.costo, self.origen)
        self.bd.guardar_estado(f"cartera_{self.origen}", self.cartera.dict())
        self.bd.guardar_patrimonio(fecha, c.efectivo, c.cantidad, precio_exec, self.origen)
        self.ultimo = dict(creado=ahora(), fecha_vela=fecha, precio_ejecucion=precio_exec, contexto=contexto,
                           propuesta=propuesta, justificacion=just, latencia_s=lat, accion_final=res.accion_final,
                           aprobada=res.aprobada, motivo=res.motivo)
        return {"resultado": "decision registrada", **self.ultimo}

    # ---------- lectura ----------
    def resumen(self) -> dict:
        if self.ultimo:
            patrimonio = self.cartera.patrimonio(self.ultimo["precio_ejecucion"])
        else:                                                # tras un reinicio: último registro guardado
            filas = self.bd.curva_patrimonio(1, self.origen)
            patrimonio = filas[-1]["patrimonio"] if filas else self.cartera.efectivo
        return dict(version=__version__, modo=self.cfg.modo, estado=self.estado, simbolo=self.cfg.simbolo,
                    intervalo=self.cfg.intervalo,
                    modelo=dict(nombre=self.predictor.nombre, cargado=self.predictor.cargado,
                                meta=self.predictor.meta or {}),
                    llm=dict(modelo=self.llm.modelo, local=True),
                    cartera=self.cartera.dict(),
                    patrimonio=patrimonio,
                    capital_inicial=self.cfg.capital_inicial,
                    riesgo=dict(exposicion_max=self.cfg.exposicion_max, perdida_diaria_max=self.cfg.perdida_diaria_max,
                                antiguedad_max_h=self.cfg.antiguedad_max_h, costo=self.cfg.costo,
                                deslizamiento=self.cfg.deslizamiento),
                    ultimo=self.ultimo)
