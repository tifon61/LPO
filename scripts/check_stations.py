#!/usr/bin/env python3
"""
Chequea la red de estaciones meteorológicas (ThingSpeak / Wunderground) de
"¿Cómo está el tiempo en tu escuela?" y arma/actualiza data/stations-monitor.json
con el historial de caídas de cada una. Lo corre GitHub Actions cada 15 minutos.

Se considera "caída" cuando:
- la API no responde o devuelve un error, o
- no hay ninguna lectura con menos de STALE_MINUTES minutos de antigüedad
  (mismo umbral de 120 min que usa la propia página para marcar el punto en rojo).

Solo se listan acá las estaciones marcadas "live: true" en la página de la red
(ver puntos[] en esa página). Monte Veloz y EP N°34 están apagadas a propósito,
así que no se chequean.
"""
import json
import os
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import certifi

STALE_MINUTES = 120
MAX_INCIDENTS_KEPT = 200

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "stations-monitor.json")

CALLMEBOT_PHONE = os.environ.get("CALLMEBOT_PHONE")
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY")

STATIONS = [
    {
        "key": "bavio",
        "name": "EP N°23 (Bavío / EMA Violeta)",
        "type": "thingspeak",
        "channels": [
            {"id": "2626952", "key": "4XYH56YSV64HE17H"},
            {"id": "1778165", "key": "OJ1JHKAPCCIQB4CB"},
        ],
        # El pluviómetro y el sensor de temp/humedad pueden fallar por separado
        # (son piezas de hardware distintas en la ESP32), así que se chequean
        # como dos señales independientes en vez de mirar solo la fila más
        # reciente del canal.
        "signals": [
            {"suffix": "temp_hum", "field": "field1", "label": "Temp/Humedad"},
            {"suffix": "pluvio", "field": "field5", "label": "Pluviómetro"},
        ],
    },
    {
        "key": "san_vicente",
        "name": "San Vicente (La Plata)",
        "type": "thingspeak",
        "channels": [{"id": "2218687", "key": "TH3V4TJLRFZD3JSG"}],
    },
    {
        "key": "ema_blanca",
        "name": "EMA Blanca",
        "type": "thingspeak",
        "channels": [{"id": "2218689", "key": "ZLNOSLZJPQM3H7SD"}],
    },
    {
        "key": "observatorio",
        "name": "Observatorio (Facultad · Campbell)",
        "type": "thingspeak",
        "channels": [{"id": "2823820", "key": "FFI1HK80ZKDNS6V8"}],
    },
    {
        "key": "ema_verde",
        "name": "EMA Verde (Facultad, en prueba)",
        "type": "thingspeak",
        "channels": [{"id": "2218686", "key": "O85A0DJ31L8MQZ6F"}],
    },
    {
        "key": "daza",
        "name": "Daza (Facultad · Wunderground)",
        "type": "wunderground",
        "wu_id": "ILAPLA66",
        "wu_key": "470147c769f6493f8147c769f6693fd9",
    },
    {
        "key": "es7_ep20",
        "name": "ES7 / EP20",
        "type": "wunderground",
        "wu_id": "ILOSTA2",
        "wu_key": "f1d7143d25a24b7197143d25a23b711d",
    },
    {
        "key": "ep23_los_talas",
        "name": "EP N°23 (Los Talas, Berisso)",
        "type": "wunderground",
        "wu_id": "IBERIS14",
        "wu_key": "af815b5b4b804cfd815b5b4b80dcfd07",
    },
]


def ssl_context():
    return ssl.create_default_context(cafile=certifi.where())


