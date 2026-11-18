"""
Archivo Histórico de Observaciones — visor standalone.

Importa los Excel anuales (uno por año, mismo formato desde hace décadas)
a una base SQLite local, y permite elegir una variable + un período para
graficarlo, verlo en tabla, exportarlo a CSV, buscar valores extremos
(máximos/mínimos con fecha), ver la climatología mensual/estacional y
armar un informe de una estación del año puntual contra lo normal.
"""
import csv
import os
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk

import config
import db
import importador
from rutas import ruta_recurso

COLOR_ACENTO = "#1e3a8a"
COLOR_MAXIMO = "#b91c1c"
COLOR_MINIMO = "#1d4ed8"

VARIABLES_GRAFICO = [
    ("t_seco", "T. Seco (°C)"),
    ("t_humedo", "T. Húmedo (°C)"),
    ("t_max", "T. Máx (°C)"),
    ("t_min", "T. Mín (°C)"),
    ("punto_rocio", "Punto de Rocío (°C)"),
    ("tension_vapor", "Tensión de Vapor (hPa)"),
    ("humedad_relativa", "Humedad Relativa (%)"),
    ("barometro", "Barómetro (mmHg)"),
    ("p_n_estacion", "P. Nivel Estación (mmHg)"),
    ("p_n_mar", "P. Nivel Mar (mmHg)"),
    ("pnm_hpa", "P. Nivel Mar (hPa)"),
    ("lluvia", "Lluvia (mm)"),
]
ETIQUETAS_VARIABLE = {clave: etiqueta for clave, etiqueta in VARIABLES_GRAFICO}
ESTACIONES_PLURAL = ["veranos", "otoños", "inviernos", "primaveras"]


def _fecha_ddmmaaaa(fecha_iso):
    anio, mes, dia = fecha_iso[:10].split("-")
    return f"{dia}/{mes}/{anio}"


def _parsear_fecha_usuario(texto):
    texto = texto.strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return None


def _fmt_valor(valor, decimales=1):
    return f"{valor:.{decimales}f}" if isinstance(valor, (int, float)) else "—"


def _combo_variable(padre, ancho=26):
    """Combobox con las variables disponibles, para reusar en cada pestaña."""
    combo = ttk.Combobox(padre, state="readonly", width=ancho, values=[e for _c, e in VARIABLES_GRAFICO])
    combo.current(0)
    return combo


def _variable_elegida(combo):
    return VARIABLES_GRAFICO[combo.current()]


