# Informe del agente de trading BTCUSDT · v0.3.0

**Autora:** Lyzzet Valenzuela Cabello · **Materia:** Deep Learning para Finanzas · **Fecha:** 2026-11-25

## 1. Objetivo
Construir un agente que decida una vez al día sobre BTCUSDT en MEXC combinando el pronóstico de una red neuronal (práctica, caps. 7–10) con la propuesta de un LLM ejecutado localmente, bajo controles de riesgo fijos y en modo Paper.

## 2. Arquitectura
Interfaz Vue + Vite + TypeScript → API FastAPI protegida con clave → ciclo del agente (datos públicos de MEXC, MLP, Ollama local, validación, riesgo, simulador Paper) → SQLite. El diagrama está en el README.

## 3. Modelo de pronóstico
- Modelo: **MLP16** (RMSE de VA en Colab: 0.025028).
- Entradas: 20 rendimientos diarios; objetivo: rendimiento del día siguiente. Escalador ajustado solo con TR.
- Validación con precios de MEXC: -1.19%. El MLP NO mejora al pronóstico cero con datos de MEXC: sus pronósticos deben tomarse con cautela..

## 4. LLM local
- Ollama en `http://127.0.0.1:11434`, modelo `qwen2.5:7b`. Tiempo de respuesta de prueba: 5.51 s.
- El prompt solo contiene datos de mercado y de la cartera; ninguna clave llega al LLM (verificado con una prueba automática).
- La respuesta se valida (JSON, acción del catálogo, símbolo y vela); si falla, no se opera.

## 5. Riesgo y simulación
Capital 50,000 USDT, costo 0.10%, deslizamiento 0.05%, exposición máxima 100.00%, pérdida diaria máxima 5.00%, antigüedad máxima del dato 26 h. Sin apalancamiento ni ventas en corto. La decisión del cierre *t* se ejecuta en la apertura de *t+1*.

## 6. Evidencia de ciclos
| Origen | Ciclos | Operaciones | Rechazadas | Sin propuesta válida | Latencia media | Errores |
|---|---|---|---|---|---|---|
| En vivo | 1 | 0 | 1 | 1 | — | 7 |
| Replay | 25 | 5 | 2 | 0 | 0.8 s | 0 |

Se alcanzan los 20 ciclos válidos. Los ciclos de replay usan velas históricas de MEXC, una decisión por vela diaria, y están marcados como replay.

## 7. Comparación (replay, mismo periodo y mismos costos)
| Estrategia | Rendimiento neto | Máx. drawdown | Operaciones | Win Rate |
|---|---|---|---|---|
| Comprar y mantener | -7.94% | -11.00% | 2 | 0.00% |
| Modelo sin LLM (pronóstico > 0.00%) | -7.94% | -11.00% | 2 | 0.00% |
| Agente con LLM | -10.02% | -12.11% | 6 | 0.00% |

En 25 ciclos (2026-10-16 a 2026-11-09), el agente con LLM obtuvo -10.02% contra -7.94% de comprar y mantener y -7.94% del modelo sin LLM. El agente no superó a comprar y mantener en este periodo. Agregar el LLM no mejoró el resultado frente al modelo solo. Latencia media del LLM: 0.8 s; propuestas rechazadas: 2.

## 8. Errores provocados
| # | Error | Comportamiento esperado | Evidencia |
|---|---|---|---|
| 1 | API de MEXC sin respuesta o con límite de solicitudes | el ciclo se omite y se registra el error; no se opera con datos incompletos | ✔ errores/01_mexc_sin_respuesta.md |
| 2 | Dato atrasado | la vela con más de ANTIGUEDAD_MAX_H horas se rechaza | ✔ errores/02_dato_atrasado.md |
| 3 | Ollama detenido | se registra el error y la acción final es MANTENER | ✔ errores/03_ollama_detenido.md |
| 4 | JSON inválido del LLM | la propuesta se rechaza por la validación y no se opera | ✔ errores/04_json_invalido.md |
| 5 | Clave incorrecta | la API responde 401 y el intento queda en errores | ✔ errores/05_clave_incorrecta.md |
| 6 | Saldo insuficiente | la orden se rechaza por monto mínimo o falta de efectivo | ✔ errores/06_saldo_insuficiente.md |
| 7 | Evento duplicado | la misma vela no se decide dos veces | ✔ errores/07_evento_duplicado.md |
| 8 | Reinicio del backend | la cartera se recupera desde SQLite sin duplicar operaciones | ✔ errores/08_reinicio_backend.md |
| 9 | Botón de detener | el ciclo se detiene y no se toman más decisiones | ✔ errores/09_boton_detener.md |

Pruebas automáticas: 49 passed, 1 warning in 11.60s.

## 9. Limitaciones
- El MLP se entrenó con BTC-USD de Yahoo Finance y opera con precios de MEXC; la sección 3 indica si su error se mantiene.
- Los rendimientos diarios de BTC tienen mucho ruido: un pronóstico cercano a cero es esperable y el resultado depende del periodo.
- El replay reproduce decisiones sobre velas pasadas; no sustituye la operación en vivo durante varias semanas.
- Modo Paper: no hay ejecución real, profundidad de mercado ni comisiones de retiro.

## 10. Conclusiones
El agente cumplió el protocolo: 25 ciclos de replay con datos reales de MEXC, LLM local (qwen2.5:7b en mi RTX 5080, ~5.5 s por respuesta) y los 9 errores provocados manejados sin operar con datos inválidos. En el periodo del 16 de octubre al 9 de noviembre, BTC cayó y ninguna estrategia ganó: el agente con LLM obtuvo −10.02 % contra −7.94 % de comprar y mantener, porque hizo más operaciones (6 contra 2) y pagó más costos en un mercado a la baja. El MLP16 no mejoró al pronóstico cero con precios de MEXC (RMSE −1.19 %), lo que confirma que los rendimientos diarios de BTC tienen mucho ruido. En una siguiente versión usaría un umbral mínimo de pronóstico para operar menos, probaría la LSTM (que fue la mejor en VA en el avance 2) y dejaría el bot en vivo varias semanas para comparar con el replay.

_Informe generado el 2026-11-25 23:09 UTC con `python -m app.informe`._
