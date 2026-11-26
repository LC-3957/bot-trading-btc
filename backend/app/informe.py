"""Genera docs/informe.md con las cifras reales de la base de datos y de la evidencia en docs/.

Uso (desde backend/), después de correr el replay, la validación y el diagnóstico:
    python -m app.informe
Revisa el resultado y completa la sección de conclusiones personales antes de entregar.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .comparacion import comparar
from .config import RAIZ, cargar
from .db import BD
from .modelo import cargar_predictor

ERRORES = [  # (archivo de captura esperado, error provocado, comportamiento esperado)
    ("01_mexc_sin_respuesta.png", "API de MEXC sin respuesta o con límite de solicitudes",
     "el ciclo se omite y se registra el error; no se opera con datos incompletos"),
    ("02_dato_atrasado.png", "Dato atrasado", "la vela con más de ANTIGUEDAD_MAX_H horas se rechaza"),
    ("03_ollama_detenido.png", "Ollama detenido", "se registra el error y la acción final es MANTENER"),
    ("04_json_invalido.png", "JSON inválido del LLM", "la propuesta se rechaza por la validación y no se opera"),
    ("05_clave_incorrecta.png", "Clave incorrecta", "la API responde 401 y el intento queda en errores"),
    ("06_saldo_insuficiente.png", "Saldo insuficiente", "la orden se rechaza por monto mínimo o falta de efectivo"),
    ("07_evento_duplicado.png", "Evento duplicado", "la misma vela no se decide dos veces"),
    ("08_reinicio_backend.png", "Reinicio del backend", "la cartera se recupera desde SQLite sin duplicar operaciones"),
    ("09_boton_detener.png", "Botón de detener", "el ciclo se detiene y no se toman más decisiones"),
]


def _pct(v) -> str:
    return "—" if v is None else f"{v:.2%}"


def _tabla_comparacion(res: dict) -> str:
    if not res["ciclos"]:
        return "_Todavía no hay ciclos para comparar._\n"
    filas = ["| Estrategia | Rendimiento neto | Máx. drawdown | Operaciones | Win Rate |", "|---|---|---|---|---|"]
    for f in res["estrategias"]:
        filas.append(f"| {f['estrategia']} | {_pct(f['rendimiento_neto'])} | {_pct(f['max_drawdown'])} | "
                     f"{f['operaciones']} | {_pct(f['win_rate'])} |")
    return "\n".join(filas) + "\n"


def _lectura(res: dict) -> str:
    if not res["ciclos"]:
        return ""
    e = {f["estrategia"].split(" (")[0]: f for f in res["estrategias"]}
    ag, bh, mo = e["Agente con LLM"], e["Comprar y mantener"], e["Modelo sin LLM"]
    frases = [f"En {res['ciclos']} ciclos ({res['periodo'][0]} a {res['periodo'][1]}), el agente con LLM obtuvo "
              f"{_pct(ag['rendimiento_neto'])} contra {_pct(bh['rendimiento_neto'])} de comprar y mantener "
              f"y {_pct(mo['rendimiento_neto'])} del modelo sin LLM."]
    frases.append("El agente superó a comprar y mantener." if ag["rendimiento_neto"] > bh["rendimiento_neto"]
                  else "El agente no superó a comprar y mantener en este periodo.")
    frases.append("Agregar el LLM mejoró el resultado frente al modelo solo." if ag["rendimiento_neto"] > mo["rendimiento_neto"]
                  else "Agregar el LLM no mejoró el resultado frente al modelo solo.")
    if ag["max_drawdown"] > bh["max_drawdown"]:
        frases.append(f"El agente tuvo una caída máxima menor ({_pct(ag['max_drawdown'])} vs. {_pct(bh['max_drawdown'])}).")
    frases.append(f"Latencia media del LLM: {ag['latencia_media_s']:.1f} s; propuestas rechazadas: {ag['rechazadas']}."
                  if ag.get("latencia_media_s") is not None else f"Propuestas rechazadas: {ag['rechazadas']}.")
    return " ".join(frases) + "\n"


def _resumen_md(ruta: Path, patron: str) -> str | None:
    if not ruta.exists():
        return None
    m = re.search(patron, ruta.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else "ver archivo"


def generar(cfg, bd: BD, docs: Path) -> str:
    pred = cargar_predictor(cfg.modelo_path)
    m_vivo, m_rep = bd.metricas("vivo"), bd.metricas("replay")
    origen = "replay" if m_rep["ciclos"] >= m_vivo["ciclos"] else "vivo"
    res = comparar(bd.decisiones_cronologicas(origen), cfg)
    validacion = _resumen_md(docs / "validacion_mexc.md", r"Cambio de RMSE frente al pronóstico cero: ([^\n]+)")
    entorno = _resumen_md(docs / "entorno_llm.md", r"\| Tiempo de respuesta \(propuesta de prueba\) \| ([^|]+) \|")
    pruebas = _resumen_md(docs / "pruebas_automaticas.txt", r"=+ (\d+ passed[^=]*) =+")
    capturas, carpeta_err = docs / "capturas", docs / "errores"

    def evidencia(i: int, archivo: str) -> str:
        partes = []
        md = next(iter(sorted(carpeta_err.glob(f"{i:02d}_*.md"))), None) if carpeta_err.exists() else None
        if md is not None:
            partes.append(("✔ " if "✔" in md.read_text(encoding="utf-8") else "✘ ") + f"errores/{md.name}")
        if (capturas / archivo).exists():
            partes.append(f"captura {archivo}")
        return " · ".join(partes) or "pendiente"

    filas_err = "\n".join(f"| {i} | {nombre} | {esperado} | {evidencia(i, archivo)} |"
                          for i, (archivo, nombre, esperado) in enumerate(ERRORES, 1))
    meta = pred.meta or {}
    return f"""# Informe del agente de trading {cfg.simbolo} · v{__version__}

