"""Evidencia de que el LLM corre en esta computadora (lo pide el protocolo).

Registra:
- Hardware: sistema operativo, procesador, núcleos, RAM y GPU NVIDIA si existe.
- Ollama: URL (debe ser de esta máquina), versión y si el modelo está descargado.
- Una propuesta de prueba: tiempo de respuesta y si pasó la validación del JSON.

Uso (desde backend/):  python -m app.diagnostico
Resultado: docs/entorno_llm.md
"""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import HOSTS_LOCALES, RAIZ, cargar
from .llm import ClienteOllama, OllamaError, PropuestaInvalida, validar_propuesta

FECHA_PRUEBA = "2026-01-01"


def ram_gb() -> float | None:
    try:
        if sys.platform == "win32":
            class Estado(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            e = Estado(); e.dwLength = ctypes.sizeof(Estado)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e))  # type: ignore[attr-defined]
            return e.ullTotalPhys / 1024 ** 3
        if sys.platform == "darwin":
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)) / 1024 ** 3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return None


def procesador() -> str:
    try:
        if sys.platform == "win32":
            salida = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"], text=True, timeout=15)
            return salida.strip() or platform.processor()
        if sys.platform == "darwin":
            return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        for linea in Path("/proc/cpuinfo").read_text().splitlines():
            if linea.startswith("model name"):
                return linea.split(":", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.processor() or "desconocido"


def gpu() -> str:
    if not shutil.which("nvidia-smi"):
        return "sin GPU NVIDIA detectada (Ollama usará CPU u otra aceleración)"
    try:
        return subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                                        "--format=csv,noheader"], text=True, timeout=15).strip()
    except (OSError, subprocess.SubprocessError):
        return "nvidia-smi no respondió"


def hardware() -> dict:
    r = ram_gb()
    return {"Sistema operativo": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "Procesador": procesador(), "Núcleos lógicos": str(os.cpu_count()),
            "RAM": f"{r:.1f} GB" if r else "desconocida", "GPU": gpu(), "Python": platform.python_version()}


def probar_llm(cfg, llm: ClienteOllama) -> dict:
    res = {"URL de Ollama": cfg.ollama_url,
           "URL local": "sí" if urlparse(cfg.ollama_url).hostname in HOSTS_LOCALES else "NO",
           "Modelo configurado": cfg.ollama_modelo}
    try:
        info = llm.info()
        res["Versión de Ollama"] = info["version_ollama"]
        res["Modelo descargado"] = "sí" if info["modelo_disponible"] else f"NO (ejecuta: ollama pull {cfg.ollama_modelo})"
    except OllamaError as e:
        res["Versión de Ollama"] = f"sin respuesta: {e}"
        return res
    contexto = dict(simbolo=cfg.simbolo, fecha_vela=FECHA_PRUEBA, cierre=90000.0, rend_ultimo=0.004, pronostico=0.0012,
                    dist_sma20=0.015, vol20=0.021, posicion=0, efectivo=50000.0, patrimonio=50000.0, modelo="diagnóstico")
    try:
        texto, lat = llm.proponer(contexto)
        res["Tiempo de respuesta (propuesta de prueba)"] = f"{lat:.2f} s"
        try:
            p = validar_propuesta(texto, cfg.simbolo, FECHA_PRUEBA)
            res["Propuesta de prueba"] = f"válida: {p.accion} · «{p.justificacion}»"
        except PropuestaInvalida as e:
            res["Propuesta de prueba"] = f"rechazada por la validación: {e}"
    except OllamaError as e:
        res["Tiempo de respuesta (propuesta de prueba)"] = f"sin respuesta: {e}"
    return res


def a_markdown(hw: dict, llm: dict) -> str:
    filas = lambda d: "\n".join(f"| {k} | {v} |" for k, v in d.items())
    return ("# Entorno del LLM local\n\n"
            "Evidencia de que la inferencia del LLM ocurre en esta computadora y no en la nube.\n\n"
            "## Hardware\n\n| Dato | Valor |\n|---|---|\n" + filas(hw) +
            "\n\n## Ollama\n\n| Dato | Valor |\n|---|---|\n" + filas(llm) +
            "\n\nLa propuesta de prueba usa datos ficticios y no se guarda en la base de datos. "
            "El prompt solo contiene datos de mercado y de la cartera; ninguna clave.\n\n"
            f"_Generado el {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC con `python -m app.diagnostico`._\n")


def main() -> None:
    cfg = cargar()
    texto = a_markdown(hardware(), probar_llm(cfg, ClienteOllama(cfg.ollama_url, cfg.ollama_modelo, cfg.ollama_timeout_s)))
    salida = Path(RAIZ) / "docs" / "entorno_llm.md"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    print(texto + f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
