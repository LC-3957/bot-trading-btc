# Error 7: Evento duplicado

**Resultado:** ✔ comportamiento correcto

**Cómo se provocó:** Se ejecutó dos veces el ciclo sobre la misma vela real.

**Respuesta del agente:**

```
{'primer_ciclo': 'decision registrada', 'segundo_ciclo': 'vela ya procesada'}
```

**Registros en la tabla de errores:**

| Hora (UTC) | Etapa | Tipo | Mensaje |
|---|---|---|---|
| — | — | — | sin registros |

_Generado el 2026-11-25 23:09 UTC con `python -m app.provocar 7`._
