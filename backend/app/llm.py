"""Cliente del LLM local (Ollama) y validación de su propuesta.

Reglas de seguridad:
- Solo se acepta un Ollama en localhost (ver config.validar).
- El prompt se arma únicamente con datos de mercado, pronóstico y estado de la cartera.
  Nunca incluye claves, rutas ni variables de entorno: "no pasar API a la IA".
- El LLM solo propone. La propuesta se valida y después pasa por los controles de riesgo,
  que el LLM no puede modificar.
"""
from __future__ import annotations

import json
import time
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator


class OllamaError(Exception):
    """Ollama detenido, sin respuesta o modelo no disponible."""


class PropuestaInvalida(Exception):
    """El LLM devolvió JSON inválido o una propuesta que no corresponde al ciclo."""


class Propuesta(BaseModel):
    accion: Literal["COMPRAR", "VENDER", "MANTENER"]
    simbolo: str
    fecha_vela: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    justificacion: str = Field(min_length=5, max_length=600)

    @field_validator("accion", mode="before")
    @classmethod
    def _mayus(cls, v):
        return v.upper().strip() if isinstance(v, str) else v


CAMPOS_PERMITIDOS = {"simbolo", "fecha_vela", "cierre", "rend_ultimo", "pronostico", "dist_sma20",
                     "vol20", "posicion", "efectivo", "patrimonio", "modelo"}

SISTEMA = (
    "Eres el módulo de decisión de un bot académico de trading en modo simulado (Paper). "
    "Recibes datos de una vela diaria ya cerrada y un pronóstico del rendimiento del día siguiente. "
    "Propón UNA acción: COMPRAR (solo si la posición es 0), VENDER (solo si la posición es 1) o MANTENER. "
    "No puedes cambiar límites de riesgo, capital ni símbolo. "
    "Responde SOLO con un objeto JSON con las claves exactas: "
    '{"accion": "COMPRAR|VENDER|MANTENER", "simbolo": "<símbolo recibido>", '
    '"fecha_vela": "<fecha recibida YYYY-MM-DD>", "justificacion": "<máximo 2 frases en español>"}'
)


def construir_prompt(contexto: dict) -> str:
    extra = set(contexto) - CAMPOS_PERMITIDOS
    if extra:
        raise ValueError(f"Campos no permitidos en el prompt: {sorted(extra)}")
    return "Datos del ciclo (JSON):\n" + json.dumps(contexto, ensure_ascii=False, indent=2)


def validar_propuesta(texto: str, simbolo: str, fecha_vela: str) -> Propuesta:
    try:
        datos = json.loads(texto)
    except (json.JSONDecodeError, TypeError) as e:
        raise PropuestaInvalida(f"JSON inválido del LLM: {str(texto)[:120]!r}") from e
    try:
        p = Propuesta.model_validate(datos)
    except ValidationError as e:
        raise PropuestaInvalida(f"Propuesta con campos inválidos: {e.errors()[0]['msg']}") from e
    if p.simbolo.upper() != simbolo:
        raise PropuestaInvalida(f"Símbolo distinto al configurado: {p.simbolo} ≠ {simbolo}")
    if p.fecha_vela != fecha_vela:
        raise PropuestaInvalida(f"La propuesta es para otra vela: {p.fecha_vela} ≠ {fecha_vela}")
    return p


class ClienteOllama:
    def __init__(self, url: str, modelo: str, timeout_s: float = 120.0,
                 transport: httpx.BaseTransport | None = None):
        self.modelo = modelo
        self._http = httpx.Client(base_url=url.rstrip("/"), timeout=timeout_s, transport=transport)

    def info(self) -> dict:
        try:
            v = self._http.get("/api/version").json().get("version", "?")
            modelos = [m["name"] for m in self._http.get("/api/tags").json().get("models", [])]
        except (httpx.HTTPError, ValueError) as e:
            raise OllamaError(f"Ollama no responde en local: {type(e).__name__}") from e
        return {"version_ollama": v, "modelo": self.modelo, "modelo_disponible": self.modelo in modelos}

    def proponer(self, contexto: dict) -> tuple[str, float]:
        """Devuelve (texto crudo del LLM, latencia en segundos)."""
        cuerpo = {"model": self.modelo, "stream": False, "format": "json",
                  "options": {"temperature": 0, "seed": 42},
                  "messages": [{"role": "system", "content": SISTEMA},
                               {"role": "user", "content": construir_prompt(contexto)}]}
        t0 = time.perf_counter()
        try:
            r = self._http.post("/api/chat", json=cuerpo)
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama detenido o sin respuesta: {type(e).__name__}") from e
        if r.status_code != 200:
            raise OllamaError(f"Ollama respondió {r.status_code}: {r.text[:200]}")
        try:
            texto = r.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as e:
            raise OllamaError("Respuesta de Ollama sin mensaje") from e
        return texto, time.perf_counter() - t0
