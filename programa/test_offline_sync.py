"""
Prueba de extremo a extremo del flujo offline-first: simula un corte de
internet, carga observaciones locales, reconecta y verifica que sync.py
suba lo pendiente sin duplicar nada.

No toca la Google Sheet real: levanta un servidor HTTP local que imita el
contrato de apps-script/Code.gs (mismos endpoints POST/GET, mismas
respuestas), y apunta config.py a ese servidor de prueba.

Correr con: python3 test_offline_sync.py
"""
import json
import os
import socket
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import calculos
import config
import db
import sync

FALLAS = []


def check(condicion, mensaje):
    marca = "OK" if condicion else "FALLA"
    if not condicion:
        FALLAS.append(mensaje)
    print(f"[{marca}] {mensaje}")


class FilasServidorPrueba:
    """Estado del "Apps Script" de prueba: una lista de filas en memoria,
    igual que haría la Sheet real."""

    def __init__(self):
        self.filas = []
        self.lock = threading.Lock()

    def agregar(self, fila):
        with self.lock:
            self.filas.append(fila)

    def listar(self):
        with self.lock:
            return list(self.filas)

    def marcar_descarte(self, fecha, hora, descartada, motivo, descartado_por):
        with self.lock:
            for fila in self.filas:
                if fila.get("fecha") == fecha and fila.get("hora") == hora:
                    fila["descartada"] = descartada
                    fila["motivoDescarte"] = motivo if descartada else ""
                    fila["descartadoPor"] = descartado_por if descartada else ""
                    return True
            return False


def crear_handler(estado, token_esperado):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # silencia el log de acceso default

        def do_POST(self):
            largo = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(largo) or b"{}")
            if token_esperado and body.get("token") != token_esperado:
                self._responder({"ok": False, "error": "Token inválido."})
                return
            if body.get("accion") == "marcar_descarte":
                encontrada = estado.marcar_descarte(
                    body.get("fecha"), body.get("hora"), bool(body.get("descartada")),
                    body.get("motivo", ""), body.get("descartadoPor", ""),
                )
                if not encontrada:
                    self._responder({"ok": False, "error": "No se encontró ninguna observación con esa fecha y hora."})
                    return
                self._responder({"ok": True, "fila": body})
                return
            estado.agregar(body)
            self._responder({"ok": True, "fila": body})

        def do_GET(self):
            self._responder({"ok": True, "filas": estado.listar()})

        def _responder(self, data):
            cuerpo = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    return Handler


