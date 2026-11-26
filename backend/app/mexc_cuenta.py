"""Conexión con la cuenta spot de MEXC del usuario (endpoints firmados).

Solo existen dos llamadas privadas:
- GET  /api/v3/account     → leer permisos y saldos.
- POST /api/v3/order/test  → MEXC "crea y valida una orden nueva, pero no la manda al motor de
                              ejecución" (documentación oficial Spot V3). Es la forma de probar el
                              bot con la cuenta sin mover dinero.

No hay ningún método que llame a /api/v3/order (orden real). Una prueba automática lo verifica.

Seguridad: la clave y el secreto viven solo en `.env` y en este objeto. No se envían al LLM, no se
devuelven al navegador (solo una versión enmascarada) y no se escriben en la base de datos.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx

RUTA_CUENTA = "/api/v3/account"
RUTA_ORDEN_PRUEBA = "/api/v3/order/test"
RUTA_HORA = "/api/v3/time"
# RUTA_HORA es pública: da la hora del servidor de MEXC para corregir el reloj de la compu.


class CuentaError(Exception):
    """MEXC rechazó la petición (clave inválida, permisos, parámetros de la orden, etc.)."""


def firmar(secreto: str, consulta: str) -> str:
    return hmac.new(secreto.encode(), consulta.encode(), hashlib.sha256).hexdigest()


def enmascarar(clave: str) -> str:
    return f"{clave[:4]}…{clave[-4:]}" if len(clave) > 8 else "…"


class ClienteCuentaMEXC:
    def __init__(self, base_url: str, api_key: str, api_secret: str, timeout_s: float = 10.0,
                 transport: httpx.BaseTransport | None = None, reloj_ms=lambda: int(time.time() * 1000)):
        if not api_key or not api_secret:
            raise ValueError("Faltan MEXC_API_KEY o MEXC_API_SECRET.")
        self._key, self._secret, self._reloj = api_key, api_secret, reloj_ms
        self._desfase_ms: int | None = None    # hora de MEXC − hora de esta compu
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s, transport=transport,
                                  headers={"X-MEXC-APIKEY": api_key, "Content-Type": "application/json"})

    @property
    def clave_visible(self) -> str:
        return enmascarar(self._key)

    def _sincronizar(self) -> None:
        """Mide la diferencia entre el reloj de la compu y el de MEXC (evita el error de recvWindow)."""
        try:
            antes = self._reloj()
            r = self._http.get(RUTA_HORA)
            despues = self._reloj()
            self._desfase_ms = int(r.json()["serverTime"]) - (antes + despues) // 2
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            self._desfase_ms = 0

    def _enviar(self, metodo: str, ruta: str, params: dict) -> httpx.Response:
        if self._desfase_ms is None:
            self._sincronizar()
        consulta = urlencode({**params, "timestamp": self._reloj() + (self._desfase_ms or 0), "recvWindow": 10000})
        url = f"{ruta}?{consulta}&signature={firmar(self._secret, consulta)}"
        ultimo: Exception | None = None
        for _ in range(2):                                   # un reintento si la red falla
            try:
                return self._http.request(metodo, url)
            except httpx.HTTPError as e:
                ultimo = e
        raise CuentaError(f"MEXC sin respuesta: {type(ultimo).__name__}") from ultimo

    def _firmado(self, metodo: str, ruta: str, params: dict) -> dict:
        for intento in range(2):
            r = self._enviar(metodo, ruta, params)
            try:
                datos = r.json()
            except ValueError:
                datos = {}
            msg = datos.get("msg") if isinstance(datos, dict) else None
            if intento == 0 and r.status_code >= 400 and msg and "recvWindow" in msg:
                self._sincronizar()                          # reloj desfasado: se vuelve a medir y se reintenta
                continue
            if r.status_code >= 400 or (isinstance(datos, dict) and datos.get("code") not in (None, 0, 200)):
                raise CuentaError(f"MEXC respondió {r.status_code}: {msg or r.text[:200]}")
            return datos
        raise CuentaError("MEXC rechazó la hora de la petición incluso tras sincronizar el reloj.")

    def cuenta(self) -> dict:
        d = self._firmado("GET", RUTA_CUENTA, {})
        saldos = [{"activo": b["asset"], "libre": float(b["free"]), "bloqueado": float(b["locked"])}
                  for b in d.get("balances", []) if float(b.get("free", 0)) + float(b.get("locked", 0)) > 0]
        return {"puede_operar": bool(d.get("canTrade")), "permisos": d.get("permissions", []), "saldos": saldos}

    def orden_prueba(self, simbolo: str, accion: str, cantidad: float, monto_usdt: float, decimales: int) -> dict:
        """Manda a MEXC la misma orden que ejecutó el simulador, pero al endpoint de prueba."""
        if accion == "COMPRAR":
            params = {"symbol": simbolo, "side": "BUY", "type": "MARKET", "quoteOrderQty": f"{monto_usdt:.2f}"}
        elif accion == "VENDER":
            params = {"symbol": simbolo, "side": "SELL", "type": "MARKET", "quantity": f"{cantidad:.{decimales}f}"}
        else:
            raise ValueError(f"Acción sin orden: {accion}")
        self._firmado("POST", RUTA_ORDEN_PRUEBA, params)
        return params