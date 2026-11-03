# Archivo Histórico de Observaciones (standalone)

Programa aparte de `programa/` (el de carga diaria de LPO) — este lee los
Excel anuales con décadas de observaciones ya cargadas (uno por año) y los
junta en una base SQLite local, para poder ver/graficar cualquier período
y exportarlo a CSV. Corre 100% local en esta computadora: no sincroniza
con ningún servidor ni Google Sheet, no sube nada a ningún lado.

## Formato esperado de los Excel

Un archivo por año, con las columnas en este orden (ver `importador.py`
para el detalle exacto):

```
FECHA | AÑO | HORA | T. SECO | T. HUMEDO | T. MAX | T. MIN | PR | TV | HR |
T. ADJUNTO | BAROMETRO | P. N. ESTACION | P. N. MAR | P.N.M. hPa | LLUVIA |
HORA (repetida) | (vacía) | (fecha auxiliar) | Acum. Diario UTC
```

Se lee por **posición** de columna, no por el texto del título — en 50
años de archivos armados por distintas personas los títulos pueden variar
un poco (como un espacio de más), pero la posición se mantuvo. Si un
archivo en particular tiene el encabezado muy distinto, el programa avisa
igual pero intenta importarlo — conviene revisar ese archivo a mano si
aparece ese aviso.

Acepta tanto números ya numéricos como texto con coma decimal ("15,5"),
y trata "/" o cualquier texto no numérico como "sin dato" (no rompe la
importación, esa celda queda vacía).

## Cómo correrlo

```bash
cd historico
pip install -r requirements.txt
python3 main.py
```

La primera vez crea `historico.db` (vacío) en esta misma carpeta.

### Si la compu es de 32 bits (Windows "x86")

Mismo problema y misma solución que en `programa/` (ver
`programa/README.md`, sección "Si la compu es de 32 bits"): `matplotlib`
no trae paquetes precompilados para 32 bits en versiones recientes. Usá
Python 3.10 (32-bit) y estas versiones específicas:

```
py -3.10 -m pip install openpyxl xlrd Pillow numpy==1.21.6 matplotlib==3.5.3 kiwisolver==1.4.4 ttkbootstrap==2.2.3
```

## Uso

1. **Importar todo** — la primera vez (o si sumaste años viejos que
   todavía no estaban cargados), elegís la carpeta donde están todos los
   Excel y se importan todos juntos. Se recuerda esa carpeta para el paso
   siguiente.
2. **Actualizar año actual** — para el uso de todos los días: vuelve a
   leer *solo* el Excel de este año (lo encuentra buscando el año actual
   en el nombre del archivo, ej. "2026.xlsx" o "Datos_2026.xlsx") —mucho
   más rápido que reimportar los 50 años cada vez. Si todavía no se usó
   "Importar todo" una vez, pide la carpeta la primera vez y después ya
   la recuerda sola.
3. Reimportar un archivo (por cualquiera de los dos botones) nunca
   duplica: una observación con la misma fecha+hora que ya existía se
   actualiza en vez de agregarse de nuevo. Así que no pasa nada si se
   aprieta "Actualizar año actual" varias veces seguidas, o si se vuelve
   a hacer "Importar todo" sobre la misma carpeta.
4. **Ver / graficar un período** — elegís la variable y el rango de
   fechas (dd/mm/aaaa), apretás "Graficar" y se dibuja la serie + se
   llena la tabla de abajo (si el período es muy largo, la tabla solo
   muestra las primeras 2000 filas, pero el gráfico y el CSV sí usan
   todo el período).
5. **Exportar período a CSV** — exporta exactamente lo que se graficó la
   última vez, con BOM UTF-8 y la directiva `sep=,` para que Excel en
   configuración regional argentina no mezcle todo en una sola columna.

## Estructura

- `main.py` — interfaz (ttkbootstrap/Tkinter): importar, graficar, tabla, exportar CSV.
- `importador.py` — lectura de los Excel anuales (.xlsx y .xls) y conversión a filas listas para la base.
- `db.py` — almacenamiento local en SQLite.
- `config.py` — recuerda la carpeta de los Excel (para "Actualizar año actual").
- `rutas.py` — resuelve dónde guardar la base, tanto corriendo `python main.py` como empaquetado en un `.exe`.
