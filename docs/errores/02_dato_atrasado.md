# Error 2: Dato atrasado

**Resultado:** ✔ comportamiento correcto

**Cómo se provocó:** Se bajó ANTIGUEDAD_MAX_H a 0.01 h: la última vela cerrada real de MEXC queda fuera del límite.

**Respuesta del agente:**

```
{'resultado': 'sin datos válidos', 'error': 'Última vela cerrada (2026-11-24) tiene 23.2 h; máximo permitido 0.01 h.'}
```

**Registros en la tabla de errores:**

| Hora (UTC) | Etapa | Tipo | Mensaje |
|---|---|---|---|
| 2026-11-25T23:09:07+00:00 | datos | DatoAtrasadoError | Última vela cerrada (2026-11-24) tiene 23.2 h; máximo permitido 0.01 h. |

_Generado el 2026-11-25 23:09 UTC con `python -m app.provocar 2`._
