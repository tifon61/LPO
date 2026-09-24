"""
Programa de escritorio para cargar observaciones meteorológicas.
Funciona sin internet (guarda local en SQLite) y sincroniza con la misma
Google Sheet que usa la página web cuando hay conexión.
"""
import os
import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, simpledialog

import ttkbootstrap as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk

import calculos
import db
import sync
from rutas import ruta_recurso

TEMA = "flatly"
COLOR_ACENTO = "#0f766e"  # mismo verde azulado (teal) que usa la página web

CAMPOS = [
    ("fecha", "Fecha (AAAA-MM-DD)", True),
    ("hora", "Hora (sinóptica)", True),
    ("observador", "Observador — opcional", False),
    ("t_seca", "T. Bulbo Seco (°C)", True),
    ("t_humeda", "T. Bulbo Húmedo (°C)", True),
    ("t_max", "T. Máx (°C) — opcional", False),
    ("t_min", "T. Mín (°C) — opcional", False),
    ("t_adjunto", "T. Adjunto (°C)", True),
    ("barometro", "Barómetro (mmHg)", True),
    ("t_seca_12h_antes", "T. Bulbo Seco 12hs antes (°C) — opcional", False),
    ("lluvia", "Lluvia (mm) — opcional", False),
]

OBLIGATORIOS = ["t_seca", "t_humeda", "t_adjunto", "barometro"]

VARIABLES_GRAFICO = [
    ("t_seca", "T. Bulbo Seco (°C)"),
    ("t_humeda", "T. Bulbo Húmedo (°C)"),
    ("punto_rocio", "Punto de Rocío (°C)"),
    ("humedad_relativa", "Humedad Relativa (%)"),
    ("p_est_hpa", "P. Estación (hPa)"),
    ("pnm_hpa", "P. Nivel del Mar (hPa)"),
    ("tension_vapor", "Tensión de Vapor (hPa)"),
    ("lluvia", "Lluvia acumulada (mm)"),
]

FUENTE_FORMULA = ("Consolas", 9)


class MarcoDesplazable(ttk.Frame):
    """Un frame con scroll vertical, para meter adentro contenido más
    largo que la ventana (usado en la pestaña Fórmulas)."""

    def __init__(self, contenedor, color_fondo, *args, **kwargs):
        super().__init__(contenedor, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, background=color_fondo)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.interior = ttk.Frame(canvas)

        self.interior.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.interior, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _rueda(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _rueda)


