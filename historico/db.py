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


# ---------- Extremos, climatología e informes ----------
# Columnas numéricas válidas para estas consultas (se arma la SQL con el
# nombre de columna interpolado, así que solo se acepta uno de esta lista
# — nunca texto que venga directo de la interfaz).
COLUMNAS_NUMERICAS = {
    "t_seco", "t_humedo", "t_max", "t_min", "punto_rocio", "tension_vapor",
    "humedad_relativa", "t_adjunto", "barometro", "p_n_estacion", "p_n_mar",
    "pnm_hpa", "lluvia", "acum_diario_mm",
}

# Variables "extensivas": lo que importa es el total acumulado del período,
# no el promedio de cada lectura suelta (a diferencia de temperatura,
# presión, humedad, etc., que sí se promedian).
VARIABLES_EXTENSIVAS = {"lluvia", "acum_diario_mm"}

MESES_NOMBRE = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
ESTACIONES_NOMBRE = ["Verano", "Otoño", "Invierno", "Primavera"]


def _validar_columna(variable):
    if variable not in COLUMNAS_NUMERICAS:
        raise ValueError(f"Variable desconocida: {variable}")


def _estacion_de_mes(mes):
    """0=Verano, 1=Otoño, 2=Invierno, 3=Primavera (hemisferio sur)."""
    if mes in (12, 1, 2):
        return 0
    if mes in (3, 4, 5):
        return 1
    if mes in (6, 7, 8):
        return 2
    return 3


def _anio_estacion(anio, mes):
    """Diciembre cuenta para el verano del año que empieza en enero
    siguiente (ej. dic 1990 es parte del "Verano 1991")."""
    return anio + 1 if mes == 12 else anio


def extremos(variable, fecha_desde, fecha_hasta, n=10):
    """(máximos, mínimos): hasta n filas {fecha, hora, v} cada una, ordenadas
    de más extremo a menos, para una variable en un período."""
    _validar_columna(variable)
    with conectar() as conn:
        maximos = conn.execute(
            f"SELECT fecha, hora, {variable} AS v FROM observaciones "
            f"WHERE {variable} IS NOT NULL AND fecha >= ? AND fecha <= ? "
            f"ORDER BY v DESC, fecha ASC LIMIT ?",
            (fecha_desde, fecha_hasta, n),
        ).fetchall()
        minimos = conn.execute(
            f"SELECT fecha, hora, {variable} AS v FROM observaciones "
            f"WHERE {variable} IS NOT NULL AND fecha >= ? AND fecha <= ? "
            f"ORDER BY v ASC, fecha ASC LIMIT ?",
            (fecha_desde, fecha_hasta, n),
        ).fetchall()
        return [dict(r) for r in maximos], [dict(r) for r in minimos]


def _filas_variable(variable, conn):
    return conn.execute(
        f"SELECT fecha, {variable} AS v FROM observaciones WHERE {variable} IS NOT NULL ORDER BY fecha"
    ).fetchall()


def _agrupar(variable, fn_clave):
    """Suma o promedia (según VARIABLES_EXTENSIVAS) las lecturas de cada
    (año, mes) real, y después junta esos valores por el grupo que arme
    fn_clave(año, mes) -> (grupo, año_del_período). Devuelve
    {grupo: [(año_período, valor), ...]}."""
    _validar_columna(variable)
    es_extensiva = variable in VARIABLES_EXTENSIVAS
    acumulado = {}  # (grupo, año_período) -> [suma, cuenta]
    with conectar() as conn:
        filas = _filas_variable(variable, conn)
    for r in filas:
        anio, mes = int(r["fecha"][:4]), int(r["fecha"][5:7])
        clave = fn_clave(anio, mes)
        suma, cuenta = acumulado.get(clave, (0.0, 0))
        acumulado[clave] = (suma + r["v"], cuenta + 1)

    por_grupo = {}
    for (grupo, anio_periodo), (suma, cuenta) in acumulado.items():
        valor = suma if es_extensiva else suma / cuenta
        por_grupo.setdefault(grupo, []).append((anio_periodo, valor))
    return por_grupo


def _resumen_por_grupo(por_grupo, grupos_orden, etiquetas):
    resultado = []
    for grupo, etiqueta in zip(grupos_orden, etiquetas):
        datos = sorted(por_grupo.get(grupo, []))
        if not datos:
            resultado.append({
                "grupo": grupo, "etiqueta": etiqueta, "n_anios": 0, "promedio": None,
                "maximo": None, "anio_maximo": None, "minimo": None, "anio_minimo": None,
            })
            continue
        valores = [v for _a, v in datos]
        anio_max, valor_max = max(datos, key=lambda t: t[1])
        anio_min, valor_min = min(datos, key=lambda t: t[1])
        resultado.append({
            "grupo": grupo, "etiqueta": etiqueta, "n_anios": len(datos),
            "promedio": sum(valores) / len(valores),
            "maximo": valor_max, "anio_maximo": anio_max,
            "minimo": valor_min, "anio_minimo": anio_min,
        })
    return resultado


def climatologia_mensual(variable):
    """Para cada mes del año (independiente del año calendario): promedio
    histórico (o total, si es una variable extensiva como lluvia) de ese
    mes a lo largo de todos los años cargados, más el año con el valor más
    alto y el año con el valor más bajo."""
    por_grupo = _agrupar(variable, lambda anio, mes: (mes, anio))
    return _resumen_por_grupo(por_grupo, list(range(1, 13)), MESES_NOMBRE)


def climatologia_estacional(variable):
    """Igual que climatologia_mensual pero agrupado de a 3 meses
    (Verano/Otoño/Invierno/Primavera, hemisferio sur)."""
    def clave(anio, mes):
        return _estacion_de_mes(mes), _anio_estacion(anio, mes)

    por_grupo = _agrupar(variable, clave)
    return _resumen_por_grupo(por_grupo, list(range(4)), ESTACIONES_NOMBRE)


def resumen_estacion_puntual(variable, estacion_idx, anio_periodo):
    """Promedio (o total) de 'variable' en una estación del año puntual —
    ej. Invierno 2025 — para compararlo contra el histórico de
    climatologia_estacional. None si no hay datos cargados para ese
    período."""
    _validar_columna(variable)
    es_extensiva = variable in VARIABLES_EXTENSIVAS
    suma, cuenta = 0.0, 0
    with conectar() as conn:
        filas = _filas_variable(variable, conn)
    for r in filas:
        anio, mes = int(r["fecha"][:4]), int(r["fecha"][5:7])
        if _estacion_de_mes(mes) == estacion_idx and _anio_estacion(anio, mes) == anio_periodo:
            suma += r["v"]
            cuenta += 1
    if cuenta == 0:
        return None
    return suma if es_extensiva else suma / cuenta
