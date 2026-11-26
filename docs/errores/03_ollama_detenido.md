# Error 3: Ollama detenido

**Resultado:** ✔ comportamiento correcto

**Cómo se provocó:** El agente apuntó a un puerto local donde no hay Ollama (equivale a Ollama detenido). También puedes cerrar Ollama y presionar «Revisar vela ahora» en el panel.

**Respuesta del agente:**

```
{'resultado': 'decision registrada', 'creado': '2026-11-25T23:09:10+00:00', 'fecha_vela': '2026-11-24', 'precio_ejecucion': 59830.51, 'contexto': {'simbolo': 'BTCUSDT', 'fecha_vela': '2026-11-24', 'cierre': 59830.51, 'rend_ultimo': -0.023653, 'pronostico': 0.002401, 'dist_sma20': -0.114586, 'vol20': 0.024721, 'posicion': 0, 'efectivo': 50000.0, 'patrimonio': 50000.0, 'modelo': 'MLP16'}, 'propuesta': None, 'justificacion': 'LLM no disponible: se mantiene sin operar', 'latencia_s': None, 'accion_final': 'MANTENER', 'aprobada': False, 'motivo': 'LLM no disponible: se mantiene sin operar', 'mexc_prueba': None}
```

**Registros en la tabla de errores:**

| Hora (UTC) | Etapa | Tipo | Mensaje |
|---|---|---|---|
| 2026-11-25T23:09:10+00:00 | llm | OllamaError | Ollama detenido o sin respuesta: ConnectError |

_Generado el 2026-11-25 23:09 UTC con `python -m app.provocar 3`._
