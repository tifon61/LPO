"""
Test de la lista de observadores (sin tocar la base real ni la Sheet):
la misma regla que el formulario web.

    python3 test_observadores.py
"""
import os
import tempfile

import config
import db

OFICIAL = sorted(config.OBSERVADORES, key=str.lower)


def main():
    with tempfile.TemporaryDirectory() as d:
        db.DB_PATH = os.path.join(d, "prueba.db")
        db.inicializar()
        # Observaciones viejas con el nombre escrito de otra forma: NO entran en la lista.
        base = {"t_seca": 20, "t_humeda": 17, "cargado_el": "2026-11-12T12:00:00"}
        db.insertar_observacion({**base, "fecha": "2026-11-12", "hora": "09:00", "observador": "mauricio"},
                                origen="sheet", sync_status="sincronizado")
        assert db.listar_observadores() == OFICIAL, db.listar_observadores()

        assert db.agregar_observador("ZZ") is True                   # alguien nuevo, en esta compu
        assert db.agregar_observador("mb") is False                  # ya está (lista oficial)
        assert db.listar_observadores() == sorted(OFICIAL + ["ZZ"], key=str.lower)

        db.eliminar_observador("MB")                                  # quitado de la oficial, en esta compu
        assert "MB" not in db.listar_observadores()
        assert db.agregar_observador("MB") is True                   # se puede volver a poner
        assert "MB" in db.listar_observadores()

        # En la compu de la oficina ya habían cargado las iniciales a mano:
        # no se repiten.
        for n in config.OBSERVADORES:
            db.agregar_observador(n)
        assert db.listar_observadores() == sorted(OFICIAL + ["ZZ"], key=str.lower)

        assert db.ultimo_observador() == ""
        db.recordar_observador("IV")
        db.inicializar()                                              # abrir de nuevo no rompe nada
        assert db.ultimo_observador() == "IV"
    print("OK: lista de observadores")


if __name__ == "__main__":
    main()
