"""
Configuración local mínima: solo recuerda en qué carpeta están los Excel,
para que "Actualizar año actual" sepa dónde buscar sin tener que
preguntarlo cada vez. Todo queda en esta misma compu, no se sube a
ningún lado.
"""
import json
import os

import rutas

CONFIG_PATH = os.path.join(rutas.dir_datos(), "config.json")


def cargar():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def guardar(cambios):
    actual = cargar()
    actual.update(cambios)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(actual, f, ensure_ascii=False, indent=2)
