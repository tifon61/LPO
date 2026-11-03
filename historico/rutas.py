"""
Resolución de rutas que funciona igual corriendo `python main.py` directo
que empaquetado como .exe con PyInstaller (--onefile) — mismo criterio que
programa/rutas.py (ver ese archivo para la explicación completa).
"""
import os
import sys

DIR_SCRIPT = os.path.dirname(os.path.abspath(__file__))
CONGELADO = bool(getattr(sys, "frozen", False))


def dir_datos():
    """Carpeta donde guardar archivos que tienen que persistir (la base
    histórico.db). Al lado del .exe no sirve una vez instalado en
    "Program Files" (requiere admin para escribir ahí)."""
    if not CONGELADO:
        return DIR_SCRIPT
    appdata = os.getenv("APPDATA")
    if appdata:
        carpeta = os.path.join(appdata, "HistoricoLPO")
    else:
        carpeta = os.path.join(os.path.expanduser("~"), ".historico-lpo")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta
