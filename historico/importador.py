"""
Lector de los Excel anuales del archivo histórico (uno por año, mismo
formato desde hace décadas) y conversión a filas listas para la base
SQLite (ver db.py).

Formato esperado (20 columnas, siempre en este orden — confirmado con el
dueño del archivo): FECHA, AÑO, HORA, T. SECO, T. HUMEDO, T. MAX, T. MIN,
PR, TV, HR, T. ADJUNTO, BAROMETRO, P. N. ESTACION, P. N. MAR, P.N.M. hPa,
LLUVIA, HORA (repetida, se usa solo para verificar), (columna vacía),
columna de fecha sin título (auxiliar de "Acum. Diario UTC"), Acum. Diario
UTC (el valor).

Se lee por POSICIÓN de columna, no por nombre — en 50 años de archivos
digitizados por distintas personas los títulos pueden variar levemente
(como "T . MAX" con un espacio de más en el ejemplo real), pero la
posición se mantuvo estable. Por eso, antes de leer los datos, se valida
que el encabezado se parezca a lo esperado (sin exigir calzar exacto) y
se avisa si un archivo en particular luce distinto, para que se revise a
mano en vez de importar algo mal interpretado en silencio.
"""
import datetime
import os

import openpyxl

try:
    import xlrd  # solo hace falta para leer .xls (formato viejo, pre-2007)
except ImportError:
    xlrd = None

# Posición (0-indexada) -> nombre de columna en la base. "_verificar_hora"
# y las dos auxiliares de abajo no son parte del dato principal, se
# guardan igual por si hace falta revisar algo más adelante.
POSICIONES = [
    "fecha", "anio", "hora", "t_seco", "t_humedo", "t_max", "t_min",
    "punto_rocio", "tension_vapor", "humedad_relativa", "t_adjunto",
    "barometro", "p_n_estacion", "p_n_mar", "pnm_hpa", "lluvia",
    "hora_verificacion", "_vacio", "acum_diario_fecha", "acum_diario_mm",
]

# Para la validación "liviana" del encabezado: alguna de estas palabras
# clave debería aparecer (sin acentos, mayúsculas) en los primeros title.
PALABRAS_CLAVE_ENCABEZADO = ["FECHA", "HORA", "SECO", "HUMEDO", "BAROMETRO", "LLUVIA"]


class ErrorImportacion(Exception):
    pass


def _sin_acentos(texto):
    reemplazos = str.maketrans("ÁÉÍÓÚÑáéíóúñ", "AEIOUNaeioun")
    return texto.translate(reemplazos)


def _texto_celda(valor):
    if valor is None:
        return ""
    return _sin_acentos(str(valor)).strip().upper()


def _encabezado_parece_valido(fila_encabezado):
    texto_completo = " ".join(_texto_celda(c) for c in fila_encabezado)
    encontradas = sum(1 for palabra in PALABRAS_CLAVE_ENCABEZADO if palabra in texto_completo)
    return encontradas >= len(PALABRAS_CLAVE_ENCABEZADO) - 1  # tolera que falte una


