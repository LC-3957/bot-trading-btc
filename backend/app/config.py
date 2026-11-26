"""Configuración del bot. Todo sale de variables de entorno (.env); nada se escribe en el código.

Los límites de riesgo viven aquí y el LLM no puede cambiarlos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1"}


class ConfigError(Exception):
    """Configuración inválida: el bot no arranca."""


def _f(nombre: str, defecto: str) -> float:
    try:
        return float(os.getenv(nombre, defecto))
    except ValueError as e:
        raise ConfigError(f"{nombre} debe ser numérico") from e


def _ruta(nombre: str, defecto: str) -> str:
    """Rutas relativas se resuelven desde la raíz del repositorio, no desde la carpeta actual."""
    p = Path(os.getenv(nombre, defecto))
    return str(p if p.is_absolute() else RAIZ / p)


@dataclass(frozen=True)
class Config:
    modo: str = field(default_factory=lambda: os.getenv("MODO", "PAPER").upper())
    simbolo: str = field(default_factory=lambda: os.getenv("SIMBOLO", "BTCUSDT").upper())
    intervalo: str = field(default_factory=lambda: os.getenv("INTERVALO", "1d"))
    mexc_url: str = field(default_factory=lambda: os.getenv("MEXC_URL", "https://api.mexc.com"))

    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
    ollama_modelo: str = field(default_factory=lambda: os.getenv("OLLAMA_MODELO", "qwen2.5:7b"))
    ollama_timeout_s: float = field(default_factory=lambda: _f("OLLAMA_TIMEOUT_S", "120"))

    api_key: str = field(default_factory=lambda: os.getenv("BOT_API_KEY", ""), repr=False)
    mexc_api_key: str = field(default_factory=lambda: os.getenv("MEXC_API_KEY", "").strip(), repr=False)
    mexc_api_secret: str = field(default_factory=lambda: os.getenv("MEXC_API_SECRET", "").strip(), repr=False)
    mexc_monto_prueba: float = field(default_factory=lambda: _f("MEXC_MONTO_PRUEBA_USDT", "0"))
    db_path: str = field(default_factory=lambda: _ruta("DB_PATH", "data/bot_v2.sqlite"))
    modelo_path: str = field(default_factory=lambda: _ruta("MODELO_PATH", "models/modelo_mlp.json"))

    capital_inicial: float = field(default_factory=lambda: _f("CAPITAL_INICIAL", "50000"))
    costo: float = field(default_factory=lambda: _f("COSTO", "0.0"))
    deslizamiento: float = field(default_factory=lambda: _f("DESLIZAMIENTO", "0.0005"))
    exposicion_max: float = field(default_factory=lambda: _f("EXPOSICION_MAX", "1.0"))
    perdida_diaria_max: float = field(default_factory=lambda: _f("PERDIDA_DIARIA_MAX", "0.05"))
    antiguedad_max_h: float = field(default_factory=lambda: _f("ANTIGUEDAD_MAX_H", "26"))
    revisar_cada_s: float = field(default_factory=lambda: _f("REVISAR_CADA_S", "60"))
    umbral_modelo: float = field(default_factory=lambda: _f("UMBRAL_MODELO", "0.0"))

    def validar(self) -> "Config":
        if self.modo != "PAPER":
            raise ConfigError("v0.1 solo opera en MODO=PAPER. Las órdenes reales están bloqueadas.")
        if self.api_key.upper().startswith("CAMBIA"):
            raise ConfigError("Cambia BOT_API_KEY en .env: no uses el valor de ejemplo.")
        if len(self.api_key) < 16:
            raise ConfigError("BOT_API_KEY debe tener al menos 16 caracteres (ver .env.example).")
        host = urlparse(self.ollama_url).hostname
        if host not in HOSTS_LOCALES:
            raise ConfigError(f"OLLAMA_URL debe ser local (localhost/127.0.0.1); se recibió '{host}'. "
                              "El bot solo consume un LLM local.")
        if not 0 < self.exposicion_max <= 1:
            raise ConfigError("EXPOSICION_MAX debe estar entre 0 y 1 (sin apalancamiento).")
        if not 0 < self.perdida_diaria_max < 1:
            raise ConfigError("PERDIDA_DIARIA_MAX debe estar entre 0 y 1.")
        return self


def cargar() -> Config:
    return Config().validar()
