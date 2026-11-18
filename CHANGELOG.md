# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versionado semántico.

## [0.2.0] - 2026-11-17
### Cambiado
- Cada registro de la base de datos lleva `origen` (`vivo` o `replay`). La nueva base es `data/bot_v2.sqlite`.

### Agregado
- Modo replay (`python -m app.replay`): recorre velas históricas de MEXC con el mismo ciclo y marca todo como replay.
- Comparación del protocolo: comprar y mantener vs. modelo sin LLM vs. agente con LLM, con rendimiento neto, drawdown, Win Rate, operaciones, latencia y rechazos.
- Validación del MLP con datos reales de MEXC (`python -m app.validar`).
- Panel: gráfica de precio con compras y ventas, métricas de evidencia, tabla de comparación, selector vivo/replay y exportación a CSV.
- Endpoints `/api/metricas`, `/api/comparacion`, `/api/grafica` y `/api/exportar/{tabla}`.
- GitHub Actions: pruebas del backend y build de la interfaz en cada push.
- 9 pruebas nuevas (32 en total).

## [0.1.0] - 2026-11-17
### Agregado
- Backend en FastAPI con ciclo diario: datos públicos de MEXC → variables → pronóstico del MLP → propuesta del LLM local → validación → riesgo → simulación Paper → registro.
- Cliente de Ollama solo para localhost, con salida JSON validada (acción, símbolo, fecha de vela y justificación).
- Simulador Paper: 50,000 USDT, sin apalancamiento ni ventas en corto, precisión y mínimo del par, deslizamiento configurable.
- Controles de riesgo en configuración: exposición máxima, pérdida diaria máxima y antigüedad máxima del dato.
- SQLite para velas, decisiones, órdenes, patrimonio, errores y estado; una sola decisión por vela.
- API protegida con `X-API-Key` y documentación automática en `/docs`.
- Interfaz en Vue 3 + Vite + TypeScript con botones de iniciar, pausar, detener y revisar vela.
- 23 pruebas automatizadas, incluidos los 9 errores provocados del protocolo.
