"""Cliente de datos públicos de MEXC (spot v3).

Solo usa endpoints públicos: velas y reglas del par. No existe ningún método que firme
peticiones ni envíe órdenes: en v0.1 las órdenes reales están bloqueadas por diseño.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


class MercadoError(Exception):
    """API sin respuesta, límite de solicitudes o respuesta inválida."""


class DatoAtrasadoError(Exception):
    """La última vela cerrada es más vieja que ANTIGUEDAD_MAX_H."""


@dataclass(frozen=True)
class Vela:
    apertura_ms: int
    open: float
    high: float
    low: float
    close: float
    volumen: float
    cierre_ms: int

    @property
    def fecha(self) -> str:
        return datetime.fromtimestamp(self.apertura_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


@dataclass(frozen=True)
class ReglasPar:
    precision_cantidad: int = 6
    precision_precio: int = 2
    minimo_notional: float = 1.0


class ClienteMEXC:
    def __init__(self, base_url: str, timeout_s: float = 10.0, reintentos: int = 2,
                 transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.reintentos = reintentos
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout_s, transport=transport)

    def _get(self, ruta: str, params: dict) -> object:
        ultimo = None
        for intento in range(self.reintentos + 1):
            try:
                r = self._http.get(ruta, params=params)
            except httpx.HTTPError as e:                      # sin respuesta, DNS, timeout
                ultimo = MercadoError(f"MEXC sin respuesta en {ruta}: {type(e).__name__}")
            else:
                if r.status_code == 429:
                    ultimo = MercadoError("MEXC: límite de solicitudes (429). Se reintenta en el siguiente ciclo.")
                elif r.status_code >= 400:
                    raise MercadoError(f"MEXC respondió {r.status_code} en {ruta}: {r.text[:200]}")
                else:
                    try:
                        return r.json()
                    except ValueError as e:
                        raise MercadoError(f"MEXC devolvió JSON inválido en {ruta}") from e
            time.sleep(min(2 ** intento, 5))
        raise ultimo  # type: ignore[misc]

    def velas(self, simbolo: str, intervalo: str = "1d", limite: int = 60) -> list[Vela]:
        datos = self._get("/api/v3/klines", {"symbol": simbolo, "interval": intervalo, "limit": limite})
        if not isinstance(datos, list) or not datos:
            raise MercadoError(f"MEXC no devolvió velas para {simbolo}")
        velas = []
        for fila in datos:
            try:
                velas.append(Vela(int(fila[0]), float(fila[1]), float(fila[2]), float(fila[3]),
                                  float(fila[4]), float(fila[5]), int(fila[6])))
            except (IndexError, TypeError, ValueError) as e:
                raise MercadoError(f"Vela con formato inesperado: {fila!r}") from e
        velas.sort(key=lambda v: v.apertura_ms)
        return velas

    def reglas(self, simbolo: str) -> ReglasPar:
        datos = self._get("/api/v3/exchangeInfo", {"symbol": simbolo})
        try:
            s = next(x for x in datos["symbols"] if x["symbol"] == simbolo)  # type: ignore[index]
            return ReglasPar(precision_cantidad=int(s.get("baseAssetPrecision", 6)),
                             precision_precio=int(s.get("quotePrecision", 2)),
                             minimo_notional=float(s.get("quoteAmountPrecision", 1.0)))
        except (KeyError, StopIteration, TypeError, ValueError) as e:
            raise MercadoError(f"No se encontraron las reglas de {simbolo}") from e


def separar_velas(velas: list[Vela], ahora_ms: int, antiguedad_max_h: float) -> tuple[list[Vela], Vela | None]:
    """Devuelve (velas cerradas, vela en curso). Falla si la última vela cerrada es demasiado vieja."""
    cerradas = [v for v in velas if v.cierre_ms < ahora_ms]
    en_curso = next((v for v in velas if v.apertura_ms <= ahora_ms <= v.cierre_ms), None)
    if not cerradas:
        raise DatoAtrasadoError("No hay velas cerradas.")
    edad_h = (ahora_ms - cerradas[-1].cierre_ms) / 3_600_000
    if edad_h > antiguedad_max_h:
        raise DatoAtrasadoError(f"Última vela cerrada ({cerradas[-1].fecha}) tiene {edad_h:.1f} h; "
                                f"máximo permitido {antiguedad_max_h} h.")
    return cerradas, en_curso