**Autora:** Lyzzet Valenzuela Cabello · **Materia:** Deep Learning para Finanzas · **Fecha:** {datetime.now(timezone.utc):%Y-%m-%d}

## 1. Objetivo
Construir un agente que decida una vez al día sobre {cfg.simbolo} en MEXC combinando el pronóstico de una red neuronal (práctica, caps. 7–10) con la propuesta de un LLM ejecutado localmente, bajo controles de riesgo fijos y en modo Paper.

## 2. Arquitectura
Interfaz Vue + Vite + TypeScript → API FastAPI protegida con clave → ciclo del agente (datos públicos de MEXC, MLP, Ollama local, validación, riesgo, simulador Paper) → SQLite. El diagrama está en el README.

## 3. Modelo de pronóstico
- Modelo: **{pred.nombre}**{f" (RMSE de VA en Colab: {meta['rmse_va']:.6f})" if 'rmse_va' in meta else ""}.
- Entradas: 20 rendimientos diarios; objetivo: rendimiento del día siguiente. Escalador ajustado solo con TR.
- Validación con precios de MEXC: {validacion or "pendiente (ejecuta `python -m app.validar`)"}.

## 4. LLM local
- Ollama en `{cfg.ollama_url}`, modelo `{cfg.ollama_modelo}`. Tiempo de respuesta de prueba: {entorno or "pendiente (ejecuta `python -m app.diagnostico`)"}.
- El prompt solo contiene datos de mercado y de la cartera; ninguna clave llega al LLM (verificado con una prueba automática).
- La respuesta se valida (JSON, acción del catálogo, símbolo y vela); si falla, no se opera.

## 5. Riesgo y simulación
Capital {cfg.capital_inicial:,.0f} USDT, costo {_pct(cfg.costo)}, deslizamiento {_pct(cfg.deslizamiento)}, exposición máxima {_pct(cfg.exposicion_max)}, pérdida diaria máxima {_pct(cfg.perdida_diaria_max)}, antigüedad máxima del dato {cfg.antiguedad_max_h:.0f} h. Sin apalancamiento ni ventas en corto. La decisión del cierre *t* se ejecuta en la apertura de *t+1*.

## 6. Evidencia de ciclos
| Origen | Ciclos | Operaciones | Rechazadas | Sin propuesta válida | Latencia media | Errores |
|---|---|---|---|---|---|---|
| En vivo | {m_vivo['ciclos']} | {m_vivo['operaciones']} | {m_vivo['rechazadas'] or 0} | {m_vivo['sin_propuesta_valida'] or 0} | {'—' if m_vivo['latencia_media'] is None else f"{m_vivo['latencia_media']:.1f} s"} | {m_vivo['errores']} |
| Replay | {m_rep['ciclos']} | {m_rep['operaciones']} | {m_rep['rechazadas'] or 0} | {m_rep['sin_propuesta_valida'] or 0} | {'—' if m_rep['latencia_media'] is None else f"{m_rep['latencia_media']:.1f} s"} | {m_rep['errores']} |

{"Se alcanzan los 20 ciclos válidos." if max(m_vivo['ciclos'], m_rep['ciclos']) >= 20 else "**Aún no se alcanzan los 20 ciclos válidos.**"} Los ciclos de replay usan velas históricas de MEXC, una decisión por vela diaria, y están marcados como replay.

## 7. Comparación ({origen}, mismo periodo y mismos costos)
{_tabla_comparacion(res)}
{_lectura(res)}
## 8. Errores provocados
| # | Error | Comportamiento esperado | Evidencia |
|---|---|---|---|
{filas_err}

Pruebas automáticas: {pruebas or "pendiente (ejecuta el script de evidencia)"}.

## 9. Limitaciones
- El MLP se entrenó con BTC-USD de Yahoo Finance y opera con precios de MEXC; la sección 3 indica si su error se mantiene.
- Los rendimientos diarios de BTC tienen mucho ruido: un pronóstico cercano a cero es esperable y el resultado depende del periodo.
- El replay reproduce decisiones sobre velas pasadas; no sustituye la operación en vivo durante varias semanas.
- Modo Paper: no hay ejecución real, profundidad de mercado ni comisiones de retiro.

## 10. Conclusiones
_[Escribe aquí 3–5 líneas con tu interpretación de los resultados de las secciones 6 a 8 y qué cambiarías en una siguiente versión.]_

_Informe generado el {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC con `python -m app.informe`._
"""


def main() -> None:
    cfg = cargar()
    docs = Path(RAIZ) / "docs"
    docs.mkdir(exist_ok=True)
    texto = generar(cfg, BD(cfg.db_path), docs)
    (docs / "informe.md").write_text(texto, encoding="utf-8")
    print(texto + f"\nGuardado en {docs / 'informe.md'}")


if __name__ == "__main__":
    main()
