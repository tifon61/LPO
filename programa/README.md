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

## Empaquetarlo como .exe con ícono (para instalar sin tener Python)

Hay que compilarlo en Windows (un .exe se genera corriendo PyInstaller en
Windows, no en Linux/Mac — si en algún momento alguien lo usa en Mac, se
compila un binario Mac aparte, en una Mac).

### Paso 1 — Generar el .exe

```
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --onefile --windowed --name ObservacionesLPO ^
  --icon icono.ico ^
  --add-data "img;img" --add-data "icono.ico;." ^
  main.py
```

(el `^` es el separador de línea de `cmd`; si lo pegás en PowerShell,
escribí todo en una sola línea sin los `^`). Esto deja el ejecutable en
`dist\ObservacionesLPO.exe`: un solo archivo, ya con el ícono del
termómetro, que corre en cualquier Windows sin tener Python instalado.
`--add-data` es necesario para que el .exe lleve adentro las fotos de la
pestaña Fórmulas y el ícono — sin eso, esas imágenes no aparecerían.

Con solo este paso ya podés copiar `ObservacionesLPO.exe` al Escritorio o
mandarle un acceso directo (click derecho → Enviar a → Escritorio) y va a
verse como cualquier otro programa, con su ícono. `config.json` y
`observaciones.db` se crean al lado del `.exe` la primera vez que se corre
— cada computadora tiene su propia base local, y todas convergen a través
de la misma Google Sheet.

### Paso 2 (opcional) — Armar un instalador de verdad

Si querés el asistente típico de "Siguiente > Siguiente > Instalar", con
acceso directo automático en el Escritorio/Menú Inicio y un desinstalador
en "Aplicaciones y características":

1. Instalá [Inno Setup](https://jrsoftware.org/isinfo.php) (gratis).
2. Abrí `instalador.iss` (de esta carpeta) con el Inno Setup Compiler.
3. **Build → Compile** (o F9). Necesita que ya exista `dist\ObservacionesLPO.exe`
   del paso 1.
4. Queda el instalador en `programa\Output\Instalador_ObservacionesLPO.exe`
   — ese es el archivo que le pasás a cualquier computadora para "instalar"
   el programa como cualquier otro.

## Estructura

- `main.py` — interfaz (ttkbootstrap/Tkinter, tres pestañas: Cargar / Histórico / Fórmulas).
  La pestaña Histórico incluye un gráfico (matplotlib) de la variable elegida a lo largo
  del tiempo, además de la tabla.
- `calculos.py` — motor de cálculo (mismo que `observaciones/calculos.js`).
- `db.py` — almacenamiento local en SQLite.
- `sync.py` — subir/bajar contra el Web App de Apps Script.
- `config.py` / `config.json` — URL y token del backend.
- `rutas.py` — resuelve dónde guardar/leer archivos, tanto corriendo `python main.py`
  como empaquetado en un `.exe` (que necesita rutas distintas para no perder
  `config.json`/`observaciones.db` entre arranques).
- `icono.ico` / `icono.png` — ícono del programa.
- `instalador.iss` — script de Inno Setup para generar un instalador de Windows.
