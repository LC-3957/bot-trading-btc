"""Simulador Paper y controles de riesgo.

- Capital inicial configurable (50,000 USDT por defecto), sin apalancamiento ni ventas en corto.
- Costo y deslizamiento configurables; el deslizamiento empeora el precio de ejecución.
- La cantidad se redondea hacia abajo a la precisión del par y se respeta el mínimo de la orden.
- Los límites salen de la configuración; el LLM no puede cambiarlos.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .mexc import ReglasPar


class SaldoInsuficienteError(Exception):
    """La orden no alcanza el mínimo del par o no hay saldo."""


@dataclass
class Cartera:
    efectivo: float
    cantidad: float = 0.0
    precio_entrada: float = 0.0
    patrimonio_inicio_dia: float = 0.0
    dia: str = ""

    @property
    def posicion(self) -> int:
        return int(self.cantidad > 0)

    def patrimonio(self, precio: float) -> float:
        return self.efectivo + self.cantidad * precio

    def dict(self) -> dict:
        return asdict(self) | {"posicion": self.posicion}


@dataclass
class Resultado:
    accion_final: str
    aprobada: bool
    motivo: str
    precio: float | None = None
    cantidad: float = 0.0
    costo: float = 0.0


def _redondear_abajo(x: float, decimales: int) -> float:
    f = 10 ** decimales
    return math.floor(x * f) / f


def revisar_riesgo(accion: str, cartera: Cartera, precio: float, cfg) -> tuple[bool, str]:
    if accion == "MANTENER":
        return True, "sin operación"
    if accion == "COMPRAR" and cartera.posicion:
        return False, "ya hay una posición abierta (sin piramidar)"
    if accion == "VENDER" and not cartera.posicion:
        return False, "no hay posición que vender (sin ventas en corto)"
    if accion == "COMPRAR":
        if cartera.patrimonio_inicio_dia > 0:
            caida = 1 - cartera.patrimonio(precio) / cartera.patrimonio_inicio_dia
            if caida >= cfg.perdida_diaria_max:
                return False, f"pérdida diaria {caida:.2%} ≥ límite {cfg.perdida_diaria_max:.2%}: compras bloqueadas"
    return True, "dentro de límites"


def ejecutar(accion: str, cartera: Cartera, precio_ref: float, reglas: ReglasPar, cfg) -> Resultado:
    ok, motivo = revisar_riesgo(accion, cartera, precio_ref, cfg)
    if not ok:
        return Resultado("MANTENER", False, motivo)
    if accion == "MANTENER":
        return Resultado("MANTENER", True, motivo)
    if not (math.isfinite(precio_ref) and precio_ref > 0):
        return Resultado("MANTENER", False, "precio de ejecución inválido")

    if accion == "COMPRAR":
        precio = precio_ref * (1 + cfg.deslizamiento)
        monto = cartera.efectivo * cfg.exposicion_max
        cantidad = _redondear_abajo(monto / (precio * (1 + cfg.costo)), reglas.precision_cantidad)
        bruto = cantidad * precio
        if cantidad <= 0 or bruto < reglas.minimo_notional:
            raise SaldoInsuficienteError(f"Orden de {bruto:.2f} USDT menor al mínimo {reglas.minimo_notional} USDT")
        costo = bruto * cfg.costo
        if bruto + costo > cartera.efectivo + 1e-9:
            raise SaldoInsuficienteError("Saldo insuficiente para la compra (sin apalancamiento)")
        cartera.efectivo -= bruto + costo
        cartera.cantidad += cantidad
        cartera.precio_entrada = precio
        return Resultado("COMPRAR", True, motivo, precio, cantidad, costo)

    precio = precio_ref * (1 - cfg.deslizamiento)                      # VENDER
    cantidad = cartera.cantidad
    bruto = cantidad * precio
    costo = bruto * cfg.costo
    cartera.efectivo += bruto - costo
    cartera.cantidad = 0.0
    cartera.precio_entrada = 0.0
    return Resultado("VENDER", True, motivo, precio, cantidad, costo)
