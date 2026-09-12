"""
Almacenamiento local (SQLite) de las observaciones cargadas desde este
programa. Cada fila tiene un estado de sincronización ('pendiente' o
'sincronizado') y una clave única (fecha, hora) que se usa tanto para
evitar duplicados locales como para conciliar con la Google Sheet.
"""
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "observaciones.db")

CAMPOS_ENTRADA = [
    "fecha", "hora", "t_seca", "t_humeda", "t_max", "t_min",
    "t_adjunto", "barometro", "t_seca_12h_antes", "lluvia",
]
CAMPOS_CALCULADOS = [
    "p_est_mmhg", "p_est_hpa", "pnm_mmhg", "pnm_hpa",
    "tension_vapor", "punto_rocio", "humedad_relativa",
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
                t_seca REAL, t_humeda REAL, t_max REAL, t_min REAL,
                t_adjunto REAL, barometro REAL, t_seca_12h_antes REAL, lluvia REAL,
                p_est_mmhg REAL, p_est_hpa REAL, pnm_mmhg REAL, pnm_hpa REAL,
                tension_vapor REAL, punto_rocio REAL, humedad_relativa REAL,
                cargado_el TEXT NOT NULL,
                origen TEXT NOT NULL DEFAULT 'local',
                sync_status TEXT NOT NULL DEFAULT 'pendiente',
                UNIQUE(fecha, hora)
            )
            """
        )
        conn.commit()


def insertar_observacion(datos, origen="local", sync_status="pendiente"):
    """Inserta una observación. datos: dict con CAMPOS_ENTRADA + CAMPOS_CALCULADOS.
    Devuelve True si insertó, False si ya existía una con la misma (fecha, hora)."""
    columnas = CAMPOS_ENTRADA + CAMPOS_CALCULADOS + ["cargado_el", "origen", "sync_status"]
    valores = [datos.get(c) for c in CAMPOS_ENTRADA + CAMPOS_CALCULADOS]
    valores += [datos.get("cargado_el") or datetime.now(timezone.utc).isoformat(), origen, sync_status]

    placeholders = ", ".join(["?"] * len(columnas))
    sql = f"INSERT OR IGNORE INTO observaciones ({', '.join(columnas)}) VALUES ({placeholders})"
    with conectar() as conn:
        cur = conn.execute(sql, valores)
        conn.commit()
        return cur.rowcount > 0


def existe(fecha, hora):
    with conectar() as conn:
        row = conn.execute(
            "SELECT 1 FROM observaciones WHERE fecha = ? AND hora = ?", (fecha, hora)
        ).fetchone()
        return row is not None


def obtener_pendientes():
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM observaciones WHERE sync_status = 'pendiente' ORDER BY fecha, hora"
        ).fetchall()
        return [dict(r) for r in rows]


def marcar_sincronizada(obs_id):
    with conectar() as conn:
        conn.execute(
            "UPDATE observaciones SET sync_status = 'sincronizado' WHERE id = ?", (obs_id,)
        )
        conn.commit()


def listar_observaciones(limite=200):
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM observaciones ORDER BY fecha DESC, hora DESC LIMIT ?", (limite,)
        ).fetchall()
        return [dict(r) for r in rows]


def contar_pendientes():
    with conectar() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM observaciones WHERE sync_status = 'pendiente'"
        ).fetchone()
        return row["n"]
