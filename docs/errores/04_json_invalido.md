# Error 4: JSON inválido del LLM

**Resultado:** ✔ comportamiento correcto

**Cómo se provocó:** Falla inyectada: se reemplazó la respuesta del LLM por un JSON cortado.

**Respuesta del agente:**

```
{'resultado': 'decision registrada', 'creado': '2026-11-25T23:09:12+00:00', 'fecha_vela': '2026-11-24', 'precio_ejecucion': 59830.51, 'contexto': {'simbolo': 'BTCUSDT', 'fecha_vela': '2026-11-24', 'cierre': 59830.51, 'rend_ultimo': -0.023653, 'pronostico': 0.002401, 'dist_sma20': -0.114586, 'vol20': 0.024721, 'posicion': 0, 'efectivo': 50000.0, 'patrimonio': 50000.0, 'modelo': 'MLP16'}, 'propuesta': None, 'justificacion': 'Propuesta rechazada: JSON inválido del LLM: \'{"accion": "COMPRAR", "simbolo": \'', 'latencia_s': 0.0, 'accion_final': 'MANTENER', 'aprobada': False, 'motivo': 'Propuesta rechazada: JSON inválido del LLM: \'{"accion": "COMPRAR", "simbolo": \'', 'mexc_prueba': None}
```

**Registros en la tabla de errores:**

| Hora (UTC) | Etapa | Tipo | Mensaje |
|---|---|---|---|
| 2026-11-25T23:09:12+00:00 | validacion | PropuestaInvalida | JSON inválido del LLM: '{"accion": "COMPRAR", "simbolo": ' |

_Generado el 2026-11-25 23:09 UTC con `python -m app.provocar 4`._