def main():
    dir_tmp = tempfile.mkdtemp(prefix="lpo_test_")
    db.DB_PATH = os.path.join(dir_tmp, "observaciones.db")
    config.CONFIG_PATH = os.path.join(dir_tmp, "config.json")
    print(f"DB de prueba: {db.DB_PATH}")
    db.inicializar()

    token = "token-de-prueba"
    estado_servidor = FilasServidorPrueba()

    # Elige un puerto libre y lo suelta enseguida: mientras no levantemos el
    # servidor ahí, cualquier request da "conexión rechazada" al instante
    # (a diferencia de crear el servidor ya bindeado pero sin escuchar
    # todavía, que dejaría la conexión colgada hasta el timeout).
    sock_temporal = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_temporal.bind(("127.0.0.1", 0))
    puerto = sock_temporal.getsockname()[1]
    sock_temporal.close()

    config.guardar({"apps_script_url": f"http://127.0.0.1:{puerto}/", "apps_script_token": token})

    # --- Paso 1: "sin internet" (todavía no hay nada escuchando en el puerto) ---
    print("\n--- Simulando corte de internet ---")
    entrada1 = {"t_seca": 20.0, "t_humeda": 15.0, "t_adjunto": 19.0, "barometro": 758.0}
    resultado1 = calculos.calcular_observacion(entrada1)
    fila1 = {"fecha": "2026-09-13", "hora": "09:00", **entrada1, **resultado1}
    db.insertar_observacion(fila1, origen="local", sync_status="pendiente")

    entrada2 = {"t_seca": 22.0, "t_humeda": 17.0, "t_adjunto": 21.0, "barometro": 759.5}
    resultado2 = calculos.calcular_observacion(entrada2)
    fila2 = {"fecha": "2026-09-13", "hora": "15:00", **entrada2, **resultado2}
    db.insertar_observacion(fila2, origen="local", sync_status="pendiente")

    check(db.contar_pendientes() == 2, "Las 2 observaciones quedaron guardadas local como 'pendiente'")

    try:
        sync.sincronizar_todo()
        check(False, "sincronizar_todo() debía fallar sin servidor disponible (no falló)")
    except Exception:
        check(True, "sincronizar_todo() falla prolijamente cuando no hay conexión (esperado)")

    check(db.contar_pendientes() == 2, "Las observaciones siguen 'pendiente' después del intento fallido")

    # --- Paso 2: "vuelve internet" ---
    print("\n--- Reconectando (arrancando el servidor de prueba) ---")
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), crear_handler(estado_servidor, token))
    hilo_servidor = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo_servidor.start()

    subidas, bajadas = sync.sincronizar_todo()
    check(subidas == 2, f"Subió las 2 observaciones pendientes (subidas={subidas})")
    check(db.contar_pendientes() == 0, "Ya no quedan observaciones 'pendiente' después de sincronizar")
    check(len(estado_servidor.listar()) == 2, "El servidor de prueba (Sheet simulada) tiene exactamente 2 filas")

    # --- Paso 3: sincronizar de nuevo no debe duplicar nada ---
    print("\n--- Sincronizando de nuevo (no debería duplicar nada) ---")
    subidas2, bajadas2 = sync.sincronizar_todo()
    check(subidas2 == 0, f"No sube nada de nuevo, ya estaba todo sincronizado (subidas={subidas2})")
    check(bajadas2 == 0, f"No baja duplicados de lo que ya tenía local (bajadas={bajadas2})")
    check(len(estado_servidor.listar()) == 2, "El servidor sigue con exactamente 2 filas (no se duplicó nada)")
    check(len(db.listar_observaciones()) == 2, "La base local sigue con exactamente 2 observaciones")

    # --- Paso 4: algo cargado "desde la web" (directo en el servidor) baja al programa ---
    print("\n--- Simulando una carga hecha desde la web mientras tanto ---")
    entrada3 = {"t_seca": 18.0, "t_humeda": 14.0, "t_adjunto": 17.5, "barometro": 760.2}
    resultado3 = calculos.calcular_observacion(entrada3)
    payload_web = {
        "fecha": "2026-09-13", "hora": "21:00", "token": token,
        "tSeca": entrada3["t_seca"], "tHumeda": entrada3["t_humeda"],
        "tAdjunto": entrada3["t_adjunto"], "barometro": entrada3["barometro"],
        "pEstMmhg": resultado3["p_est_mmhg"], "pEstHpa": resultado3["p_est_hpa"],
        "pnmMmhg": resultado3["pnm_mmhg"], "pnmHpa": resultado3["pnm_hpa"],
        "tensionVapor": resultado3["tension_vapor"], "puntoRocio": resultado3["punto_rocio"],
        "humedadRelativa": resultado3["humedad_relativa"],
    }
    estado_servidor.agregar(payload_web)

    subidas3, bajadas3 = sync.sincronizar_todo()
    check(bajadas3 == 1, f"Bajó la observación cargada 'desde la web' (bajadas={bajadas3})")
    check(len(db.listar_observaciones()) == 3, "La base local ahora tiene las 3 observaciones")
    check(db.existe("2026-09-13", "21:00"), "La observación de la web quedó guardada local, sin cargarla a mano")

    # --- Paso 5: descartar una observación local y sincronizar el descarte ---
    print("\n--- Descartando una observación local (con motivo) y sincronizando ---")
    obs1 = next(f for f in db.listar_observaciones() if f["fecha"] == "2026-09-13" and f["hora"] == "09:00")
    db.marcar_descarte(obs1["id"], True, motivo="Termómetro descalibrado", descartado_por="Mauricio")
    check(len(db.obtener_descartes_pendientes()) == 1, "El descarte queda 'pendiente' de subir")

    subidas4, bajadas4 = sync.sincronizar_todo()
    check(len(db.obtener_descartes_pendientes()) == 0, "El descarte ya no queda pendiente tras sincronizar")
    fila_servidor = next(f for f in estado_servidor.listar() if f["fecha"] == "2026-09-13" and f["hora"] == "09:00")
    check(fila_servidor.get("descartada") is True, "El servidor (Sheet simulada) recibió el descarte")
    check(fila_servidor.get("motivoDescarte") == "Termómetro descalibrado", "El servidor recibió el motivo correcto")

    # --- Paso 6: un descarte hecho "desde la web" baja y se refleja local ---
    print("\n--- Simulando un descarte hecho desde la web ---")
    estado_servidor.marcar_descarte("2026-09-13", "15:00", True, "Lluvia mojó el instrumento", "Otro observador")
    _, bajadas5 = sync.sincronizar_todo()
    obs2 = next(f for f in db.listar_observaciones() if f["fecha"] == "2026-09-13" and f["hora"] == "15:00")
    check(bool(obs2["descartada"]), "El descarte hecho en el servidor se reflejó en la base local")
    check(obs2["motivo_descarte"] == "Lluvia mojó el instrumento", "El motivo bajado coincide con el del servidor")
    check(obs2["descartado_por"] == "Otro observador", "Quién descartó también se sincronizó")

    servidor.shutdown()

    print("\n" + ("TODO OK" if not FALLAS else f"HAY {len(FALLAS)} FALLA(S)"))
    return 0 if not FALLAS else 1


if __name__ == "__main__":
    sys.exit(main())
