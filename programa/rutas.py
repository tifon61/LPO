"""
Resolución de rutas que funciona igual corriendo `python main.py` directo
que empaquetado como .exe con PyInstaller (--onefile).

Hay dos casos distintos:
- Recursos de solo lectura empaquetados adentro del .exe (imágenes, ícono):
  PyInstaller los extrae a una carpeta temporal (sys._MEIPASS) en cada
  arranque -> hay que leerlos de ahí.
- Datos que el programa escribe y tienen que persistir entre arranques
  (config.json, observaciones.db): tienen que vivir al lado del .exe real
  (sys.executable), no en esa carpeta temporal que se borra sola.
"""
import os
import sys

DIR_SCRIPT = os.path.dirname(os.path.abspath(__file__))
CONGELADO = bool(getattr(sys, "frozen", False))


def dir_datos():
    """Carpeta donde guardar archivos que tienen que persistir (config, DB)."""
    if CONGELADO:
        return os.path.dirname(sys.executable)
    return DIR_SCRIPT


def ruta_recurso(*partes):
    """Carpeta donde están los recursos de solo lectura empaquetados (img/, ícono)."""
    base = getattr(sys, "_MEIPASS", DIR_SCRIPT)
    return os.path.join(base, *partes)
