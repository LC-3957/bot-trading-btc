# Error 6: Saldo insuficiente

**Resultado:** ✔ comportamiento correcto

**Cómo se provocó:** Capital de 0.5 USDT (menor al mínimo de MEXC) y propuesta de compra inyectada.

**Respuesta del agente:**

```
{'resultado': 'decision registrada', 'creado': '2026-11-25T23:09:15+00:00', 'fecha_vela': '2026-11-24', 'precio_ejecucion': 59830.51, 'contexto': {'simbolo': 'BTCUSDT', 'fecha_vela': '2026-11-24', 'cierre': 59830.51, 'rend_ultimo': -0.023653, 'pronostico': 0.002401, 'dist_sma20': -0.114586, 'vol20': 0.024721, 'posicion': 0, 'efectivo': 0.5, 'patrimonio': 0.5, 'modelo': 'MLP16'}, 'propuesta': 'COMPRAR', 'justificacion': 'Compra forzada para la prueba de saldo.', 'latencia_s': 0.0, 'accion_final': 'MANTENER', 'aprobada': False, 'motivo': 'Orden de 0.50 USDT menor al mínimo 1.0 USDT', 'mexc_prueba': None}
```

**Registros en la tabla de errores:**

| Hora (UTC) | Etapa | Tipo | Mensaje |
|---|---|---|---|
| 2026-11-25T23:09:15+00:00 | riesgo | SaldoInsuficienteError | Orden de 0.50 USDT menor al mínimo 1.0 USDT |

_Generado el 2026-11-25 23:09 UTC con `python -m app.provocar 6`._
