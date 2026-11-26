"""Persistencia en SQLite: velas, decisiones, órdenes, patrimonio, errores y estado de la cartera.

Cada registro lleva `origen`: "vivo" (ciclos con la vela recién cerrada) o "replay" (ciclos sobre
velas históricas). Así la evidencia de replay queda marcada y nunca se mezcla con la operación en vivo.
La restricción UNIQUE(simbolo, fecha_vela, origen) impide decidir dos veces la misma vela.
"""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

ORIGENES = ("vivo", "replay")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS velas (
  simbolo TEXT, fecha TEXT, open REAL, high REAL, low REAL, close REAL, volumen REAL,
  PRIMARY KEY (simbolo, fecha));
CREATE TABLE IF NOT EXISTS decisiones (
  id INTEGER PRIMARY KEY AUTOINCREMENT, origen TEXT NOT NULL DEFAULT 'vivo', simbolo TEXT NOT NULL,
  fecha_vela TEXT NOT NULL, creado TEXT NOT NULL, cierre REAL, precio_ejecucion REAL, pronostico REAL,
  variables TEXT, respuesta_llm TEXT, latencia_s REAL, modelo_llm TEXT, accion_propuesta TEXT, justificacion TEXT,
  accion_final TEXT, aprobada INTEGER, motivo TEXT,
  UNIQUE (simbolo, fecha_vela, origen));
CREATE TABLE IF NOT EXISTS ordenes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, origen TEXT NOT NULL DEFAULT 'vivo', decision_id INTEGER REFERENCES decisiones(id),
  fecha_vela TEXT, creado TEXT, accion TEXT, precio REAL, cantidad REAL, costo REAL, modo TEXT DEFAULT 'PAPER');
CREATE TABLE IF NOT EXISTS patrimonio (
  id INTEGER PRIMARY KEY AUTOINCREMENT, origen TEXT NOT NULL DEFAULT 'vivo', creado TEXT, fecha_vela TEXT,
  efectivo REAL, cantidad REAL, precio REAL, patrimonio REAL);
CREATE TABLE IF NOT EXISTS errores (
  id INTEGER PRIMARY KEY AUTOINCREMENT, origen TEXT NOT NULL DEFAULT 'vivo', creado TEXT, etapa TEXT, tipo TEXT, mensaje TEXT);
