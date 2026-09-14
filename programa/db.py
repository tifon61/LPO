"""
Almacenamiento local (SQLite) de las observaciones cargadas desde este
programa. Cada fila tiene un estado de sincronización ('pendiente' o
'sincronizado') y una clave única (fecha, hora) que se usa tanto para
evitar duplicados locales como para conciliar con la Google Sheet.

También guarda si una observación fue "descartada" (con un motivo) en
vez de borrarla — así queda el rastro del dato crudo original. El
descarte tiene su propio estado de sincronización
(descarte_sync_status), separado del de la fila en sí, porque una fila
que ya estaba sincronizada hace rato puede descartarse recién ahora.
"""
import os
import sqlite3
from datetime import datetime, timezone

import rutas

DB_PATH = os.path.join(rutas.dir_datos(), "observaciones.db")

CAMPOS_ENTRADA = [
    "fecha", "hora", "observador", "t_seca", "t_humeda", "t_max", "t_min",
    "t_adjunto", "barometro", "t_seca_12h_antes", "lluvia",
]
CAMPOS_CALCULADOS = [
    "p_est_mmhg", "p_est_hpa", "pnm_mmhg", "pnm_hpa",
    "tension_vapor", "punto_rocio", "humedad_relativa",
]

# Columnas agregadas después de la primera versión de la base: se suman con
# ALTER TABLE si faltan, para no romper la base local de quien ya la tenía.
MIGRACIONES = {
    "observador": "TEXT NOT NULL DEFAULT ''",
    "descartada": "INTEGER NOT NULL DEFAULT 0",
    "motivo_descarte": "TEXT NOT NULL DEFAULT ''",
    "descartado_por": "TEXT NOT NULL DEFAULT ''",
    "descarte_sync_status": "TEXT NOT NULL DEFAULT 'sincronizado'",
}


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
                observador TEXT DEFAULT '',
                t_seca REAL, t_humeda REAL, t_max REAL, t_min REAL,
                t_adjunto REAL, barometro REAL, t_seca_12h_antes REAL, lluvia REAL,
                p_est_mmhg REAL, p_est_hpa REAL, pnm_mmhg REAL, pnm_hpa REAL,
                tension_vapor REAL, punto_rocio REAL, humedad_relativa REAL,
                cargado_el TEXT NOT NULL,
                origen TEXT NOT NULL DEFAULT 'local',
                sync_status TEXT NOT NULL DEFAULT 'pendiente',
                descartada INTEGER NOT NULL DEFAULT 0,
                motivo_descarte TEXT NOT NULL DEFAULT '',
                descartado_por TEXT NOT NULL DEFAULT '',
                descarte_sync_status TEXT NOT NULL DEFAULT 'sincronizado',
                UNIQUE(fecha, hora)
            )
            """
        )
        columnas_existentes = {row["name"] for row in conn.execute("PRAGMA table_info(observaciones)")}
        for columna, tipo in MIGRACIONES.items():
            if columna not in columnas_existentes:
                conn.execute(f"ALTER TABLE observaciones ADD COLUMN {columna} {tipo}")
        conn.commit()


def insertar_observacion(datos, origen="local", sync_status="pendiente"):
    """Inserta una observación. datos: dict con CAMPOS_ENTRADA + CAMPOS_CALCULADOS
    (y opcionalmente descartada/motivo_descarte/descartado_por, para cuando
    viene de la Sheet y ya llegó marcada como descartada).
    Devuelve True si insertó, False si ya existía una con la misma (fecha, hora)."""
    columnas = CAMPOS_ENTRADA + CAMPOS_CALCULADOS + [
        "cargado_el", "origen", "sync_status", "descartada", "motivo_descarte", "descartado_por",
    ]
    valores = [
        (datos.get(c) or "" if c == "observador" else datos.get(c))
        for c in CAMPOS_ENTRADA + CAMPOS_CALCULADOS
    ]
    valores += [
        datos.get("cargado_el") or datetime.now(timezone.utc).isoformat(),
        origen, sync_status,
        1 if datos.get("descartada") else 0,
        datos.get("motivo_descarte") or "",
        datos.get("descartado_por") or "",
    ]

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


def listar_para_grafico(limite=500):
    """Igual que listar_observaciones, pero en orden cronológico ascendente
    (más vieja a más nueva), como conviene para graficar una serie temporal."""
    with conectar() as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM observaciones ORDER BY fecha DESC, hora DESC LIMIT ?
            ) ORDER BY fecha ASC, hora ASC
            """,
            (limite,),
        ).fetchall()
        return [dict(r) for r in rows]


def contar_pendientes():
    with conectar() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM observaciones WHERE sync_status = 'pendiente'"
        ).fetchone()
        return row["n"]


def marcar_descarte(obs_id, descartada, motivo="", descartado_por=""):
    """Marca (o desmarca) una observación como descartada, con un motivo.
    No la borra: la fila sigue existiendo, con el dato crudo original."""
    with conectar() as conn:
        conn.execute(
            """
            UPDATE observaciones
            SET descartada = ?, motivo_descarte = ?, descartado_por = ?, descarte_sync_status = 'pendiente'
            WHERE id = ?
            """,
            (1 if descartada else 0, motivo if descartada else "", descartado_por if descartada else "", obs_id),
        )
        conn.commit()


def obtener_descartes_pendientes():
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM observaciones WHERE descarte_sync_status = 'pendiente' ORDER BY fecha, hora"
        ).fetchall()
        return [dict(r) for r in rows]


def marcar_descarte_sincronizado(obs_id):
    with conectar() as conn:
        conn.execute(
            "UPDATE observaciones SET descarte_sync_status = 'sincronizado' WHERE id = ?", (obs_id,)
        )
        conn.commit()


def actualizar_descarte_desde_remoto(fecha, hora, descartada, motivo, descartado_por=""):
    """Aplica el estado de descarte que ya está en la Sheet a la fila local
    correspondiente — pero solo si esa fila no tiene un cambio local propio
    todavía sin subir (para no pisarlo con un dato remoto desactualizado)."""
    with conectar() as conn:
        conn.execute(
            """
            UPDATE observaciones
            SET descartada = ?, motivo_descarte = ?, descartado_por = ?
            WHERE fecha = ? AND hora = ? AND descarte_sync_status = 'sincronizado'
            """,
            (1 if descartada else 0, motivo if descartada else "", descartado_por if descartada else "", fecha, hora),
        )
        conn.commit()
