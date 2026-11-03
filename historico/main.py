"""
Archivo Histórico de Observaciones — visor standalone.

Importa los Excel anuales (uno por año, mismo formato desde hace décadas)
a una base SQLite local, y permite elegir una variable + un período para
graficarlo, verlo en tabla, y exportarlo a CSV.
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

import config
import db
import importador

COLOR_ACENTO = "#1e3a8a"

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


class App(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title("Archivo Histórico — Estación La Plata Observatorio")
        self.geometry("1100x820")
        self._datos_periodo_actual = []

        self._armar_encabezado()
        self._armar_importar()
        self._armar_visor()
        self._actualizar_rango_disponible()

    # ---------- Encabezado ----------

    def _armar_encabezado(self):
        ttk.Label(
            self, text="Archivo Histórico de Observaciones", font=("Georgia", 16, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 0))
        self.label_rango = ttk.Label(self, text="", bootstyle="secondary")
        self.label_rango.pack(anchor="w", padx=12, pady=(0, 8))

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
        # último mes disponible — así alcanza con tocar "Graficar" una vez
        # para ver algo, en vez de tener que saber de entrada qué rango pedir.
        if not self.entrada_desde.get().strip() and not self.entrada_hasta.get().strip():
            hasta = datetime.strptime(fecha_max, "%Y-%m-%d").date()
            desde = hasta - timedelta(days=30)
            self.entrada_desde.insert(0, desde.strftime("%d/%m/%Y"))
            self.entrada_hasta.insert(0, hasta.strftime("%d/%m/%Y"))

    # ---------- Visor ----------

    def _armar_visor(self):
        marco = ttk.Labelframe(self, text=" Ver / graficar un período ", padding=10)
        marco.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        barra = ttk.Frame(marco)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Variable:").pack(side="left", padx=(0, 6))
        self.combo_variable = ttk.Combobox(
            barra, state="readonly", width=24, values=[etiqueta for _c, etiqueta in VARIABLES_GRAFICO],
        )
        self.combo_variable.current(0)
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
        clave, etiqueta = VARIABLES_GRAFICO[self.combo_variable.current()]
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


if __name__ == "__main__":
    db.inicializar()
    app = App()
    app.mainloop()