def http_get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "pronostico-unlp-monitor"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def check_thingspeak(station):
    latest_dt = None
    try:
        for ch in station["channels"]:
            url = (
                f"https://api.thingspeak.com/channels/{ch['id']}/feeds.json"
                f"?results=1&api_key={ch['key']}"
            )
            data = http_get_json(url)
            feeds = data.get("feeds") or []
            if not feeds:
                continue
            created_at = feeds[-1].get("created_at")
            if not created_at:
                continue
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if latest_dt is None or dt > latest_dt:
                latest_dt = dt
    except Exception as e:
        return "down", f"No se pudo conectar: {e}", None

    if latest_dt is None:
        return "down", "Sin lecturas en el canal", None
    return _status_from_timestamp(latest_dt)


def check_thingspeak_signals(station):
    """Como check_thingspeak, pero devuelve el estado de cada señal (campo)
    por separado en vez de uno solo para todo el canal: busca, para cada
    campo pedido, la lectura no vacía más reciente entre las últimas filas."""
    last_valid = {s["suffix"]: None for s in station["signals"]}
    try:
        for ch in station["channels"]:
            url = (
                f"https://api.thingspeak.com/channels/{ch['id']}/feeds.json"
                f"?results=100&api_key={ch['key']}"
            )
            data = http_get_json(url)
            feeds = data.get("feeds") or []
            for signal in station["signals"]:
                field = signal["field"]
                for f in reversed(feeds):
                    val = f.get(field)
                    if val is None or val == "":
                        continue
                    try:
                        float(val)
                    except (TypeError, ValueError):
                        continue
                    created_at = f.get("created_at")
                    if not created_at:
                        continue
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    suf = signal["suffix"]
                    if last_valid[suf] is None or dt > last_valid[suf]:
                        last_valid[suf] = dt
                    break
    except Exception as e:
        return {s["suffix"]: ("down", f"No se pudo conectar: {e}", None) for s in station["signals"]}

    results = {}
    for signal in station["signals"]:
        suf = signal["suffix"]
        dt = last_valid[suf]
        if dt is None:
            results[suf] = ("down", f"Sin lecturas de {signal['label']}", None)
        else:
            results[suf] = _status_from_timestamp(dt)
    return results


