"""
Sincronización con la misma Google Sheet que usa la página web:
- subir(): manda las observaciones locales pendientes al Web App (POST),
  y después los cambios de descarte pendientes (marcar/desmarcar).
- bajar(): trae el histórico completo de la Sheet (GET), inserta local
  las observaciones que todavía no existan (por fecha+hora), y actualiza
  el estado de descarte de las que ya tenía si cambió del lado remoto.
"""
import requests

import config
import db

TIMEOUT_SEGUNDOS = 15

# Mapeo columnas locales (snake_case) <-> claves que espera/devuelve Apps Script (camelCase)
CLAVES_REMOTAS = {
    "fecha": "fecha", "hora": "hora", "observador": "observador",
    "t_seca": "tSeca", "t_humeda": "tHumeda", "t_max": "tMax", "t_min": "tMin",
    "t_adjunto": "tAdjunto", "barometro": "barometro",
    "t_seca_12h_antes": "tSeca12hAntes", "lluvia": "lluvia",
    "p_est_mmhg": "pEstMmhg", "p_est_hpa": "pEstHpa",
    "pnm_mmhg": "pnmMmhg", "pnm_hpa": "pnmHpa",
    "tension_vapor": "tensionVapor", "punto_rocio": "puntoRocio",
    "humedad_relativa": "humedadRelativa",
    "descartada": "descartada", "motivo_descarte": "motivoDescarte", "descartado_por": "descartadoPor",
}


def _a_remoto(fila_local):
    payload = {remoto: fila_local.get(local) for local, remoto in CLAVES_REMOTAS.items()}
    payload["token"] = config.cargar()["apps_script_token"]
    return payload


def _de_remoto(fila_remota):
    fila_local = {local: fila_remota.get(remoto) for local, remoto in CLAVES_REMOTAS.items()}
    return fila_local


def subir():
    """Sube las observaciones pendientes y, después, los cambios de descarte
    pendientes. Devuelve cuántas observaciones nuevas subió (los descartes se
    cuentan aparte). Lanza una excepción si no hay conexión o el servidor
    responde error."""
    cfg = config.cargar()
    pendientes = db.obtener_pendientes()
    subidas = 0
    for fila in pendientes:
        resp = requests.post(
            cfg["apps_script_url"],
            json=_a_remoto(fila),
            timeout=TIMEOUT_SEGUNDOS,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Apps Script rechazó la observación {fila['fecha']} {fila['hora']}: {data.get('error')}")
        db.marcar_sincronizada(fila["id"])
        subidas += 1

    subir_descartes()
    return subidas


def subir_descartes():
    """Sube los cambios de descarte pendientes (marcar o desmarcar una
    observación ya existente). Devuelve cuántos subió. Se corre después de
    subir observaciones nuevas, por si una recién subida también se
    descartó antes de sincronizar."""
    cfg = config.cargar()
    pendientes = db.obtener_descartes_pendientes()
    subidos = 0
    for fila in pendientes:
        payload = {
            "accion": "marcar_descarte",
            "fecha": fila["fecha"],
            "hora": fila["hora"],
            "descartada": bool(fila["descartada"]),
            "motivo": fila["motivo_descarte"],
            "descartadoPor": fila["descartado_por"],
            "token": cfg["apps_script_token"],
        }
        resp = requests.post(cfg["apps_script_url"], json=payload, timeout=TIMEOUT_SEGUNDOS)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Apps Script rechazó el descarte de {fila['fecha']} {fila['hora']}: {data.get('error')}")
        db.marcar_descarte_sincronizado(fila["id"])
        subidos += 1
    return subidos


def bajar():
    """Trae el histórico remoto, inserta local lo que falte, y actualiza el
    estado de descarte de lo que ya tenía si cambió del lado remoto (por
    ejemplo, se descartó desde la web). Devuelve cuántas observaciones
    nuevas bajó."""
    cfg = config.cargar()
    resp = requests.get(
        cfg["apps_script_url"],
        params={"token": cfg["apps_script_token"]},
        timeout=TIMEOUT_SEGUNDOS,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Apps Script no pudo devolver el histórico: {data.get('error')}")

    bajadas = 0
    for fila_remota in data.get("filas", []):
        fila_local = _de_remoto(fila_remota)
        if not fila_local.get("fecha") or not fila_local.get("hora"):
            continue
        insertada = db.insertar_observacion(fila_local, origen="remoto", sync_status="sincronizado")
        if insertada:
            bajadas += 1
        else:
            db.actualizar_descarte_desde_remoto(
                fila_local["fecha"], fila_local["hora"],
                bool(fila_local.get("descartada")),
                fila_local.get("motivo_descarte") or "",
                fila_local.get("descartado_por") or "",
            )
    return bajadas


def sincronizar_todo():
    """Sube lo pendiente (observaciones + descartes) y despues baja lo que
    falte. Devuelve (subidas, bajadas)."""
    subidas = subir()
    bajadas = bajar()
    return subidas, bajadas
