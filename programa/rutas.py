"""
Resolución de rutas que funciona igual corriendo `python main.py` directo
que empaquetado como .exe con PyInstaller (--onefile).

Hay dos casos distintos:
- Recursos de solo lectura empaquetados adentro del .exe (imágenes, ícono):
  PyInstaller los extrae a una carpeta temporal (sys._MEIPASS) en cada
  arranque -> hay que leerlos de ahí.
- Datos que el programa escribe y tienen que persistir entre arranques
  (config.json, observaciones.db): tienen que vivir en una carpeta que el
  usuario pueda escribir sin ser administrador. Al lado del .exe NO sirve
  en cuanto el programa queda instalado en "Program Files" (requiere admin
  para escribir ahí, y sqlite tira "unable to open database file") — se
  usa la carpeta de datos de la app del usuario (%APPDATA% en Windows,
  ~/.observaciones-lpo en Mac/Linux), que siempre es escribible.
"""
import os
import sys

DIR_SCRIPT = os.path.dirname(os.path.abspath(__file__))
CONGELADO = bool(getattr(sys, "frozen", False))


def dir_datos():
    """Carpeta donde guardar archivos que tienen que persistir (config, DB)."""
    if not CONGELADO:
        return DIR_SCRIPT
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    carpeta = os.path.join(base, "ObservacionesLPO")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def ruta_recurso(*partes):
    """Carpeta donde están los recursos de solo lectura empaquetados (img/, ícono)."""
    base = getattr(sys, "_MEIPASS", DIR_SCRIPT)
    return os.path.join(base, *partes)