def check_wunderground(station):
    url = (
        "https://api.weather.com/v2/pws/observations/current"
        f"?stationId={station['wu_id']}&format=json&units=e&apiKey={station['wu_key']}"
    )
    try:
        data = http_get_json(url)
        observations = data.get("observations") or []
        if not observations:
            return "down", "Sin observaciones de Wunderground", None
        raw_ts = observations[0].get("obsTimeUtc") or observations[0].get("obsTimeLocal")
        if not raw_ts:
            return "down", "Sin timestamp en la observación", None
        dt = datetime.fromisoformat(raw_ts.replace(" ", "T").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception as e:
        return "down", f"No se pudo conectar: {e}", None

    return _status_from_timestamp(dt)


def _status_from_timestamp(dt):
    now = datetime.now(timezone.utc)
    age_minutes = (now - dt.astimezone(timezone.utc)).total_seconds() / 60
    dt_iso = dt.astimezone(timezone.utc).isoformat()
    if age_minutes > STALE_MINUTES:
        return "down", f"Sin datos nuevos hace {_fmt_age(age_minutes)}", dt_iso
    return "up", None, dt_iso


def _fmt_age(minutes):
    if minutes < 120:
        return f"{minutes:.0f} min"
    return f"{minutes / 60:.1f}h"


def check_station(station):
    if station["type"] == "thingspeak":
        return check_thingspeak(station)
    if station["type"] == "wunderground":
        return check_wunderground(station)
    raise ValueError(f"Tipo de estación desconocido: {station['type']}")


def send_whatsapp(text):
    if not CALLMEBOT_PHONE or not CALLMEBOT_APIKEY:
        print("CALLMEBOT_PHONE/CALLMEBOT_APIKEY no configurados, no se manda WhatsApp")
        return
    qs = urllib.parse.urlencode({"phone": CALLMEBOT_PHONE, "apikey": CALLMEBOT_APIKEY, "text": text})
    url = f"https://api.callmebot.com/whatsapp.php?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=20, context=ssl_context()) as resp:
            print("CallMeBot:", resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print("Error mandando WhatsApp:", e)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"stations": {}}


def new_station_state():
    return {
        "monitoring_since": None,
        "current_status": "pending",
        "current_reason": "Todavía no corrió el primer chequeo automático.",
        "down_since": None,
        "last_data_timestamp": None,
        "last_check": None,
        "current_issue_number": 0,
        "incidents": [],
    }


def process_check(stations_state, key, display_name, status, reason, data_ts_iso, now, now_iso):
    """Actualiza el estado/historial de una estación (o señal de una estación)
    con el resultado de un chequeo, y manda el WhatsApp correspondiente si
    justo pasó de arriba a caída o de caída a arriba."""
    state = stations_state.setdefault(key, new_station_state())
    state["display_name"] = display_name
    prev_status = state.get("current_status")

    if state.get("monitoring_since") is None:
        state["monitoring_since"] = now_iso

    incidents = state.setdefault("incidents", [])
    just_down = status == "down" and prev_status != "down"
    just_recovered = status == "up" and prev_status == "down"
    recovered_duration = None

    if status == "down" and prev_status != "down":
        state["down_since"] = now_iso
        state["current_issue_number"] = state.get("current_issue_number", 0) + 1
        incidents.append({"start": now_iso, "end": None, "duration_minutes": None, "reason": reason})
    elif status == "down" and prev_status == "down":
        if incidents and incidents[-1]["end"] is None:
            incidents[-1]["reason"] = reason
    elif status == "up" and prev_status == "down":
        if incidents and incidents[-1]["end"] is None:
            start = datetime.fromisoformat(incidents[-1]["start"])
            duration = (now - start).total_seconds() / 60
            incidents[-1]["end"] = now_iso
            incidents[-1]["duration_minutes"] = round(duration, 1)
            recovered_duration = _fmt_age(duration)
        state["down_since"] = None

    if len(incidents) > MAX_INCIDENTS_KEPT:
        del incidents[: len(incidents) - MAX_INCIDENTS_KEPT]

    state["current_status"] = status
    state["current_reason"] = reason
    state["last_check"] = now_iso
    if data_ts_iso is not None:
        state["last_data_timestamp"] = data_ts_iso

    print(f"{key}: {status} ({reason or 'sin novedad'})")

    if just_down:
        send_whatsapp(f"⚠️ Se cayó la estación {display_name}: {reason}")
    elif just_recovered:
        send_whatsapp(f"✅ Volvió la estación {display_name}, había estado caída {recovered_duration}")


def main():
    full_state = load_state()
    stations_state = full_state.setdefault("stations", {})
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    valid_keys = set()
    for station in STATIONS:
        key = station["key"]

        if station.get("signals"):
            results = check_thingspeak_signals(station)
            for signal in station["signals"]:
                suf = signal["suffix"]
                signal_key = f"{key}_{suf}"
                valid_keys.add(signal_key)
                status, reason, data_ts_iso = results[suf]
                process_check(
                    stations_state,
                    signal_key,
                    f"{station['name']} — {signal['label']}",
                    status, reason, data_ts_iso, now, now_iso,
                )
        else:
            valid_keys.add(key)
            status, reason, data_ts_iso = check_station(station)
            process_check(stations_state, key, station["name"], status, reason, data_ts_iso, now, now_iso)

    # Saca del JSON las estaciones/señales que ya no están en STATIONS (ej. la
    # "bavio" de una versión anterior, reemplazada por "bavio_temp_hum" y
    # "bavio_pluvio"), para que no quede un estado congelado dando vueltas.
    for stale_key in set(stations_state) - valid_keys:
        del stations_state[stale_key]

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(full_state, f, ensure_ascii=False, indent=2)
    print(f"Escrito {STATE_PATH}")


if __name__ == "__main__":
    main()
