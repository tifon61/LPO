# Programa de escritorio — Observaciones meteorológicas (offline-first)

Carga observaciones sin necesitar internet (queda guardado local en
`observaciones.db`, un archivo SQLite en esta misma carpeta) y sincroniza
con la misma Google Sheet que usa la página web, en los dos sentidos:

- **Sube** las observaciones cargadas acá que todavía no estén en la Sheet.
- **Baja** las observaciones cargadas desde la web (u otra computadora) que
  todavía no estén acá.

Usa el mismo backend (Google Apps Script) y el mismo motor de cálculo
(mismas fórmulas y Tabla D-4) que `observaciones/` — están portados a
Python en `calculos.py`. Si cambiás una fórmula, replicala en los tres
lugares: `observaciones/calculos.js`, `apps-script/Code.gs` y este `calculos.py`.

## Cómo correrlo (con Python instalado)

```bash
cd programa
pip install -r requirements.txt
python3 main.py
```

La primera vez crea `config.json` (con la URL y el token ya apuntando a la
misma Sheet que la web — no hace falta configurar nada) y `observaciones.db`
(vacío) en esta carpeta.

## Cómo funciona la sincronización

- Al arrancar el programa, y después de guardar cada observación, intenta
  sincronizar solo en segundo plano (no bloquea la ventana). Si no hay
  internet, no pasa nada — la observación queda guardada local, marcada
  "pendiente", y se sube la próxima vez que sincronice con éxito.
- El botón **"Sincronizar ahora"** lo fuerza manualmente y avisa si falló.
- Para no duplicar filas, cada observación se identifica por su combinación
  única de **fecha + hora** — tanto localmente (SQLite) como al conciliar
  contra la Sheet. Si cargás dos veces la misma fecha/hora, la segunda se
  ignora (con un aviso).

## Empaquetarlo como .exe (para instalar sin tener Python)

Con [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name ObservacionesLPO main.py
```

Esto genera `dist/ObservacionesLPO.exe` (en Windows) o el binario
equivalente en Mac/Linux — un solo archivo que se puede copiar a cualquier
computadora sin instalar Python ni nada más. Hay que compilarlo en el mismo
sistema operativo donde se va a usar (un .exe se genera corriendo
PyInstaller en Windows, no en Linux/Mac).

`config.json` y `observaciones.db` se crean al lado del ejecutable la
primera vez que se corre — cada computadora tiene su propia base local, y
todas convergen a través de la misma Google Sheet.

## Estructura

- `main.py` — interfaz (ttkbootstrap/Tkinter, tres pestañas: Cargar / Histórico / Fórmulas).
  La pestaña Histórico incluye un gráfico (matplotlib) de la variable elegida a lo largo
  del tiempo, además de la tabla.
- `calculos.py` — motor de cálculo (mismo que `observaciones/calculos.js`).
- `db.py` — almacenamiento local en SQLite.
- `sync.py` — subir/bajar contra el Web App de Apps Script.
- `config.py` / `config.json` — URL y token del backend.