class App(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title("Archivo Histórico — Estación La Plata Observatorio")
        self.geometry("1150x880")
        try:
            self.iconbitmap(ruta_recurso("icono.ico"))
        except tk.TclError:
            pass  # en Linux/Mac iconbitmap no siempre acepta .ico; no es crítico
        self._imagenes = []  # mantiene referencias vivas para que Tkinter no las libere
        self._datos_periodo_actual = []

        self._armar_encabezado()
        self._armar_importar()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        tab_visor = ttk.Frame(notebook, padding=10)
        tab_extremos = ttk.Frame(notebook, padding=10)
        tab_clima_mensual = ttk.Frame(notebook, padding=10)
        tab_clima_estacional = ttk.Frame(notebook, padding=10)
        tab_informe = ttk.Frame(notebook, padding=10)
        notebook.add(tab_visor, text="Ver / graficar")
        notebook.add(tab_extremos, text="Extremos")
        notebook.add(tab_clima_mensual, text="Climatología mensual")
        notebook.add(tab_clima_estacional, text="Climatología estacional")
        notebook.add(tab_informe, text="Informe de una estación")

        self._armar_visor(tab_visor)
        self._armar_extremos(tab_extremos)
        self._armar_climatologia_mensual(tab_clima_mensual)
        self._armar_climatologia_estacional(tab_clima_estacional)
        self._armar_informe_estacional(tab_informe)

        self._actualizar_rango_disponible()

    # ---------- Encabezado ----------

    def _armar_encabezado(self):
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=12, pady=(12, 0))

        logo = self._cargar_imagen("logo-historico.png", ancho=44)
        if logo:
            logo_marco = ttk.Frame(frame, bootstyle="light", padding=5)
            logo_marco.pack(side="left", padx=(0, 10))
            ttk.Label(logo_marco, image=logo, bootstyle="light").pack()

        titulos = ttk.Frame(frame)
        titulos.pack(side="left")
        ttk.Label(titulos, text="Archivo Histórico de Observaciones", font=("Georgia", 16, "bold")).pack(anchor="w")
        self.label_rango = ttk.Label(titulos, text="", bootstyle="secondary")
        self.label_rango.pack(anchor="w")

    def _cargar_imagen(self, nombre_archivo, ancho=320):
        ruta = ruta_recurso("img", nombre_archivo)
        if not os.path.exists(ruta):
            return None
        img = Image.open(ruta)
        proporcion = ancho / img.width
        img = img.resize((ancho, int(img.height * proporcion)))
        foto = ImageTk.PhotoImage(img)
        self._imagenes.append(foto)  # evita que el garbage collector la borre
        return foto

    # ---------- Importar ----------

    def _armar_importar(self):
        marco = ttk.Labelframe(self, text=" Importar desde Excel ", padding=10)
        marco.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(
            marco,
            text="\"Importar todo\" lee todos los Excel de una carpeta (usalo la primera vez, "
            "o si agregaste años viejos nuevos). \"Actualizar año actual\" solo vuelve a leer "
            "el archivo de este año — para usar seguido, sin tener que re-leer 50 años cada vez.",
            wraplength=1000, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        barra = ttk.Frame(marco)
        barra.pack(fill="x")
        self.boton_importar = ttk.Button(
            barra, text="Importar todo...", command=self._elegir_carpeta_e_importar, bootstyle="secondary-outline",
        )
        self.boton_importar.pack(side="left")
        self.boton_actualizar = ttk.Button(
            barra, text="Actualizar año actual", command=self._actualizar_anio_actual, bootstyle="primary",
        )
        self.boton_actualizar.pack(side="left", padx=(8, 0))
        self.progreso = ttk.Progressbar(barra, mode="determinate")
        self.progreso.pack(side="left", fill="x", expand=True, padx=(10, 0))

        self.label_estado_import = ttk.Label(marco, text="", bootstyle="secondary")
        self.label_estado_import.pack(anchor="w", pady=(6, 0))

    def _elegir_carpeta_e_importar(self):
        carpeta = filedialog.askdirectory(title="Carpeta con los Excel anuales")
        if not carpeta:
            return
        archivos = importador.listar_excels(carpeta)
        if not archivos:
            messagebox.showinfo("Importar", "No se encontraron archivos .xlsx/.xls en esa carpeta.")
            return
        config.guardar({"carpeta_excels": carpeta})
        self._iniciar_importacion(archivos)

    def _actualizar_anio_actual(self):
        carpeta = config.cargar().get("carpeta_excels")
        if not carpeta or not os.path.isdir(carpeta):
            messagebox.showinfo(
                "Actualizar año actual",
                "Todavía no se usó 'Importar todo' para indicar en qué carpeta están los "
                "Excel — elegila ahora, después 'Actualizar año actual' ya la va a recordar sola.",
            )
            carpeta = filedialog.askdirectory(title="Carpeta con los Excel anuales")
            if not carpeta:
                return
            config.guardar({"carpeta_excels": carpeta})

        anio_actual = str(datetime.now().year)
        archivos = importador.listar_excels(carpeta)
        candidatos = [a for a in archivos if anio_actual in os.path.basename(a)]
        if not candidatos:
            messagebox.showwarning(
                "Actualizar año actual",
                f"No encontré ningún archivo con '{anio_actual}' en el nombre dentro de:\n{carpeta}\n\n"
                "Revisá que el archivo de este año ya exista ahí, o usá 'Importar todo' si cambió de carpeta.",
            )
            return
        self._iniciar_importacion(candidatos)

    def _iniciar_importacion(self, archivos):
        self.boton_importar.config(state="disabled")
        self.boton_actualizar.config(state="disabled")
        self.progreso.configure(maximum=len(archivos), value=0)
        threading.Thread(target=self._importar_en_hilo, args=(archivos,), daemon=True).start()

    def _importar_en_hilo(self, archivos):
        total_filas = 0
        avisos = []
        errores = []
        for i, ruta in enumerate(archivos):
            nombre = os.path.basename(ruta)
            self.after(0, lambda n=nombre: self.label_estado_import.config(text=f"Importando {n}..."))
            try:
                filas = importador.leer_archivo(ruta, avisos=avisos)
                if filas:
                    db.upsert_muchas(filas)
                total_filas += len(filas)
            except Exception as e:
                errores.append(f"{nombre}: {e}")
            self.after(0, lambda v=i + 1: self.progreso.configure(value=v))
        self.after(0, lambda: self._importacion_terminada(len(archivos), total_filas, avisos, errores))

    def _importacion_terminada(self, n_archivos, total_filas, avisos, errores):
        self.boton_importar.config(state="normal")
        self.boton_actualizar.config(state="normal")
        self.label_estado_import.config(
            text=f"Listo: {n_archivos} archivo(s) procesados, {total_filas} observaciones importadas."
        )
        self._actualizar_rango_disponible()

        mensaje = f"Se importaron {total_filas} observaciones de {n_archivos} archivo(s)."
        if avisos:
            mensaje += f"\n\n{len(avisos)} aviso(s) (filas salteadas o encabezados con pinta rara):\n"
            mensaje += "\n".join(avisos[:15])
            if len(avisos) > 15:
                mensaje += f"\n...y {len(avisos) - 15} más (revisá esos archivos a mano)."
        if errores:
            mensaje += f"\n\n{len(errores)} archivo(s) con error (no se pudieron leer):\n"
            mensaje += "\n".join(errores[:15])
        messagebox.showinfo("Importación terminada", mensaje)

    def _actualizar_rango_disponible(self):
        n = db.contar()
        if n == 0:
            self.label_rango.config(text="Base vacía — importá los Excel para empezar.")
            return
        fecha_min, fecha_max = db.rango_fechas()
        self.label_rango.config(
            text=f"{n} observaciones guardadas, desde {_fecha_ddmmaaaa(fecha_min)} hasta {_fecha_ddmmaaaa(fecha_max)}."
        )
        # Si los campos de fecha están vacíos (primera vez), precarga el
        # último mes disponible en el visor — así alcanza con tocar
        # "Graficar" una vez para ver algo — y todo el período en Extremos,
        # que de entrada tiene más sentido buscar en toda la base.
        if not self.entrada_desde.get().strip() and not self.entrada_hasta.get().strip():
            hasta = datetime.strptime(fecha_max, "%Y-%m-%d").date()
            desde = hasta - timedelta(days=30)
            self.entrada_desde.insert(0, desde.strftime("%d/%m/%Y"))
            self.entrada_hasta.insert(0, hasta.strftime("%d/%m/%Y"))
        if not self.extremos_desde.get().strip() and not self.extremos_hasta.get().strip():
            self.extremos_desde.insert(0, _fecha_ddmmaaaa(fecha_min))
            self.extremos_hasta.insert(0, _fecha_ddmmaaaa(fecha_max))

    # ---------- Visor ----------

    def _armar_visor(self, marco):
        ttk.Label(
            marco, text="Elegí una variable y un período para ver su evolución, en gráfico y en tabla.",
            bootstyle="secondary",
        ).pack(anchor="w", pady=(0, 8))

        barra = ttk.Frame(marco)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Variable:").pack(side="left", padx=(0, 6))
        self.combo_variable = _combo_variable(barra, ancho=24)
        self.combo_variable.pack(side="left", padx=(0, 16))

        ttk.Label(barra, text="Desde:").pack(side="left", padx=(0, 4))
        self.entrada_desde = ttk.Entry(barra, width=12)
        self.entrada_desde.pack(side="left", padx=(0, 12))
        ttk.Label(barra, text="Hasta:").pack(side="left", padx=(0, 4))
        self.entrada_hasta = ttk.Entry(barra, width=12)
        self.entrada_hasta.pack(side="left", padx=(0, 12))
        ttk.Label(barra, text="(dd/mm/aaaa)", bootstyle="secondary").pack(side="left")

        ttk.Button(barra, text="Graficar", command=self._graficar, bootstyle="primary").pack(side="right")
        ttk.Button(
            barra, text="Exportar período a CSV", command=self._exportar_csv, bootstyle="secondary-outline",
        ).pack(side="right", padx=(0, 8))

        marco_grafico = ttk.Frame(marco)
        marco_grafico.pack(fill="both", expand=True)
        self.figura = Figure(figsize=(9, 3.2), dpi=100)
        self.ejes = self.figura.add_subplot(111)
        self.lienzo = FigureCanvasTkAgg(self.figura, master=marco_grafico)
        self.lienzo.get_tk_widget().pack(fill="both", expand=True)

        self.label_aviso_tabla = ttk.Label(marco, text="", bootstyle="warning")
        self.label_aviso_tabla.pack(anchor="w", pady=(6, 0))

        columnas_tabla = [c for c, _e in db.COLUMNAS]
        self.tabla = ttk.Treeview(marco, columns=columnas_tabla, show="headings", height=8, bootstyle="secondary")
        for clave, titulo in db.COLUMNAS:
            self.tabla.heading(clave, text=titulo)
            self.tabla.column(clave, width=90, anchor="center")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview, bootstyle="round")
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True, pady=(4, 0))
        scroll.pack(side="right", fill="y", pady=(4, 0))

    def _graficar(self):
        fecha_desde = _parsear_fecha_usuario(self.entrada_desde.get())
        fecha_hasta = _parsear_fecha_usuario(self.entrada_hasta.get())
        if not fecha_desde or not fecha_hasta:
            messagebox.showerror("Fechas inválidas", "Escribí las fechas como dd/mm/aaaa.")
            return
        if fecha_desde > fecha_hasta:
            messagebox.showerror("Fechas inválidas", "La fecha 'Desde' tiene que ser anterior a 'Hasta'.")
            return

        datos = db.listar_periodo(fecha_desde, fecha_hasta)
        self._datos_periodo_actual = datos
        self._refrescar_tabla(datos)
        self._dibujar_grafico(datos)

    def _refrescar_tabla(self, datos):
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        tope = 2000  # no trabar la interfaz si se pide un período de años enteros
        for fila in datos[:tope]:
            self.tabla.insert("", tk.END, values=[fila.get(clave) for clave, _e in db.COLUMNAS])
        if len(datos) > tope:
            self.label_aviso_tabla.config(
                text=f"La tabla muestra solo las primeras {tope} filas de {len(datos)} — "
                "para ver todo el período, usá 'Exportar período a CSV'."
            )
        else:
            self.label_aviso_tabla.config(text="")

    def _dibujar_grafico(self, datos):
        clave, etiqueta = _variable_elegida(self.combo_variable)
        self.ejes.clear()

        if not datos:
            self.ejes.text(0.5, 0.5, "Sin datos en ese período", ha="center", va="center", color="#94a3b8")
            self.ejes.set_xticks([])
        else:
            etiquetas_x = [f"{_fecha_ddmmaaaa(f['fecha'])} {f['hora']}" for f in datos]
            valores_y = [
                f.get(clave) if isinstance(f.get(clave), (int, float)) else float("nan") for f in datos
            ]
            xs = list(range(len(datos)))
            self.ejes.plot(xs, valores_y, color=COLOR_ACENTO, linewidth=1.1)

            valores_validos = [v for v in valores_y if v == v]
            if valores_validos:
                v_min, v_max = min(valores_validos), max(valores_validos)
                margen = (v_max - v_min) * 0.1 or 1.0
                self.ejes.set_ylim(v_min - margen, v_max + margen)

            paso = max(1, len(xs) // 12)
            ticks = xs[::paso]
            self.ejes.set_xticks(ticks)
            self.ejes.set_xticklabels([etiquetas_x[i] for i in ticks], rotation=30, ha="right", fontsize=7)

        self.ejes.set_title(etiqueta, fontsize=10, color="#334155")
        self.ejes.grid(True, alpha=0.25)
        self.figura.tight_layout()
        self.lienzo.draw()

    def _exportar_csv(self):
        if not self._datos_periodo_actual:
            messagebox.showinfo("Exportar a CSV", "Primero graficá un período (botón 'Graficar').")
            return
        ruta = filedialog.asksaveasfilename(
            title="Exportar período a CSV", defaultextension=".csv",
            initialfile="historico_periodo.csv", filetypes=[("CSV (separado por comas)", "*.csv")],
        )
        if not ruta:
            return
        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                f.write("sep=,\n")  # para que Excel en configuración regional argentina no mezcle todo en una columna
                escritor = csv.writer(f)
                escritor.writerow([etiqueta for _c, etiqueta in db.COLUMNAS])
                for fila in self._datos_periodo_actual:
                    escritor.writerow([fila.get(clave) for clave, _e in db.COLUMNAS])
        except Exception as e:
            messagebox.showerror("No se pudo exportar", str(e))
            return
        messagebox.showinfo(
            "Exportar a CSV", f"Se exportaron {len(self._datos_periodo_actual)} observaciones a:\n{ruta}"
        )

    # ---------- Extremos ----------

    def _armar_extremos(self, marco):
        ttk.Label(
            marco,
            text="Busca el valor más alto y más bajo registrado para una variable en un período, "
            "con la fecha y hora exactas — y el resto del ranking de los 10 más extremos.",
            bootstyle="secondary", wraplength=1000, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        barra = ttk.Frame(marco)
        barra.pack(fill="x", pady=(0, 10))
        ttk.Label(barra, text="Variable:").pack(side="left", padx=(0, 6))
        self.combo_extremos_variable = _combo_variable(barra)
        self.combo_extremos_variable.pack(side="left", padx=(0, 16))
        ttk.Label(barra, text="Desde:").pack(side="left", padx=(0, 4))
        self.extremos_desde = ttk.Entry(barra, width=12)
        self.extremos_desde.pack(side="left", padx=(0, 12))
        ttk.Label(barra, text="Hasta:").pack(side="left", padx=(0, 4))
        self.extremos_hasta = ttk.Entry(barra, width=12)
        self.extremos_hasta.pack(side="left", padx=(0, 12))
        ttk.Button(barra, text="Buscar extremos", command=self._buscar_extremos, bootstyle="primary").pack(side="right")

        resumen = ttk.Frame(marco)
        resumen.pack(fill="x", pady=(0, 10))
        self.caja_maximo = self._armar_caja_extremo(resumen, "MÁXIMO", COLOR_MAXIMO)
        self.caja_minimo = self._armar_caja_extremo(resumen, "MÍNIMO", COLOR_MINIMO)

        rankings = ttk.Frame(marco)
        rankings.pack(fill="both", expand=True)
        rankings.columnconfigure(0, weight=1)
        rankings.columnconfigure(1, weight=1)

        marco_max = ttk.Labelframe(rankings, text=" Top 10 más altos ", padding=8)
        marco_max.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.tabla_max = self._armar_tabla_ranking(marco_max)

        marco_min = ttk.Labelframe(rankings, text=" Top 10 más bajos ", padding=8)
        marco_min.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.tabla_min = self._armar_tabla_ranking(marco_min)

    def _armar_caja_extremo(self, padre, titulo, color):
        caja = ttk.Frame(padre, bootstyle="light", padding=12)
        caja.pack(side="left", fill="x", expand=True, padx=(0, 10) if titulo == "MÁXIMO" else (10, 0))
        ttk.Label(caja, text=titulo, font=("Segoe UI", 9, "bold"), foreground=color).pack(anchor="w")
        label_valor = ttk.Label(caja, text="—", font=("Georgia", 22, "bold"))
        label_valor.pack(anchor="w")
        label_fecha = ttk.Label(caja, text="", bootstyle="secondary")
        label_fecha.pack(anchor="w")
        return {"valor": label_valor, "fecha": label_fecha}

    def _armar_tabla_ranking(self, padre):
        tabla = ttk.Treeview(padre, columns=("fecha", "hora", "valor"), show="headings", height=10, bootstyle="secondary")
        tabla.heading("fecha", text="Fecha")
        tabla.heading("hora", text="Hora")
        tabla.heading("valor", text="Valor")
        for c in ("fecha", "hora", "valor"):
            tabla.column(c, width=90, anchor="center")
        tabla.pack(fill="both", expand=True)
        return tabla

    def _buscar_extremos(self):
        fecha_desde = _parsear_fecha_usuario(self.extremos_desde.get())
        fecha_hasta = _parsear_fecha_usuario(self.extremos_hasta.get())
        if not fecha_desde or not fecha_hasta:
            messagebox.showerror("Fechas inválidas", "Escribí las fechas como dd/mm/aaaa.")
            return
        if fecha_desde > fecha_hasta:
            messagebox.showerror("Fechas inválidas", "La fecha 'Desde' tiene que ser anterior a 'Hasta'.")
            return

        clave, etiqueta = _variable_elegida(self.combo_extremos_variable)
        maximos, minimos = db.extremos(clave, fecha_desde, fecha_hasta, n=10)

        for tabla in (self.tabla_max, self.tabla_min):
            for item in tabla.get_children():
                tabla.delete(item)

        if maximos:
            self.caja_maximo["valor"].config(text=_fmt_valor(maximos[0]["v"]))
            self.caja_maximo["fecha"].config(text=f"{_fecha_ddmmaaaa(maximos[0]['fecha'])} {maximos[0]['hora']}")
        else:
            self.caja_maximo["valor"].config(text="—")
            self.caja_maximo["fecha"].config(text="Sin datos en el período")
        for fila in maximos:
            self.tabla_max.insert("", tk.END, values=(_fecha_ddmmaaaa(fila["fecha"]), fila["hora"], _fmt_valor(fila["v"])))

        if minimos:
            self.caja_minimo["valor"].config(text=_fmt_valor(minimos[0]["v"]))
            self.caja_minimo["fecha"].config(text=f"{_fecha_ddmmaaaa(minimos[0]['fecha'])} {minimos[0]['hora']}")
        else:
            self.caja_minimo["valor"].config(text="—")
            self.caja_minimo["fecha"].config(text="Sin datos en el período")
        for fila in minimos:
            self.tabla_min.insert("", tk.END, values=(_fecha_ddmmaaaa(fila["fecha"]), fila["hora"], _fmt_valor(fila["v"])))

        if not maximos and not minimos:
            messagebox.showinfo("Extremos", f"No hay datos de {etiqueta} en ese período.")

    # ---------- Climatología mensual ----------

    def _armar_climatologia_mensual(self, marco):
        ttk.Label(
            marco,
            text="Promedio histórico de cada mes (o total acumulado, para la lluvia) a lo largo de todos "
            "los años cargados, con el año en que ese mes tuvo el valor más alto y el más bajo.",
            bootstyle="secondary", wraplength=1000, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        barra = ttk.Frame(marco)
        barra.pack(fill="x", pady=(0, 10))
        ttk.Label(barra, text="Variable:").pack(side="left", padx=(0, 6))
        self.combo_clima_mensual = _combo_variable(barra)
        self.combo_clima_mensual.pack(side="left", padx=(0, 16))
        ttk.Button(barra, text="Calcular", command=self._calcular_climatologia_mensual, bootstyle="primary").pack(side="left")

        cuerpo = ttk.Frame(marco)
        cuerpo.pack(fill="both", expand=True)

        marco_grafico = ttk.Frame(cuerpo)
        marco_grafico.pack(fill="x", pady=(0, 10))
        self.figura_clima_mensual = Figure(figsize=(9, 2.6), dpi=100)
        self.ejes_clima_mensual = self.figura_clima_mensual.add_subplot(111)
        self.lienzo_clima_mensual = FigureCanvasTkAgg(self.figura_clima_mensual, master=marco_grafico)
        self.lienzo_clima_mensual.get_tk_widget().pack(fill="both", expand=True)

        columnas = ("etiqueta", "promedio", "maximo", "anio_maximo", "minimo", "anio_minimo", "n_anios")
        self.tabla_clima_mensual = ttk.Treeview(cuerpo, columns=columnas, show="headings", height=12, bootstyle="secondary")
        titulos = {
            "etiqueta": "Mes", "promedio": "Promedio", "maximo": "Máximo", "anio_maximo": "Año (máx)",
            "minimo": "Mínimo", "anio_minimo": "Año (mín)", "n_anios": "Años con datos",
        }
        for c in columnas:
            self.tabla_clima_mensual.heading(c, text=titulos[c])
            self.tabla_clima_mensual.column(c, width=100, anchor="center")
        self.tabla_clima_mensual.pack(fill="both", expand=True)

    def _calcular_climatologia_mensual(self):
        clave, etiqueta = _variable_elegida(self.combo_clima_mensual)
        filas = db.climatologia_mensual(clave)
        es_total = clave in db.VARIABLES_EXTENSIVAS
        titulo_valor = "Total" if es_total else "Promedio"
        self.tabla_clima_mensual.heading("promedio", text=titulo_valor)

        for item in self.tabla_clima_mensual.get_children():
            self.tabla_clima_mensual.delete(item)
        for fila in filas:
            self.tabla_clima_mensual.insert("", tk.END, values=(
                fila["etiqueta"], _fmt_valor(fila["promedio"]), _fmt_valor(fila["maximo"]),
                fila["anio_maximo"] or "", _fmt_valor(fila["minimo"]), fila["anio_minimo"] or "",
                fila["n_anios"],
            ))

        self.ejes_clima_mensual.clear()
        if any(f["n_anios"] for f in filas):
            xs = list(range(12))
            promedios = [f["promedio"] if f["promedio"] is not None else 0 for f in filas]
            self.ejes_clima_mensual.bar(xs, promedios, color=COLOR_ACENTO, alpha=0.75, width=0.6)
            for i, f in enumerate(filas):
                if f["maximo"] is not None:
                    self.ejes_clima_mensual.scatter(i, f["maximo"], color=COLOR_MAXIMO, zorder=3, s=18)
                if f["minimo"] is not None:
                    self.ejes_clima_mensual.scatter(i, f["minimo"], color=COLOR_MINIMO, zorder=3, s=18)
            self.ejes_clima_mensual.set_xticks(xs)
            self.ejes_clima_mensual.set_xticklabels([f["etiqueta"][:3] for f in filas], fontsize=8)
            self.ejes_clima_mensual.set_title(
                f"{etiqueta} — {titulo_valor.lower()} por mes (puntos: máximo y mínimo histórico)",
                fontsize=9, color="#334155",
            )
            self.ejes_clima_mensual.grid(True, axis="y", alpha=0.25)
        else:
            self.ejes_clima_mensual.text(0.5, 0.5, "Sin datos", ha="center", va="center", color="#94a3b8")
            self.ejes_clima_mensual.set_xticks([])
        self.figura_clima_mensual.tight_layout()
        self.lienzo_clima_mensual.draw()

    # ---------- Climatología estacional ----------

    def _armar_climatologia_estacional(self, marco):
        ttk.Label(
            marco,
            text="Lo mismo que la climatología mensual, pero agrupado de a 3 meses "
            "(Verano/Otoño/Invierno/Primavera). El verano incluye diciembre del año anterior "
            "(ej. \"Verano 1991\" = dic 1990 + ene y feb 1991).",
            bootstyle="secondary", wraplength=1000, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        barra = ttk.Frame(marco)
        barra.pack(fill="x", pady=(0, 10))
        ttk.Label(barra, text="Variable:").pack(side="left", padx=(0, 6))
        self.combo_clima_estacional = _combo_variable(barra)
        self.combo_clima_estacional.pack(side="left", padx=(0, 16))
        ttk.Button(barra, text="Calcular", command=self._calcular_climatologia_estacional, bootstyle="primary").pack(side="left")

        columnas = ("etiqueta", "promedio", "maximo", "anio_maximo", "minimo", "anio_minimo", "n_anios")
        self.tabla_clima_estacional = ttk.Treeview(marco, columns=columnas, show="headings", height=6, bootstyle="secondary")
        titulos = {
            "etiqueta": "Estación", "promedio": "Promedio", "maximo": "Máximo", "anio_maximo": "Año (máx)",
            "minimo": "Mínimo", "anio_minimo": "Año (mín)", "n_anios": "Años con datos",
        }
        for c in columnas:
            self.tabla_clima_estacional.heading(c, text=titulos[c])
            self.tabla_clima_estacional.column(c, width=110, anchor="center")
        self.tabla_clima_estacional.pack(fill="x", pady=(0, 10))

    def _calcular_climatologia_estacional(self):
        clave, _etiqueta = _variable_elegida(self.combo_clima_estacional)
        filas = db.climatologia_estacional(clave)
        es_total = clave in db.VARIABLES_EXTENSIVAS
        self.tabla_clima_estacional.heading("promedio", text="Total" if es_total else "Promedio")

        for item in self.tabla_clima_estacional.get_children():
            self.tabla_clima_estacional.delete(item)
        for fila in filas:
            self.tabla_clima_estacional.insert("", tk.END, values=(
                fila["etiqueta"], _fmt_valor(fila["promedio"]), _fmt_valor(fila["maximo"]),
                fila["anio_maximo"] or "", _fmt_valor(fila["minimo"]), fila["anio_minimo"] or "",
                fila["n_anios"],
            ))

    # ---------- Informe de una estación puntual ----------

    def _armar_informe_estacional(self, marco):
        ttk.Label(
            marco,
            text="Compara una estación del año puntual (ej. \"Invierno 2025\") contra el promedio "
            "histórico de esa misma estación, para todas las variables a la vez.",
            bootstyle="secondary", wraplength=1000, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        barra = ttk.Frame(marco)
        barra.pack(fill="x", pady=(0, 10))
        ttk.Label(barra, text="Estación:").pack(side="left", padx=(0, 6))
        self.combo_informe_estacion = ttk.Combobox(
            barra, state="readonly", width=14, values=db.ESTACIONES_NOMBRE,
        )
        self.combo_informe_estacion.current(2)  # Invierno, la más consultada en una estación meteorológica
        self.combo_informe_estacion.pack(side="left", padx=(0, 16))
        ttk.Label(barra, text="Año:").pack(side="left", padx=(0, 4))
        self.entrada_informe_anio = ttk.Entry(barra, width=8)
        self.entrada_informe_anio.insert(0, str(datetime.now().year))
        self.entrada_informe_anio.pack(side="left", padx=(0, 6))
        ttk.Label(
            barra, text="(para Verano, el año de enero/febrero — ej. 2025 para dic 2024 a feb 2025)",
            bootstyle="secondary",
        ).pack(side="left", padx=(0, 16))
        ttk.Button(barra, text="Generar informe", command=self._generar_informe_estacional, bootstyle="primary").pack(side="left")

        columnas = ("variable", "valor_estacion", "promedio_historico", "diferencia")
        self.tabla_informe = ttk.Treeview(marco, columns=columnas, show="headings", height=13, bootstyle="secondary")
        titulos = {
            "variable": "Variable", "valor_estacion": "Esta estación", "promedio_historico": "Promedio histórico",
            "diferencia": "Diferencia",
        }
        for c in columnas:
            self.tabla_informe.heading(c, text=titulos[c])
            self.tabla_informe.column(c, width=150 if c != "variable" else 180, anchor="center")
        self.tabla_informe.pack(fill="both", expand=True, pady=(0, 8))

        self.label_informe_aviso = ttk.Label(marco, text="", bootstyle="warning")
        self.label_informe_aviso.pack(anchor="w")

    def _generar_informe_estacional(self):
        estacion_idx = self.combo_informe_estacion.current()
        texto_anio = self.entrada_informe_anio.get().strip()
        if not texto_anio.isdigit():
            messagebox.showerror("Año inválido", "Escribí el año como un número (ej. 2025).")
            return
        anio_periodo = int(texto_anio)

        for item in self.tabla_informe.get_children():
            self.tabla_informe.delete(item)

        hubo_datos = False
        for clave, etiqueta in VARIABLES_GRAFICO:
            valor_puntual = db.resumen_estacion_puntual(clave, estacion_idx, anio_periodo)
            historico = db.climatologia_estacional(clave)[estacion_idx]
            promedio_historico = historico["promedio"]

            if valor_puntual is None and promedio_historico is None:
                continue
            hubo_datos = hubo_datos or valor_puntual is not None

            if valor_puntual is not None and promedio_historico is not None:
                diferencia = valor_puntual - promedio_historico
                signo = "+" if diferencia >= 0 else ""
                texto_diferencia = f"{signo}{diferencia:.1f}"
            else:
                texto_diferencia = "—"

            self.tabla_informe.insert("", tk.END, values=(
                etiqueta, _fmt_valor(valor_puntual), _fmt_valor(promedio_historico), texto_diferencia,
            ))

        nombre_estacion = db.ESTACIONES_NOMBRE[estacion_idx]
        plural_estacion = ESTACIONES_PLURAL[estacion_idx]
        if not hubo_datos:
            self.label_informe_aviso.config(
                text=f"No hay datos cargados para {nombre_estacion} {anio_periodo}."
            )
        else:
            self.label_informe_aviso.config(
                text=f"{nombre_estacion} {anio_periodo} comparado contra el promedio histórico de "
                f"todos los {plural_estacion} cargados. \"Diferencia\" positiva = por encima de lo normal."
            )


if __name__ == "__main__":
    db.inicializar()
    app = App()
    app.mainloop()
