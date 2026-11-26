# Error 1: API de MEXC sin respuesta

**Resultado:** ✔ comportamiento correcto

**Cómo se provocó:** Se apuntó el cliente a un dominio inexistente (`api.mexc.invalid`).

**Respuesta del agente:**

```
{'resultado': 'sin datos válidos', 'error': 'MEXC sin respuesta en /api/v3/klines: ConnectError'}
```

**Registros en la tabla de errores:**

| Hora (UTC) | Etapa | Tipo | Mensaje |
|---|---|---|---|
| 2026-11-25T23:09:06+00:00 | datos | MercadoError | MEXC sin respuesta en /api/v3/klines: ConnectError |

_Generado el 2026-11-25 23:09 UTC con `python -m app.provocar 1`._
