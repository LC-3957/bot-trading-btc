# Error 8: Reinicio del backend

**Resultado:** ✔ comportamiento correcto

**Cómo se provocó:** Se creó un segundo agente sobre la misma base (equivale a reiniciar el backend).

**Respuesta del agente:**

```
{'cartera_antes': {'efectivo': 0.0005716137966373935, 'cantidad': 0.83444194, 'precio_entrada': 59860.425255, 'patrimonio_inicio_dia': 50000.0, 'dia': '2026-11-24', 'posicion': 1}, 'cartera_despues': {'efectivo': 0.0005716137966373935, 'cantidad': 0.83444194, 'precio_entrada': 59860.425255, 'patrimonio_inicio_dia': 50000.0, 'dia': '2026-11-24', 'posicion': 1}, 'ciclo_tras_reinicio': 'vela ya procesada'}
```

**Registros en la tabla de errores:**

| Hora (UTC) | Etapa | Tipo | Mensaje |
|---|---|---|---|
| — | — | — | sin registros |

_Generado el 2026-11-25 23:09 UTC con `python -m app.provocar 8`._
