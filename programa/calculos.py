"""
Motor de cálculo de variables meteorológicas derivadas (tipo SYNOP).
Port directo de observaciones/calculos.js — mismas fórmulas, mismas
constantes y misma Tabla D-4. Si cambiás algo en un lado, replicalo acá.
"""
import math

ESTACION = {
    "latitud": -34.9,
    "elevacion": 15,  # metros
    # Gravedad local (fórmula internacional de gravedad para latitud -34.9°) vs. estándar.
    "gravedad_local": 9.797207,
    "gravedad_estandar": 9.80665,
}

# Tabla D-4 del SMN (Oficina de Cálculos Generales), específica de esta
# estación (La Plata — latitud 34°55', altura 14.97 m): valores a SUMAR a
# la presión de estación (ya corregida) para obtener la presión a nivel
# del mar.
TABLA_D4 = [
    # (t_min, t_max, c730, c760)
    # c730: columna "730.00 a 759.99 mmHg" · c760: columna "760.00 a 789.99 mmHg"
    (-10.0, -0.1, 1.4, 1.5),
    (0.0, 9.9, 1.4, 1.4),
    (10.0, 19.9, 1.3, 1.4),
    (20.0, 29.9, 1.3, 1.3),
    (30.0, 39.9, 1.2, 1.3),
    (40.0, 49.9, 1.2, 1.2),
]


def presion_estacion_mmhg(barometro, t_adjunto):
    c_t = -barometro * 0.000163 * t_adjunto
    b0 = barometro + c_t
    return b0 * (ESTACION["gravedad_local"] / ESTACION["gravedad_estandar"])


def mmhg_a_hpa(mmhg):
    return mmhg * (4.0 / 3.0)


def tension_vapor_hpa(t_seca, t_humeda, p_estacion_hpa):
    es_humeda = 6.112 * math.exp((17.67 * t_humeda) / (t_humeda + 243.5))
    a = 0.0008
    e = es_humeda - a * p_estacion_hpa * (t_seca - t_humeda)
    return max(0, e)


def punto_rocio(e_hpa):
    if e_hpa <= 0:
        return 0.0
    numerador = math.log(e_hpa / 6.112) * 243.5
    denominador = 17.67 - math.log(e_hpa / 6.112)
    return numerador / denominador


def humedad_relativa(e_hpa, t_seca):
    es_seca = 6.112 * math.exp((17.67 * t_seca) / (t_seca + 243.5))
    hr = (e_hpa / es_seca) * 100
    return max(0, min(hr, 100))


def correccion_d4(t_promedio, p_est_mmhg):
    fila = None
    for t_min, t_max, c730, c760 in TABLA_D4:
        if t_min <= t_promedio <= t_max:
            fila = (t_min, t_max, c730, c760)
            break
    if fila is None:
        fila = TABLA_D4[0] if t_promedio < TABLA_D4[0][0] else TABLA_D4[-1]
    _, _, c730, c760 = fila
    return c730 if p_est_mmhg < 760.0 else c760


# Rangos físicamente razonables para esta estación (La Plata). No son los
# extremos absolutos posibles — son un colchón generoso pensado para atajar
# errores de tipeo (ej. "225" en vez de "22.5"), no para rechazar lecturas
# reales raras.
RANGOS = {
    "t_seca": (-15, 45, "T. Bulbo Seco"),
    "t_humeda": (-15, 45, "T. Bulbo Húmedo"),
    "t_max": (-15, 45, "T. Máx"),
    "t_min": (-15, 45, "T. Mín"),
    "t_adjunto": (-15, 45, "T. Adjunto"),
    "t_seca_12h_antes": (-15, 45, "T. Bulbo Seco 12hs antes"),
    "barometro": (700, 800, "Barómetro"),
    "lluvia": (0, 500, "Lluvia"),
}

# Esta estación solo toma observaciones a las tres horas sinópticas
# (12, 18 y 00 UTC), en hora local de Argentina (UTC-3).
HORAS_VALIDAS = ("09:00", "15:00", "21:00")


def validar_observacion(entrada):
    """Valida una observación antes de calcular/guardar. entrada: mismas
    claves que RANGOS (los campos opcionales pueden faltar o venir None).
    Devuelve una lista de mensajes de error (vacía si está todo bien)."""
    errores = []
    for campo, (minimo, maximo, etiqueta) in RANGOS.items():
        valor = entrada.get(campo)
        if valor is None:
            continue
        if not isinstance(valor, (int, float)):
            errores.append(f"{etiqueta}: no es un número válido.")
            continue
        if valor < minimo or valor > maximo:
            errores.append(f"{etiqueta} fuera de rango razonable (entre {minimo} y {maximo}). Revisá si hay un error de tipeo.")

    t_seca = entrada.get("t_seca")
    t_humeda = entrada.get("t_humeda")
    if isinstance(t_seca, (int, float)) and isinstance(t_humeda, (int, float)) and t_humeda > t_seca + 0.05:
        errores.append("La T. Bulbo Húmedo no puede ser mayor que la T. Bulbo Seco.")
    t_max = entrada.get("t_max")
    if isinstance(t_seca, (int, float)) and isinstance(t_max, (int, float)) and t_max < t_seca - 0.05:
        errores.append("La T. Máx no puede ser menor que la T. Bulbo Seco actual.")
    t_min = entrada.get("t_min")
    if isinstance(t_seca, (int, float)) and isinstance(t_min, (int, float)) and t_min > t_seca + 0.05:
        errores.append("La T. Mín no puede ser mayor que la T. Bulbo Seco actual.")
    hora = entrada.get("hora")
    if hora and hora not in HORAS_VALIDAS:
        errores.append(f"La hora debe ser una de las tres observaciones sinópticas: {', '.join(HORAS_VALIDAS)}.")

    return errores


def calcular_observacion(entrada):
    """
    entrada: dict con t_seca, t_humeda, t_adjunto, barometro (obligatorios,
    números) y opcionalmente t_seca_12h_antes (si falta, se usa t_seca).
    Devuelve un dict con todas las variables derivadas.
    """
    p_est_mmhg = presion_estacion_mmhg(entrada["barometro"], entrada["t_adjunto"])
    p_est_hpa = mmhg_a_hpa(p_est_mmhg)
    tv = tension_vapor_hpa(entrada["t_seca"], entrada["t_humeda"], p_est_hpa)
    pr = punto_rocio(tv)
    hr = humedad_relativa(tv, entrada["t_seca"])

    t_seca_12h = entrada.get("t_seca_12h_antes")
    if t_seca_12h is None:
        t_seca_12h = entrada["t_seca"]
    t_promedio = (entrada["t_seca"] + t_seca_12h) / 2
    corr_d4 = correccion_d4(t_promedio, p_est_mmhg)
    pnm_mmhg = p_est_mmhg + corr_d4
    pnm_hpa = mmhg_a_hpa(pnm_mmhg)

    # Redondeado a 1 decimal: evita guardar el resultado crudo de la cuenta
    # en punto flotante (con 8-10 decimales de ruido) en la base local/Sheet.
    return {
        "p_est_mmhg": round(p_est_mmhg, 1),
        "p_est_hpa": round(p_est_hpa, 1),
        "tension_vapor": round(tv, 1),
        "punto_rocio": round(pr, 1),
        "humedad_relativa": round(hr, 1),
        "pnm_mmhg": round(pnm_mmhg, 1),
        "pnm_hpa": round(pnm_hpa, 1),
    }
