# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versionado semántico.

## [0.3.0] - 2026-11-24
### Corregido
- Las peticiones firmadas usan la hora del servidor de MEXC (`/api/v3/time`): si el reloj de la compu está desfasado ya no aparece el error de `recvWindow`. Se reintenta una vez si la red falla.

### Agregado
- Conexión con la cuenta spot de MEXC (`mexc_cuenta.py`), con firma HMAC-SHA256: lectura de saldo y permisos, y órdenes de prueba en `/api/v3/order/test` (MEXC las valida y no las ejecuta).
- Cada orden del simulador guarda el resultado de su orden de prueba en MEXC (columna `mexc_prueba`, con migración automática).
- Endpoint `GET /api/mexc` (clave enmascarada) y tarjeta "Cuenta MEXC" en el panel.
- 10 pruebas nuevas (47 en total): firma, rutas permitidas, rechazos, secretos fuera del LLM y del navegador.

## [0.2.1] - 2026-11-18
### Agregado
- Dependencias actualizadas para funcionar con Python 3.14 en Windows (FastAPI 0.121, Pydantic 2.12, Uvicorn 0.38, NumPy 2.3+).
- Scripts para Windows (`scripts/windows/`) y Mac/Linux (`scripts/mac-linux/`): instalar, iniciar y generar evidencia.
- `app.diagnostico`: evidencia del LLM local (hardware, versión de Ollama, modelo y tiempo de respuesta).
- `app.provocar`: provoca los 9 errores del protocolo contra MEXC y Ollama reales y guarda un archivo de evidencia por cada uno.
- `app.informe`: informe en `docs/informe.md` con las cifras reales.
- `app.evidencia`: corre pruebas, diagnóstico, validación, errores, replay e informe en un solo paso.
- `docs/GUIA_EJECUCION.md`: guía paso a paso con solución de problemas.
- 5 pruebas nuevas (37 en total).

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