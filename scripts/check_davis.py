#!/usr/bin/env python3
"""
Chequea si la página pública de la estación Davis (campo) responde y si los
datos que muestra están frescos, y arma/actualiza data/davis-monitor.json con
el historial de caídas. Lo corre GitHub Actions cada 15 minutos, no cada
visitante del sitio.

Se considera "caída" cuando:
- la URL no responde (timeout, error de conexión, HTTP != 200), o
- responde pero el dato más reciente que reporta tiene más de STALE_MINUTES
  minutos de antigüedad.
"""
import json
import os
import re
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone

import certifi

DAVIS_URL = "https://meteo.fcaglp.unlp.edu.ar/davis/campo/downld08.txt"
STALE_MINUTES = 60
# El servidor no manda el certificado intermedio (ZeroSSL ECC DV SSL CA 2) ni
# encadena a una raíz que certifi ya incluya (Sectigo Public Server
# Authentication Root E46, todavía no está en el bundle de Mozilla/certifi).
# Sin este archivo, la verificación TLS falla con CERTIFICATE_VERIFY_FAILED
# aunque el sitio ande bien. Ver: openssl s_client -connect meteo.fcaglp.unlp.edu.ar:443 -showcerts
EXTRA_CA_CERTS = os.path.join(os.path.dirname(__file__), "extra_ca_certs.pem")
ARGENTINA_TZ = timezone(timedelta(hours=-3))
MAX_INCIDENTS_KEPT = 200

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "davis-monitor.json")

DATE_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([APap][Mm]?)?")


def parse_data_timestamp(text):
    """Busca la fecha y hora del registro más reciente del archivo de la Davis
    y la devuelve como datetime tz-aware en hora Argentina. El archivo lista
    las mediciones de más vieja a más nueva (una por línea), así que hay que
    tomar la última línea con fecha/hora, no la primera. Este archivo en
    particular usa DD/MM/YY (confirmado: los incidentes con día > 12 solo
    resuelven bien con esa interpretación). Se prueba DD/MM primero y,
    si no da una fecha válida, se prueba invertido (MM/DD/YY) como
    respaldo — probar MM/DD primero rompía todos los días 1 a 12 de cada
    mes, porque esos días también son meses válidos (ver día 1/9 leído
    como 9 de enero)."""
    date_m = time_m = None
    for line in reversed(text.splitlines()):
        date_m = DATE_RE.search(line)
        time_m = TIME_RE.search(line)
        if date_m and time_m:
            break
    if not date_m or not time_m:
        return None

    a, b, year = (int(x) for x in date_m.groups())
    if year < 100:
        year += 2000

    day = None
    for month_guess, day_guess in ((b, a), (a, b)):
        if 1 <= month_guess <= 12 and 1 <= day_guess <= 31:
            try:
                base_date = datetime(year, month_guess, day_guess)
                day = day_guess
                break
            except ValueError:
                continue
    if day is None:
        return None

    hour = int(time_m.group(1))
    minute = int(time_m.group(2))
    second = int(time_m.group(3) or 0)
    ampm = time_m.group(4)
    if ampm:
        ampm = ampm[0].upper()
        if ampm == "P" and hour != 12:
            hour += 12
        if ampm == "A" and hour == 12:
            hour = 0
    if hour > 23:
        return None

    try:
        return base_date.replace(hour=hour, minute=minute, second=second, tzinfo=ARGENTINA_TZ)
    except ValueError:
        return None


def fmt_age(minutes):
    if minutes < 120:
        return f"{minutes:.0f} min"
    return f"{minutes / 60:.1f}h"


def check_davis():
    """Devuelve (status, reason, last_data_timestamp_iso_or_None)."""
    try:
        req = urllib.request.Request(DAVIS_URL, headers={"User-Agent": "pronostico-unlp-monitor"})
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.load_verify_locations(cafile=EXTRA_CA_CERTS)
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            if resp.status != 200:
                return "down", f"HTTP {resp.status}", None
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return "down", f"No se pudo conectar: {e}", None

    data_ts = parse_data_timestamp(body)
    if data_ts is None:
        # No se pudo interpretar la fecha del archivo: no penalizamos con una
        # caída "por antigüedad" sin evidencia, solo lo dejamos sin dato.
        return "up", None, None

    now_local = datetime.now(ARGENTINA_TZ)
    age_minutes = (now_local - data_ts).total_seconds() / 60
    data_ts_iso = data_ts.astimezone(timezone.utc).isoformat()
    if age_minutes > STALE_MINUTES:
        return "down", f"Datos desactualizados: último registro hace {fmt_age(age_minutes)}", data_ts_iso
    return "up", None, data_ts_iso


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "monitoring_since": None,
        "current_status": "pending",
        "current_reason": None,
        "down_since": None,
        "last_data_timestamp": None,
        "last_check": None,
        "current_issue_number": 0,
        "incidents": [],
    }


def main():
    state = load_state()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    status, reason, data_ts_iso = check_davis()
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
            recovered_duration = fmt_age(duration)
        state["down_since"] = None

    if len(incidents) > MAX_INCIDENTS_KEPT:
        del incidents[: len(incidents) - MAX_INCIDENTS_KEPT]

    state["current_status"] = status
    state["current_reason"] = reason
    state["last_check"] = now_iso
    if data_ts_iso is not None:
        state["last_data_timestamp"] = data_ts_iso

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"Estado: {status} ({reason or 'sin novedad'}) — escrito {STATE_PATH}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"just_down={'true' if just_down else 'false'}\n")
            f.write(f"reason<<GITHUB_OUTPUT_EOF\n{reason or ''}\nGITHUB_OUTPUT_EOF\n")
            f.write(f"just_recovered={'true' if just_recovered else 'false'}\n")
            f.write(f"recovered_duration<<GITHUB_OUTPUT_EOF\n{recovered_duration or ''}\nGITHUB_OUTPUT_EOF\n")


if __name__ == "__main__":
    main()