def _a_numero(valor):
    """Un valor de celda numérico puede venir ya como float (lo normal si
    Excel lo guardó como número) o como texto con coma decimal (si se
    tipeó como texto en algún archivo viejo) — se contemplan los dos
    casos. Celda vacía o "/" (código histórico de "sin dato") -> None."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if texto == "" or texto == "/":
        return None
    texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _a_fecha_iso(valor_fecha, valor_anio, nombre_archivo, num_fila):
    """FECHA viene como "dd/mm" (string) o como un valor de fecha real de
    Excel (datetime/date, con el año que Excel le haya puesto por
    defecto, que no interesa) — en los dos casos el año real está en la
    columna AÑO aparte, nunca en FECHA."""
    anio = _a_numero(valor_anio)
    if anio is None:
        raise ErrorImportacion(
            f"{nombre_archivo}, fila {num_fila}: falta el año (columna AÑO)."
        )
    anio = int(anio)

    if isinstance(valor_fecha, (datetime.datetime, datetime.date)):
        mes, dia = valor_fecha.month, valor_fecha.day
    else:
        texto = str(valor_fecha).strip()
        partes = texto.split("/")
        if len(partes) < 2:
            raise ErrorImportacion(
                f"{nombre_archivo}, fila {num_fila}: no se pudo interpretar la fecha '{texto}'."
            )
        dia, mes = int(partes[0]), int(partes[1])

    try:
        return datetime.date(anio, mes, dia).isoformat()
    except ValueError as e:
        raise ErrorImportacion(f"{nombre_archivo}, fila {num_fila}: fecha inválida ({e}).")


def _a_hora_hhmm(valor_hora, nombre_archivo, num_fila):
    hora_num = _a_numero(valor_hora)
    if hora_num is None:
        raise ErrorImportacion(f"{nombre_archivo}, fila {num_fila}: falta la hora.")
    return f"{int(hora_num):02d}:00"


def _filas_xlsx(ruta):
    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hoja = libro.worksheets[0]
    for fila in hoja.iter_rows(values_only=True):
        yield fila
    libro.close()


def _filas_xls(ruta):
    if xlrd is None:
        raise ErrorImportacion(
            f"{os.path.basename(ruta)}: es un .xls (formato viejo de Excel) y falta instalar "
            "la librería 'xlrd' para poder leerlo (pip install xlrd)."
        )
    libro = xlrd.open_workbook(ruta)
    hoja = libro.sheet_by_index(0)
    for num_fila in range(hoja.nrows):
        fila = []
        for num_col in range(hoja.ncols):
            celda = hoja.cell(num_fila, num_col)
            if celda.ctype == xlrd.XL_CELL_DATE:
                # En .xls las fechas se guardan como número de serie, no
                # como texto ni como un objeto fecha — hay que convertirlas
                # a mano con el "datemode" de ese libro en particular.
                fila.append(xlrd.xldate_as_datetime(celda.value, libro.datemode))
            elif celda.ctype == xlrd.XL_CELL_EMPTY:
                fila.append(None)
            else:
                fila.append(celda.value)
        yield fila


def leer_archivo(ruta, avisos=None):
    """Lee un Excel anual completo (.xlsx o .xls) y devuelve una lista de
    filas (dict) listas para guardar en la base. `avisos`, si se pasa una
    lista, se le van agregando los mensajes de advertencia (filas
    salteadas, etc.) sin interrumpir la importación del resto del archivo."""
    if avisos is None:
        avisos = []
    nombre_archivo = os.path.basename(ruta)

    es_xls_viejo = ruta.lower().endswith(".xls") and not ruta.lower().endswith(".xlsx")
    filas_iter = _filas_xls(ruta) if es_xls_viejo else _filas_xlsx(ruta)

    try:
        encabezado = next(filas_iter)
    except StopIteration:
        raise ErrorImportacion(f"{nombre_archivo}: el archivo está vacío.")

    if not _encabezado_parece_valido(encabezado):
        avisos.append(
            f"{nombre_archivo}: el encabezado no se parece al formato esperado "
            "(¿cambió el orden de columnas en este archivo? revisalo a mano) — "
            "se intenta importar igual."
        )

    resultado = []
    for num_fila, fila in enumerate(filas_iter, start=2):
        if fila is None or all(c is None or str(c).strip() == "" for c in fila):
            continue  # fila completamente vacía (común al final de la hoja)
        fila = list(fila) + [None] * (len(POSICIONES) - len(fila))  # por si la fila viene corta

        try:
            fecha = _a_fecha_iso(fila[0], fila[1], nombre_archivo, num_fila)
            hora = _a_hora_hhmm(fila[2], nombre_archivo, num_fila)
        except ErrorImportacion as e:
            avisos.append(f"{e} Se saltea esa fila.")
            continue

        dato = {
            "fecha": fecha, "hora": hora,
            "t_seco": _a_numero(fila[3]), "t_humedo": _a_numero(fila[4]),
            "t_max": _a_numero(fila[5]), "t_min": _a_numero(fila[6]),
            "punto_rocio": _a_numero(fila[7]), "tension_vapor": _a_numero(fila[8]),
            "humedad_relativa": _a_numero(fila[9]), "t_adjunto": _a_numero(fila[10]),
            "barometro": _a_numero(fila[11]), "p_n_estacion": _a_numero(fila[12]),
            "p_n_mar": _a_numero(fila[13]), "pnm_hpa": _a_numero(fila[14]),
            "lluvia": _a_numero(fila[15]),
            "hora_verificacion": "" if fila[16] is None else str(fila[16]).strip(),
            "acum_diario_fecha": "" if fila[18] is None else str(fila[18]).strip(),
            "acum_diario_mm": _a_numero(fila[19]),
            "archivo_origen": nombre_archivo,
            "fila_origen": num_fila,
        }
        resultado.append(dato)

    return resultado


EXTENSIONES_VALIDAS = (".xlsx", ".xlsm", ".xls")


def listar_excels(carpeta):
    return sorted(
        os.path.join(carpeta, nombre)
        for nombre in os.listdir(carpeta)
        if nombre.lower().endswith(EXTENSIONES_VALIDAS) and not nombre.startswith("~$")
    )
