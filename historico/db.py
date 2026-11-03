"""
Almacenamiento local (SQLite) del archivo histórico importado desde los
Excel anuales. Una sola tabla, una fila por observación (fecha+hora),
re-importable sin duplicar (INSERT OR REPLACE por fecha+hora: si se
corrige un dato en el Excel y se vuelve a importar, se actualiza).
"""
import os
import sqlite3

import rutas

DB_PATH = os.path.join(rutas.dir_datos(), "historico.db")

# Nombre de columna (en la base) -> título legible (para la tabla/CSV).
COLUMNAS = [
    ("fecha", "Fecha"), ("hora", "Hora"),
    ("t_seco", "T. Seco"), ("t_humedo", "T. Húmedo"),
    ("t_max", "T. Máx"), ("t_min", "T. Mín"),
    ("punto_rocio", "P. Rocío"), ("tension_vapor", "T. Vapor"),
    ("humedad_relativa", "H.R."), ("t_adjunto", "T. Adjunto"),
    ("barometro", "Barómetro"), ("p_n_estacion", "P.N. Estación"),
    ("p_n_mar", "P.N. Mar"), ("pnm_hpa", "P.N.M. (hPa)"),
    ("lluvia", "Lluvia"),
]


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar():
    with conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS observaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                t_seco REAL, t_humedo REAL, t_max REAL, t_min REAL,
                punto_rocio REAL, tension_vapor REAL, humedad_relativa REAL,
                t_adjunto REAL, barometro REAL,
                p_n_estacion REAL, p_n_mar REAL, pnm_hpa REAL, lluvia REAL,
                hora_verificacion TEXT,
                acum_diario_fecha TEXT, acum_diario_mm REAL,
                archivo_origen TEXT NOT NULL,
                fila_origen INTEGER NOT NULL,
                UNIQUE(fecha, hora)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fecha ON observaciones(fecha)")
        conn.commit()


CAMPOS_FILA = [
    "fecha", "hora", "t_seco", "t_humedo", "t_max", "t_min",
    "punto_rocio", "tension_vapor", "humedad_relativa", "t_adjunto",
    "barometro", "p_n_estacion", "p_n_mar", "pnm_hpa", "lluvia",
    "hora_verificacion", "acum_diario_fecha", "acum_diario_mm",
    "archivo_origen", "fila_origen",
]


def upsert_observacion(fila):
    """Inserta una observación, o la reemplaza si ya existía una con la
    misma fecha+hora (permite reimportar un Excel corregido sin duplicar)."""
    columnas = CAMPOS_FILA
    valores = [fila.get(c) for c in columnas]
    placeholders = ", ".join(["?"] * len(columnas))
    sql = f"INSERT OR REPLACE INTO observaciones ({', '.join(columnas)}) VALUES ({placeholders})"
    with conectar() as conn:
        conn.execute(sql, valores)
        conn.commit()


def upsert_muchas(filas):
    """Igual que upsert_observacion pero en una sola transacción, mucho más
    rápido para importar un año entero (miles de filas) de una vez."""
    columnas = CAMPOS_FILA
    placeholders = ", ".join(["?"] * len(columnas))
    sql = f"INSERT OR REPLACE INTO observaciones ({', '.join(columnas)}) VALUES ({placeholders})"
    with conectar() as conn:
        conn.executemany(sql, [[fila.get(c) for c in columnas] for fila in filas])
        conn.commit()


def contar():
    with conectar() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM observaciones").fetchone()["n"]


def rango_fechas():
    """(fecha_min, fecha_max) de todo lo importado, o (None, None) si está vacío."""
    with conectar() as conn:
        row = conn.execute("SELECT MIN(fecha) AS min, MAX(fecha) AS max FROM observaciones").fetchone()
        return row["min"], row["max"]


def listar_periodo(fecha_desde, fecha_hasta):
    """Todas las observaciones entre dos fechas (inclusive), en orden
    cronológico — para graficar o exportar un período."""
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM observaciones WHERE fecha >= ? AND fecha <= ? ORDER BY fecha ASC, hora ASC",
            (fecha_desde, fecha_hasta),
        ).fetchall()
        return [dict(r) for r in rows]
