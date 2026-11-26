# Error 5: Clave incorrecta

**Resultado:** ✔ comportamiento correcto

**Cómo se provocó:** Se consultó la API con una clave equivocada y sin clave.

**Respuesta del agente:**

```
{'con_clave_equivocada': 401, 'sin_clave': 401}
```

**Registros en la tabla de errores:**

| Hora (UTC) | Etapa | Tipo | Mensaje |
|---|---|---|---|
| 2026-11-25T23:09:13+00:00 | api | Aviso | Clave incorrecta o ausente en X-API-Key |
| 2026-11-25T23:09:13+00:00 | api | Aviso | Clave incorrecta o ausente en X-API-Key |

_Generado el 2026-11-25 23:09 UTC con `python -m app.provocar 5`._