class App(ttk.Window):
    def __init__(self):
        super().__init__(themename=TEMA)
        self.title("Observaciones meteorológicas — LPO")
        self.geometry("960x760")
        self.minsize(820, 620)
        try:
            self.iconbitmap(ruta_recurso("icono.ico"))
        except tk.TclError:
            pass  # en Linux/Mac iconbitmap no siempre acepta .ico; no es crítico

        self._imagenes = []  # mantiene referencias vivas para que Tkinter no las libere
        self.entradas = {}
        self.color_fondo = self.style.colors.bg

        self._armar_encabezado()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        tab_cargar = ttk.Frame(notebook)
        tab_historico = ttk.Frame(notebook)
        tab_formulas = ttk.Frame(notebook)
        notebook.add(tab_cargar, text="  Cargar  ")
        notebook.add(tab_historico, text="  Histórico  ")
        notebook.add(tab_formulas, text="  Fórmulas  ")

        self._armar_formulario(tab_cargar)
        self._armar_resultados(tab_cargar)
        self._armar_historico(tab_historico)
        self._armar_formulas(tab_formulas)
        self._armar_barra_estado()

        self._set_fecha_hora_actual()
        self._recalcular()
        self._refrescar_historial()
        self._sincronizar(automatico=True)

    # ---------- Encabezado ----------

    def _armar_encabezado(self):
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=12, pady=(12, 0))
        logo = self._cargar_imagen("logo-marca.png", ancho=48)
        if logo:
            ttk.Label(frame, image=logo).pack(side="left", padx=(0, 10))
        titulos = ttk.Frame(frame)
        titulos.pack(side="left")
        ttk.Label(
            titulos, text="Estación Meteorológica — La Plata Observatorio",
            font=("TkDefaultFont", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(titulos, text="FCAG · UNLP", bootstyle="secondary").pack(anchor="w")

    # ---------- Pestaña: Cargar ----------

    def _armar_formulario(self, contenedor):
        frame = ttk.Labelframe(contenedor, text=" Datos de entrada ", padding=12, bootstyle="secondary")
        frame.pack(fill="x", padx=8, pady=(14, 8))

        for i, (clave, etiqueta, _obligatorio) in enumerate(CAMPOS):
            fila, col = divmod(i, 2)
            ttk.Label(frame, text=etiqueta).grid(row=fila, column=col * 2, sticky="w", padx=6, pady=5)
            if clave == "hora":
                entrada = ttk.Combobox(frame, width=16, state="readonly", values=list(calculos.HORAS_VALIDAS))
                entrada.bind("<<ComboboxSelected>>", lambda _e: self._recalcular())
            else:
                entrada = ttk.Entry(frame, width=18)
                entrada.bind("<KeyRelease>", lambda _e: self._recalcular())
            entrada.grid(row=fila, column=col * 2 + 1, sticky="w", padx=6, pady=5)
            self.entradas[clave] = entrada

        botones = ttk.Frame(frame)
        botones.grid(row=len(CAMPOS) // 2 + 1, column=0, columnspan=4, pady=(10, 2))
        ttk.Button(botones, text="Guardar observación", command=self._guardar, bootstyle="success").pack(
            side="left", padx=5
        )
        ttk.Button(botones, text="Limpiar", command=self._limpiar, bootstyle="secondary-outline").pack(
            side="left", padx=5
        )

    def _armar_resultados(self, contenedor):
        frame = ttk.Labelframe(
            contenedor, text=" Variables calculadas (en vivo) ", padding=12, bootstyle="secondary"
        )
        frame.pack(fill="x", padx=8, pady=8)

        self.resultado_labels = {}
        etiquetas = [
            ("p_est_mmhg", "P. Estación (mmHg)"),
            ("p_est_hpa", "P. Estación (hPa)"),
            ("pnm_mmhg", "P. Nivel Mar (mmHg)"),
            ("pnm_hpa", "P. Nivel Mar (hPa)"),
            ("tension_vapor", "Tensión de Vapor (hPa)"),
            ("punto_rocio", "Punto de Rocío (°C)"),
            ("humedad_relativa", "Humedad Relativa (%)"),
        ]
        for i, (clave, etiqueta) in enumerate(etiquetas):
            fila, col = divmod(i, 4)
            ttk.Label(frame, text=etiqueta + ":").grid(row=fila, column=col * 2, sticky="w", padx=6, pady=5)
            valor = ttk.Label(frame, text="--", font=("TkDefaultFont", 11, "bold"), bootstyle="success")
            valor.grid(row=fila, column=col * 2 + 1, sticky="w", padx=6, pady=5)
            self.resultado_labels[clave] = valor

        ttk.Label(
            contenedor,
            text="Cómo se calcula cada variable: pestaña Fórmulas.",
            bootstyle="secondary",
        ).pack(anchor="w", padx=10, pady=(2, 5))

    # ---------- Pestaña: Histórico ----------

    def _armar_historico(self, contenedor):
        barra = ttk.Frame(contenedor)
        barra.pack(fill="x", padx=8, pady=(14, 4))
        ttk.Label(barra, text="Variable del gráfico:").pack(side="left", padx=(0, 6))
        self.variable_grafico = ttk.Combobox(
            barra, state="readonly", width=24,
            values=[etiqueta for _clave, etiqueta in VARIABLES_GRAFICO],
        )
        self.variable_grafico.current(0)
        self.variable_grafico.pack(side="left")
        self.variable_grafico.bind("<<ComboboxSelected>>", lambda _e: self._actualizar_grafico())
        ttk.Button(barra, text="Actualizar", command=self._refrescar_historial, bootstyle="secondary-outline").pack(
            side="right"
        )

        marco_grafico = ttk.Frame(contenedor)
        marco_grafico.pack(fill="x", padx=8, pady=4)
        self.figura = Figure(figsize=(7.5, 2.6), dpi=100)
        self.ejes = self.figura.add_subplot(111)
        self.lienzo_grafico = FigureCanvasTkAgg(self.figura, master=marco_grafico)
        self.lienzo_grafico.get_tk_widget().pack(fill="both", expand=True)

        self.periodo_especifico_actual = "Todos"

        barra_resumen = ttk.Frame(contenedor)
        barra_resumen.pack(fill="x", padx=8, pady=(10, 4))
        ttk.Label(barra_resumen, text="Resumen por período:").pack(side="left", padx=(0, 6))
        self.periodo_resumen = ttk.Combobox(
            barra_resumen, state="readonly", width=14, values=["Diario", "Semanal", "Mensual"]
        )
        self.periodo_resumen.current(0)
        self.periodo_resumen.pack(side="left")
        self.periodo_resumen.bind("<<ComboboxSelected>>", lambda _e: self._cambiar_granularidad())

        ttk.Label(barra_resumen, text="  Ver:").pack(side="left", padx=(12, 6))
        self.periodo_especifico = ttk.Combobox(barra_resumen, state="readonly", width=16, values=["Todos"])
        self.periodo_especifico.current(0)
        self.periodo_especifico.pack(side="left")
        self.periodo_especifico.bind(
            "<<ComboboxSelected>>", lambda _e: self._seleccionar_periodo_especifico(self.periodo_especifico.get())
        )

        ttk.Label(
            contenedor,
            text="Elegí un período puntual (o hacé click en una fila) para que el gráfico y la tabla de "
            "observaciones de abajo muestren solo esos datos.",
            bootstyle="secondary",
        ).pack(anchor="w", padx=8, pady=(0, 6))

        marco_resumen = ttk.Frame(contenedor)
        marco_resumen.pack(fill="x", padx=8, pady=(0, 4))
        columnas_resumen = ("periodo", "t_min", "t_max", "lluvia")
        titulos_resumen = {
            "periodo": "Período", "t_min": "T. Mínima (°C)", "t_max": "T. Máxima (°C)", "lluvia": "Lluvia acumulada (mm)",
        }
        self.tabla_resumen = ttk.Treeview(
            marco_resumen, columns=columnas_resumen, show="headings", height=5, bootstyle="secondary"
        )
        for col in columnas_resumen:
            self.tabla_resumen.heading(col, text=titulos_resumen[col])
            self.tabla_resumen.column(col, width=130, anchor="center")
        self.tabla_resumen.tag_configure("seleccionada", background="#ccfbf1")
        self.tabla_resumen.bind("<<TreeviewSelect>>", self._on_click_fila_resumen)
        scroll_resumen = ttk.Scrollbar(marco_resumen, orient="vertical", command=self.tabla_resumen.yview, bootstyle="round")
        self.tabla_resumen.configure(yscrollcommand=scroll_resumen.set)
        self.tabla_resumen.pack(side="left", fill="x", expand=True)
        scroll_resumen.pack(side="right", fill="y")

        tabla_frame = ttk.Frame(contenedor)
        tabla_frame.pack(fill="both", expand=True, padx=8, pady=(8, 12))

        columnas = (
            "fecha", "hora", "observador", "t_seca", "t_humeda", "t_adjunto", "barometro",
            "p_est_hpa", "pnm_hpa", "tension_vapor", "punto_rocio", "humedad_relativa",
            "lluvia", "sync_status", "descarte",
        )
        titulos = {
            "fecha": "Fecha", "hora": "Hora", "observador": "Observador",
            "t_seca": "T.B.Seco", "t_humeda": "T.B.Húm.",
            "t_adjunto": "T.Adj.", "barometro": "Barómetro",
            "p_est_hpa": "P.Est (hPa)", "pnm_hpa": "P.N.M (hPa)",
            "tension_vapor": "T.Vapor", "punto_rocio": "P.Rocío", "humedad_relativa": "H.R. (%)",
            "lluvia": "Lluvia", "sync_status": "Sync", "descarte": "Descarte",
        }
        self.tabla = ttk.Treeview(tabla_frame, columns=columnas, show="headings", height=10, bootstyle="secondary")
        for col in columnas:
            self.tabla.heading(col, text=titulos[col])
            self.tabla.column(col, width=82, anchor="center")
        self.tabla.column("descarte", width=160)
        self.tabla.tag_configure("descartada", foreground="#94a3b8")
        self.tabla.bind("<Button-3>", self._menu_contextual_tabla)
        self._filas_tabla_por_id = {}

        scroll_y = ttk.Scrollbar(tabla_frame, orient="vertical", command=self.tabla.yview, bootstyle="round")
        self.tabla.configure(yscrollcommand=scroll_y.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        ttk.Label(
            contenedor,
            text="Click derecho sobre una fila para descartarla (o reactivarla) sin borrar el dato original.",
            bootstyle="secondary",
        ).pack(anchor="w", padx=8, pady=(0, 10))

    def _filtrar_por_periodo(self, datos):
        if self.periodo_especifico_actual == "Todos":
            return datos
        periodo = self.periodo_resumen.get()
        return [
            f for f in datos
            if f.get("fecha") and self._clave_periodo(f["fecha"], periodo) == self.periodo_especifico_actual
        ]

    def _actualizar_grafico(self):
        clave, etiqueta = VARIABLES_GRAFICO[self.variable_grafico.current()]
        datos = self._filtrar_por_periodo(db.listar_para_grafico())

        self.ejes.clear()
        puntos = []
        acumulado_lluvia = 0
        hay_algun_valor = False
        for f in datos:
            if f.get("descartada"):
                continue
            valor = f.get(clave)
            if clave == "lluvia":
                # La lluvia se carga como mm caídos desde la última lectura, no
                # como total del instrumento, así que el acumulado se arma
                # sumando cada observación de la serie. Nunca se muestran
                # negativos.
                valor = max(0, valor) if valor is not None else 0
                acumulado_lluvia += valor
                valor = acumulado_lluvia
                hay_algun_valor = True
            elif valor is None:
                # No se deja afuera del gráfico: se deja como hueco (NaN), así
                # la línea se corta ahí en vez de "pegar" el punto anterior
                # con el siguiente como si fueran continuos.
                valor = float("nan")
            else:
                hay_algun_valor = True
            puntos.append((f"{f['fecha']} {f['hora']}", valor))
        if puntos and hay_algun_valor:
            etiquetas_x = [p[0] for p in puntos]
            valores_y = [p[1] for p in puntos]

            # Franjas de fondo alternadas por día, para distinguir a simple
            # vista dónde termina un día y empieza el siguiente.
            alphas_dia = [0.04, 0.1]
            dia_actual = None
            inicio_idx = 0
            color_idx = -1
            for i, etiqueta in enumerate(etiquetas_x + [None]):
                dia = etiqueta[:10] if etiqueta is not None else None
                if dia != dia_actual:
                    if dia_actual is not None:
                        color_idx += 1
                        self.ejes.axvspan(
                            inicio_idx - 0.5, i - 0.5,
                            facecolor=COLOR_ACENTO, alpha=alphas_dia[color_idx % 2], zorder=0,
                        )
                    dia_actual = dia
                    inicio_idx = i

            if clave == "lluvia":
                self.ejes.step(etiquetas_x, valores_y, where="post", color=COLOR_ACENTO, linewidth=1.5)
                self.ejes.fill_between(etiquetas_x, valores_y, step="post", color=COLOR_ACENTO, alpha=0.15)
                self.ejes.set_ylim(bottom=0)
            else:
                self.ejes.plot(etiquetas_x, valores_y, marker="o", markersize=3, color=COLOR_ACENTO, linewidth=1.5)
            # No saturar el eje X de etiquetas si hay muchas observaciones.
            paso = max(1, len(etiquetas_x) // 10)
            self.ejes.set_xticks(etiquetas_x[::paso])
            self.figura.autofmt_xdate(rotation=30, ha="right")
        else:
            self.ejes.text(0.5, 0.5, "Sin datos todavía", ha="center", va="center", color="#94a3b8")
            self.ejes.set_xticks([])
        self.ejes.set_title(etiqueta, fontsize=10, color="#334155")
        self.ejes.tick_params(labelsize=7)
        self.ejes.grid(True, alpha=0.25)
        self.figura.tight_layout()
        self.lienzo_grafico.draw()

    def _clave_periodo(self, fecha_iso, periodo):
        anio, mes, dia = (int(p) for p in fecha_iso.split("-"))
        fecha = date(anio, mes, dia)
        if periodo == "Mensual":
            return fecha_iso[:7]
        if periodo == "Semanal":
            iso_anio, iso_semana, _ = fecha.isocalendar()
            return f"{iso_anio}-S{iso_semana:02d}"
        return fecha_iso  # Diario

    def _calcular_resumen(self, datos, periodo):
        grupos = {}
        for f in datos:
            if not f.get("fecha") or f.get("descartada"):
                continue
            clave = self._clave_periodo(f["fecha"], periodo)
            g = grupos.setdefault(clave, {"minimos": [], "maximos": [], "lluvia": 0, "tiene_lluvia": False, "primera_fecha": f["fecha"]})
            if isinstance(f.get("t_seca"), (int, float)):
                g["minimos"].append(f["t_seca"])
                g["maximos"].append(f["t_seca"])
            if isinstance(f.get("t_min"), (int, float)):
                g["minimos"].append(f["t_min"])
            if isinstance(f.get("t_max"), (int, float)):
                g["maximos"].append(f["t_max"])
            if isinstance(f.get("lluvia"), (int, float)):
                g["lluvia"] += f["lluvia"]
                g["tiene_lluvia"] = True
            if f["fecha"] < g["primera_fecha"]:
                g["primera_fecha"] = f["fecha"]

        filas = []
        for clave, g in grupos.items():
            filas.append({
                "periodo": clave,
                "t_min": min(g["minimos"]) if g["minimos"] else None,
                "t_max": max(g["maximos"]) if g["maximos"] else None,
                "lluvia": g["lluvia"] if g["tiene_lluvia"] else None,
                "orden": g["primera_fecha"],
            })
        filas.sort(key=lambda f: f["orden"], reverse=True)
        return filas

    def _actualizar_resumen(self):
        periodo = self.periodo_resumen.get()
        datos = db.listar_para_grafico()
        resumen = self._calcular_resumen(datos, periodo)

        valores_disponibles = ["Todos"] + [fila["periodo"] for fila in resumen]
        if self.periodo_especifico_actual not in valores_disponibles:
            self.periodo_especifico_actual = "Todos"
        self.periodo_especifico.configure(values=valores_disponibles)
        self.periodo_especifico.set(self.periodo_especifico_actual)

        for item in self.tabla_resumen.get_children():
            self.tabla_resumen.delete(item)
        for fila in resumen:
            tags = ("seleccionada",) if fila["periodo"] == self.periodo_especifico_actual else ()
            self.tabla_resumen.insert(
                "", tk.END,
                values=(
                    fila["periodo"],
                    f"{fila['t_min']:.1f}" if fila["t_min"] is not None else "",
                    f"{fila['t_max']:.1f}" if fila["t_max"] is not None else "",
                    f"{fila['lluvia']:.1f}" if fila["lluvia"] is not None else "",
                ),
                tags=tags,
            )

    def _cambiar_granularidad(self):
        self.periodo_especifico_actual = "Todos"
        self._actualizar_resumen()
        self._actualizar_grafico()
        self._refrescar_tabla_observaciones()

    def _seleccionar_periodo_especifico(self, valor):
        self.periodo_especifico_actual = valor
        self._actualizar_resumen()
        self._actualizar_grafico()
        self._refrescar_tabla_observaciones()

    def _on_click_fila_resumen(self, _evento):
        seleccion = self.tabla_resumen.selection()
        if not seleccion:
            return
        valores = self.tabla_resumen.item(seleccion[0], "values")
        self._seleccionar_periodo_especifico(valores[0])

    # ---------- Pestaña: Fórmulas ----------

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

    def _seccion_formula(self, contenedor, titulo, descripcion, formula, imagen=None, nota=None):
        card = ttk.Labelframe(contenedor, text=f" {titulo} ", padding=10, bootstyle="secondary")
        card.pack(fill="x", padx=12, pady=7)
        if descripcion:
            ttk.Label(card, text=descripcion, wraplength=580, justify="left").pack(anchor="w", pady=(0, 6))
        if formula:
            marco_formula = tk.Frame(card, background="#f1f5f9", highlightbackground="#e2e8f0", highlightthickness=1)
            marco_formula.pack(fill="x", pady=4)
            tk.Label(
                marco_formula, text=formula, font=FUENTE_FORMULA, justify="left",
                background="#f1f5f9", foreground="#0f172a", anchor="w",
            ).pack(fill="x", padx=10, pady=8)
        if nota:
            ttk.Label(card, text=nota, wraplength=580, justify="left", bootstyle="secondary").pack(
                anchor="w", pady=(6, 0)
            )
        if imagen:
            foto = self._cargar_imagen(imagen)
            if foto:
                ttk.Label(card, image=foto).pack(anchor="w", pady=(6, 0))

    def _armar_formulas(self, contenedor):
        scroll = MarcoDesplazable(contenedor, color_fondo=self.color_fondo)
        scroll.pack(fill="both", expand=True, padx=8, pady=8)
        raiz = scroll.interior

        guia = ttk.Labelframe(raiz, text=" Guía rápida para observadores ", padding=10, bootstyle="success")
        guia.pack(fill="x", padx=12, pady=(14, 7))
        ttk.Label(
            guia,
            text=(
                "Podés cargar una observación acá o desde la página web — las dos guardan en la "
                "misma planilla. Usá este programa cuando no tengas internet en el momento: guarda "
                "local y sincroniza solo apenas vuelve la conexión (mirá el cartel abajo de la ventana). "
                "Si al guardar te aparece un error de \"fuera de rango\", revisá si hay un error de "
                "tipeo antes de insistir."
            ),
            wraplength=580, justify="left",
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            guia,
            text="Datos obligatorios: Hora, T. Bulbo Seco, T. Bulbo Húmedo, T. Adjunto, Barómetro. El resto es opcional.",
            wraplength=580, justify="left", bootstyle="secondary",
        ).pack(anchor="w")
        ttk.Label(
            guia,
            text="La estación toma observaciones a las 09:00, 15:00 y 21:00 (hora local) — las tres horas "
            "sinópticas (12, 18 y 00 UTC).",
            wraplength=580, justify="left", bootstyle="secondary",
        ).pack(anchor="w", pady=(4, 0))

        ttk.Label(
            raiz,
            text=(
                "Esta estación está en latitud -34.9°, a 15 m sobre el nivel del mar. La gravedad local "
                "(g = 9.797207 m/s²) es un poco menor a la gravedad estándar (g₀ = 9.80665 m/s²), y esa "
                "diferencia es justamente una de las correcciones que se le aplica al barómetro."
            ),
            wraplength=580, justify="left", bootstyle="secondary",
        ).pack(anchor="w", padx=18, pady=(14, 6))

        self._seccion_formula(
            raiz,
            "1. Presión de estación",
            "Corrige la lectura del barómetro de mercurio por su dilatación térmica y por la gravedad "
            "local — la misma corrección que da la Tabla D-2 del SMN, buscándola a mano.",
            "C_t = -B × 0.000163 × T_adj\n"
            "B0 = B + C_t\n"
            "P_estación (mmHg) = B0 × (g_local / g_estándar)",
        )

        self._seccion_formula(
            raiz,
            "2. Tensión de vapor",
            "Fórmula psicrométrica (Magnus-Tetens + corrección de garita sin ventilación forzada).",
            "es_húmeda = 6.112 × exp((17.67 × T_h) / (T_h + 243.5))\n"
            "e (hPa) = es_húmeda − 0.0008 × P_estación(hPa) × (T_s − T_h)",
        )

        self._seccion_formula(
            raiz,
            "3. Punto de rocío",
            None,
            "T_d = (ln(e / 6.112) × 243.5) / (17.67 − ln(e / 6.112))",
        )

        self._seccion_formula(
            raiz,
            "4. Humedad relativa",
            None,
            "es_seca = 6.112 × exp((17.67 × T_s) / (T_s + 243.5))\n"
            "HR (%) = (e / es_seca) × 100",
        )

        tablas_ref = ttk.Labelframe(
            raiz,
            text=" Tablas SMN de referencia (tensión de vapor / punto de rocío / humedad) ",
            padding=10, bootstyle="secondary",
        )
        tablas_ref.pack(fill="x", padx=12, pady=7)
        ttk.Label(
            tablas_ref,
            text="La tensión de vapor, el punto de rocío y la humedad relativa se obtienen con las fórmulas "
            "de arriba en vez de buscarlos en estas tablas. Quedan las fotos por si querés consultarlas.",
            wraplength=580, justify="left",
        ).pack(anchor="w", pady=(0, 6))
        galeria = ttk.Frame(tablas_ref)
        galeria.pack(fill="x")
        for i, (archivo, etiqueta) in enumerate([
            ("tabla-i.jpg", "Tabla I"),
            ("tabla-ii-bulbo-congelado.jpg", "Tabla II — Bulbo Congelado"),
            ("tabla-iii-bulbo-sin-congelar.jpg", "Tabla III — Bulbo sin Congelar"),
            ("tabla-iv.jpg", "Tabla IV"),
        ]):
            columna = ttk.Frame(galeria)
            columna.grid(row=0, column=i, padx=5)
            foto = self._cargar_imagen(archivo, ancho=150)
            if foto:
                ttk.Label(columna, image=foto).pack()
            ttk.Label(columna, text=etiqueta, wraplength=150, justify="center", bootstyle="secondary").pack()

        tabla_d4_txt = "\n".join(
            f"{t_min:>6.1f} a {t_max:>5.1f} °C   →  {c730:.1f} mmHg (730-759,99)  /  {c760:.1f} mmHg (760-789,99)"
            for t_min, t_max, c730, c760 in calculos.TABLA_D4
        )
        self._seccion_formula(
            raiz,
            "5. Presión a nivel del mar — Tabla D-4 del SMN (Estación La Plata)",
            "A diferencia de las demás, esta variable usa la tabla oficial que ya usan los "
            "observadores en papel (específica de esta estación), no una fórmula continua.",
            "T_prom = (T_seca actual + T_seca 12hs antes) / 2\n"
            "corrección = TABLA_D4[fila T_prom][columna P_estación]\n"
            "P_mar (mmHg) = P_estación + corrección\n\n" + tabla_d4_txt,
            imagen="tabla-d4.jpg",
            nota="Si falta la T. Bulbo Seco de 12hs antes, se aproxima con la T. Bulbo Seco actual.",
        )

        self._seccion_formula(
            raiz, "6. Conversión mmHg ↔ hPa", None, "P (hPa) = P (mmHg) × 4/3",
        )

        self._seccion_formula(
            raiz,
            "Procedimiento en papel (notas del observador)",
            "El procedimiento manual completo en el que se basa este programa.",
            None,
            imagen="procedimiento-manuscrito.jpg",
        )

    # ---------- Barra de estado ----------

    def _armar_barra_estado(self):
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=12, pady=12)
        self.estado_label = ttk.Label(frame, text="Iniciando...", bootstyle="secondary")
        self.estado_label.pack(side="left")
        ttk.Button(
            frame, text="Sincronizar ahora", command=lambda: self._sincronizar(automatico=False),
            bootstyle="info",
        ).pack(side="right")

    # ---------- Lógica ----------

    def _hora_sinoptica_mas_cercana(self, momento):
        minutos_actuales = momento.hour * 60 + momento.minute
        mejor, mejor_diferencia = calculos.HORAS_VALIDAS[0], None
        for hora in calculos.HORAS_VALIDAS:
            h, m = (int(p) for p in hora.split(":"))
            minutos_hora = h * 60 + m
            diferencia = min(
                abs(minutos_actuales - minutos_hora), 1440 - abs(minutos_actuales - minutos_hora)
            )
            if mejor_diferencia is None or diferencia < mejor_diferencia:
                mejor, mejor_diferencia = hora, diferencia
        return mejor

    def _set_fecha_hora_actual(self):
        ahora = datetime.now()
        self.entradas["fecha"].insert(0, ahora.strftime("%Y-%m-%d"))
        self.entradas["hora"].set(self._hora_sinoptica_mas_cercana(ahora))

    def _leer_entrada(self, clave):
        texto = self.entradas[clave].get().strip()
        if not texto:
            return None
        try:
            return float(texto)
        except ValueError:
            return None

    def _leer_formulario(self):
        datos = {
            "fecha": self.entradas["fecha"].get().strip(),
            "hora": self.entradas["hora"].get().strip(),
            "observador": self.entradas["observador"].get().strip(),
        }
        for clave, _etiqueta, _obligatorio in CAMPOS:
            if clave in ("fecha", "hora", "observador"):
                continue
            datos[clave] = self._leer_entrada(clave)
        # Si no se cargó lluvia, se asume que no llovió (0), no que falta el dato.
        if datos.get("lluvia") is None:
            datos["lluvia"] = 0.0
        return datos

    def _recalcular(self):
        datos = self._leer_formulario()
        faltan_obligatorios = any(datos.get(c) is None for c in OBLIGATORIOS)
        if faltan_obligatorios:
            for label in self.resultado_labels.values():
                label.config(text="--")
            return None

        entrada_calculo = {
            "t_seca": datos["t_seca"], "t_humeda": datos["t_humeda"],
            "t_adjunto": datos["t_adjunto"], "barometro": datos["barometro"],
            "t_seca_12h_antes": datos.get("t_seca_12h_antes"),
        }
        resultado = calculos.calcular_observacion(entrada_calculo)
        self.resultado_labels["p_est_mmhg"].config(text=f"{resultado['p_est_mmhg']:.1f}")
        self.resultado_labels["p_est_hpa"].config(text=f"{resultado['p_est_hpa']:.1f}")
        self.resultado_labels["pnm_mmhg"].config(text=f"{resultado['pnm_mmhg']:.1f}")
        self.resultado_labels["pnm_hpa"].config(text=f"{resultado['pnm_hpa']:.1f}")
        self.resultado_labels["tension_vapor"].config(text=f"{resultado['tension_vapor']:.1f}")
        self.resultado_labels["punto_rocio"].config(text=f"{resultado['punto_rocio']:.1f}")
        self.resultado_labels["humedad_relativa"].config(text=f"{resultado['humedad_relativa']:.0f}")
        return resultado

    def _guardar(self):
        datos = self._leer_formulario()
        if not datos["fecha"] or not datos["hora"]:
            messagebox.showerror("Faltan datos", "Completá fecha y hora.")
            return
        resultado = self._recalcular()
        if resultado is None:
            messagebox.showerror(
                "Faltan datos", "Completá T. Bulbo Seco, T. Bulbo Húmedo, T. Adjunto y Barómetro (con números válidos)."
            )
            return

        errores = calculos.validar_observacion(datos)
        if errores:
            messagebox.showerror("Revisá los datos", "\n".join(errores))
            return

        if db.existe(datos["fecha"], datos["hora"]):
            if not messagebox.askyesno(
                "Ya existe", "Ya hay una observación con esa fecha y hora. ¿Guardar igual? (se ignorará si es duplicada)"
            ):
                return

        fila = {**datos, **resultado}
        insertada = db.insertar_observacion(fila, origen="local", sync_status="pendiente")
        if not insertada:
            messagebox.showwarning("Sin cambios", "Ya existía una observación con esa fecha y hora exactas.")
            return

        self._refrescar_historial()
        self._limpiar()
        self._set_fecha_hora_actual()
        self.estado_label.config(text="Observación guardada localmente. Sincronizando...")
        self._sincronizar(automatico=True)

    def _limpiar(self):
        for clave, entrada in self.entradas.items():
            if clave == "hora":
                continue  # combobox de solo lectura: siempre tiene que quedar una hora válida elegida
            entrada.delete(0, tk.END)
        self._recalcular()

    def _refrescar_tabla_observaciones(self):
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        datos = self._filtrar_por_periodo(db.listar_observaciones())
        self._filas_tabla_por_id = {}
        for fila in datos:
            self._filas_tabla_por_id[fila["id"]] = fila
            descartada = bool(fila.get("descartada"))
            self.tabla.insert(
                "",
                tk.END,
                iid=str(fila["id"]),
                values=(
                    fila["fecha"], fila["hora"], fila.get("observador") or "",
                    fila["t_seca"], fila["t_humeda"],
                    fila["t_adjunto"], fila["barometro"],
                    f"{fila['p_est_hpa']:.1f}" if fila["p_est_hpa"] is not None else "",
                    f"{fila['pnm_hpa']:.1f}" if fila["pnm_hpa"] is not None else "",
                    f"{fila['tension_vapor']:.1f}" if fila["tension_vapor"] is not None else "",
                    f"{fila['punto_rocio']:.1f}" if fila["punto_rocio"] is not None else "",
                    f"{fila['humedad_relativa']:.0f}" if fila["humedad_relativa"] is not None else "",
                    fila["lluvia"] if fila["lluvia"] is not None else "",
                    "✓ sincronizada" if fila["sync_status"] == "sincronizado" else "pendiente",
                    f"Descartada: {fila.get('motivo_descarte') or ''}" if descartada else "",
                ),
                tags=("descartada",) if descartada else (),
            )

    def _menu_contextual_tabla(self, evento):
        iid = self.tabla.identify_row(evento.y)
        if not iid:
            return
        self.tabla.selection_set(iid)
        fila = self._filas_tabla_por_id.get(int(iid))
        if not fila:
            return
        menu = tk.Menu(self, tearoff=0)
        if fila.get("descartada"):
            menu.add_command(label="Reactivar observación", command=lambda: self._alternar_descarte(fila, False))
        else:
            menu.add_command(label="Descartar observación...", command=lambda: self._alternar_descarte(fila, True))
        menu.tk_popup(evento.x_root, evento.y_root)

    def _alternar_descarte(self, fila, descartar):
        motivo, descartado_por = "", ""
        if descartar:
            motivo = simpledialog.askstring(
                "Descartar observación", "¿Por qué se descarta esta observación?", parent=self
            )
            if not motivo:
                return
            descartado_por = simpledialog.askstring(
                "Descartar observación", "¿Quién la descarta? (opcional)", parent=self
            ) or ""
        elif not messagebox.askyesno("Reactivar", "¿Reactivar esta observación?"):
            return

        db.marcar_descarte(fila["id"], descartar, motivo=motivo, descartado_por=descartado_por)
        self._refrescar_historial()
        self.estado_label.config(text="Descarte guardado localmente. Sincronizando...")
        self._sincronizar(automatico=True)

    def _refrescar_historial(self):
        # El resumen va primero: si el período específico elegido ya no
        # existe (por ejemplo, se sincronizó y cambió el conjunto de datos),
        # ahí se resetea a "Todos" antes de filtrar la tabla y el gráfico.
        self._actualizar_resumen()
        self._refrescar_tabla_observaciones()
        self._actualizar_grafico()
        pendientes = db.contar_pendientes()
        if pendientes:
            self.estado_label.config(text=f"{pendientes} observación(es) pendiente(s) de sincronizar.")
        else:
            self.estado_label.config(text="Todo sincronizado.")

    def _sincronizar(self, automatico):
        def tarea():
            try:
                subidas, bajadas = sync.sincronizar_todo()
                mensaje = f"Sincronizado: {subidas} subida(s), {bajadas} bajada(s) nueva(s)."
                self.after(0, lambda: self._al_terminar_sync(mensaje))
            except Exception as e:
                prefijo = "" if automatico else "Error al sincronizar: "
                mensaje = f"{prefijo}{e}" if not automatico else f"Sin conexión o error al sincronizar ({e}). Los datos quedan guardados localmente."
                self.after(0, lambda: self._al_terminar_sync(mensaje, error=not automatico))

        threading.Thread(target=tarea, daemon=True).start()

    def _al_terminar_sync(self, mensaje, error=False):
        self._refrescar_historial()
        self.estado_label.config(text=mensaje)
        if error:
            messagebox.showerror("Sincronización", mensaje)


if __name__ == "__main__":
    db.inicializar()
    app = App()
    app.mainloop()
