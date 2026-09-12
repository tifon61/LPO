"""
Configuración del programa: URL y token del mismo backend de Google Apps
Script que usa la página web (observaciones/config.js). Se puede
sobreescribir editando config.json al lado de este archivo, sin tocar código.
"""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

VALORES_POR_DEFECTO = {
    "apps_script_url": "https://script.google.com/macros/s/AKfycbyjvZaO3s2ExJrqXR7a4QwF3bObO4MOOxDzrXO0WscDmYhJN-uyAwjgExXZGr13wRre/exec",
    "apps_script_token": "d5c3c4ef737acc2623cc0216747bfb62",
}


def cargar():
    if not os.path.exists(CONFIG_PATH):
        guardar(VALORES_POR_DEFECTO)
        return dict(VALORES_POR_DEFECTO)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return {**VALORES_POR_DEFECTO, **datos}


def guardar(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