CREATE TABLE IF NOT EXISTS estado (clave TEXT PRIMARY KEY, valor TEXT);
"""

EXPORTABLES = {
    "decisiones": "SELECT id, origen, simbolo, fecha_vela, creado, cierre, precio_ejecucion, pronostico, modelo_llm, "
                  "accion_propuesta, justificacion, accion_final, aprobada, motivo, latencia_s FROM decisiones "
                  "WHERE origen=? ORDER BY fecha_vela",
    "ordenes": "SELECT * FROM ordenes WHERE origen=? ORDER BY id",
    "patrimonio": "SELECT * FROM patrimonio WHERE origen=? ORDER BY id",
    "errores": "SELECT * FROM errores WHERE origen=? ORDER BY id",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BD:
    def __init__(self, ruta: str):
        if ruta != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._con.executescript(ESQUEMA)
            columnas = {r[1] for r in self._con.execute("PRAGMA table_info(ordenes)")}
            if "mexc_prueba" not in columnas:                # migración: bases creadas antes de v0.3
                self._con.execute("ALTER TABLE ordenes ADD COLUMN mexc_prueba TEXT")

    def _ex(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock, self._con:
            return self._con.execute(sql, params)

    def _todos(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._con.execute(sql, params).fetchall()]

    # --- escritura ---
    def guardar_velas(self, simbolo: str, velas) -> None:
        with self._lock, self._con:
            self._con.executemany("INSERT OR REPLACE INTO velas VALUES (?,?,?,?,?,?,?)",
                                  [(simbolo, v.fecha, v.open, v.high, v.low, v.close, v.volumen) for v in velas])

    def existe_decision(self, simbolo: str, fecha_vela: str, origen: str = "vivo") -> bool:
        return bool(self._todos("SELECT 1 FROM decisiones WHERE simbolo=? AND fecha_vela=? AND origen=?",
                                (simbolo, fecha_vela, origen)))

    def guardar_decision(self, d: dict) -> int | None:
        """Devuelve el id, o None si ya existía una decisión para esa vela (evento duplicado)."""
        cols = ["origen", "simbolo", "fecha_vela", "creado", "cierre", "precio_ejecucion", "pronostico", "variables",
                "respuesta_llm", "latencia_s", "modelo_llm", "accion_propuesta", "justificacion", "accion_final",
                "aprobada", "motivo"]
        d = {"origen": "vivo", **d, "creado": ahora(), "variables": json.dumps(d.get("variables", {}))}
        try:
            cur = self._ex(f"INSERT INTO decisiones ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                           tuple(d.get(c) for c in cols))
        except sqlite3.IntegrityError:
            return None
        return cur.lastrowid

    def guardar_orden(self, decision_id: int, fecha_vela: str, accion: str, precio: float, cantidad: float,
                      costo: float, origen: str = "vivo") -> int:
        cur = self._ex("INSERT INTO ordenes (origen, decision_id, fecha_vela, creado, accion, precio, cantidad, costo) "
                       "VALUES (?,?,?,?,?,?,?,?)", (origen, decision_id, fecha_vela, ahora(), accion, precio, cantidad, costo))
        return cur.lastrowid

    def marcar_prueba_mexc(self, orden_id: int, resultado: str) -> None:
        self._ex("UPDATE ordenes SET mexc_prueba=? WHERE id=?", (resultado[:300], orden_id))

    def guardar_patrimonio(self, fecha_vela: str, efectivo: float, cantidad: float, precio: float,
                           origen: str = "vivo") -> None:
        self._ex("INSERT INTO patrimonio (origen, creado, fecha_vela, efectivo, cantidad, precio, patrimonio) "
                 "VALUES (?,?,?,?,?,?,?)", (origen, ahora(), fecha_vela, efectivo, cantidad, precio, efectivo + cantidad * precio))

    def error(self, etapa: str, exc: BaseException | str, origen: str = "vivo") -> None:
        tipo = type(exc).__name__ if isinstance(exc, BaseException) else "Aviso"
        self._ex("INSERT INTO errores (origen, creado, etapa, tipo, mensaje) VALUES (?,?,?,?,?)",
                 (origen, ahora(), etapa, tipo, str(exc)[:500]))

    def guardar_estado(self, clave: str, valor: dict) -> None:
        self._ex("INSERT OR REPLACE INTO estado VALUES (?,?)", (clave, json.dumps(valor)))

    def borrar_origen(self, origen: str) -> None:
        """Limpia una corrida (se usa antes de repetir un replay)."""
        with self._lock, self._con:
            for t in ("ordenes", "patrimonio", "errores", "decisiones"):
                self._con.execute(f"DELETE FROM {t} WHERE origen=?", (origen,))
            self._con.execute("DELETE FROM estado WHERE clave=?", (f"cartera_{origen}",))

    # --- lectura ---
    def leer_estado(self, clave: str) -> dict | None:
        r = self._todos("SELECT valor FROM estado WHERE clave=?", (clave,))
        return json.loads(r[0]["valor"]) if r else None

    def decisiones(self, n: int = 30, origen: str = "vivo") -> list[dict]:
        return self._todos("SELECT * FROM decisiones WHERE origen=? ORDER BY fecha_vela DESC, id DESC LIMIT ?", (origen, n))

    def decisiones_cronologicas(self, origen: str) -> list[dict]:
        return self._todos("SELECT * FROM decisiones WHERE origen=? ORDER BY fecha_vela", (origen,))

    def ordenes(self, n: int = 30, origen: str = "vivo") -> list[dict]:
        return self._todos("SELECT * FROM ordenes WHERE origen=? ORDER BY id DESC LIMIT ?", (origen, n))

    def errores(self, n: int = 30, origen: str = "vivo") -> list[dict]:
        return self._todos("SELECT * FROM errores WHERE origen=? ORDER BY id DESC LIMIT ?", (origen, n))

    def curva_patrimonio(self, n: int = 365, origen: str = "vivo") -> list[dict]:
        return self._todos("SELECT fecha_vela, patrimonio FROM patrimonio WHERE origen=? ORDER BY id DESC LIMIT ?",
                           (origen, n))[::-1]

    def velas_guardadas(self, simbolo: str, n: int = 120) -> list[dict]:
        return self._todos("SELECT fecha, open, high, low, close FROM velas WHERE simbolo=? ORDER BY fecha DESC LIMIT ?",
                           (simbolo, n))[::-1]

    def metricas(self, origen: str = "vivo") -> dict:
        d = self._todos("SELECT COUNT(*) AS ciclos, AVG(latencia_s) AS latencia_media, MAX(latencia_s) AS latencia_max, "
                        "SUM(CASE WHEN accion_propuesta IS NULL THEN 1 ELSE 0 END) AS sin_propuesta_valida, "
                        "SUM(CASE WHEN aprobada = 0 THEN 1 ELSE 0 END) AS rechazadas "
                        "FROM decisiones WHERE origen=?", (origen,))[0]
        d["operaciones"] = self._todos("SELECT COUNT(*) AS n FROM ordenes WHERE origen=?", (origen,))[0]["n"]
        d["errores"] = self._todos("SELECT COUNT(*) AS n FROM errores WHERE origen=?", (origen,))[0]["n"]
        d["pct_rechazadas"] = (d["rechazadas"] or 0) / d["ciclos"] if d["ciclos"] else None
        return d

    def exportar_csv(self, tabla: str, origen: str = "vivo") -> str:
        if tabla not in EXPORTABLES:
            raise KeyError(tabla)
        with self._lock:
            cur = self._con.execute(EXPORTABLES[tabla], (origen,))
            salida = io.StringIO()
            w = csv.writer(salida)
            w.writerow([c[0] for c in cur.description])
            w.writerows(cur.fetchall())
        return salida.getvalue()
