"""
Test de la lista de observadores (sin tocar la base real ni la Sheet):
la misma regla que el formulario web.

    python3 test_observadores.py
"""
import os
import tempfile

import db


def main():
    with tempfile.TemporaryDirectory() as d:
        db.DB_PATH = os.path.join(d, "prueba.db")
        db.inicializar()
        base = {"t_seca": 20, "t_humeda": 17, "cargado_el": "2026-11-12T12:00:00"}
        # Observaciones (como si vinieran de la Sheet): MB, FB, y una descartada de "Viejo".
        db.insertar_observacion({**base, "fecha": "2026-11-12", "hora": "09:00", "observador": "MB"}, origen="sheet", sync_status="sincronizado")
        db.insertar_observacion({**base, "fecha": "2026-11-11", "hora": "15:00", "observador": "FB "}, origen="sheet", sync_status="sincronizado")
        db.insertar_observacion({**base, "fecha": "2026-11-01", "hora": "21:00", "observador": "Viejo", "descartada": True},
                                origen="sheet", sync_status="sincronizado")
        assert db.listar_observadores() == ["FB", "MB"], db.listar_observadores()

        assert db.agregar_observador("IV") is True
        assert db.agregar_observador("mb") is False                  # ya está (por sus observaciones)
        assert db.listar_observadores() == ["FB", "IV", "MB"]

        db.eliminar_observador("MB")                                  # quitado: no vuelve aunque tenga observaciones
        assert db.listar_observadores() == ["FB", "IV"]
        assert db.agregar_observador("MB") is True                   # se puede volver a agregar
        assert db.listar_observadores() == ["FB", "IV", "MB"]

        assert db.ultimo_observador() == ""
        db.recordar_observador("IV")
        assert db.ultimo_observador() == "IV"
        db.inicializar()                                              # abrir de nuevo no rompe nada
        assert db.listar_observadores() == ["FB", "IV", "MB"] and db.ultimo_observador() == "IV"
    print("OK: lista de observadores")


if __name__ == "__main__":
    main()
