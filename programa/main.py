"""
Programa de escritorio para cargar observaciones meteorológicas.
Funciona sin internet (guarda local en SQLite) y sincroniza con la misma
Google Sheet que usa la página web cuando hay conexión.
"""
import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

import calculos
import db
import sync

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
DIR_IMAGENES = os.path.join(DIR_ACTUAL, "img")

CAMPOS = [
    ("fecha", "Fecha (AAAA-MM-DD)", True),
    ("hora", "Hora (HH:MM)", True),
    ("t_seca", "T. Seca (°C)", True),
    ("t_humeda", "T. Húmeda (°C)", True),
    ("t_max", "T. Máx (°C) — opcional", False),
    ("t_min", "T. Mín (°C) — opcional", False),
    ("t_adjunto", "T. Adjunto (°C)", True),
    ("barometro", "Barómetro (mmHg)", True),
    ("t_seca_12h_antes", "T. Seca 12hs antes (°C) — opcional", False),
    ("lluvia", "Lluvia (mm) — opcional", False),
]

OBLIGATORIOS = ["t_seca", "t_humeda", "t_adjunto", "barometro"]

FUENTE_FORMULA = ("Consolas", 9)


class MarcoDesplazable(ttk.Frame):
    """Un frame con scroll vertical, para meter adentro contenido más
    largo que la ventana (usado en la pestaña Fórmulas)."""

    def __init__(self, contenedor, *args, **kwargs):
        super().__init__(contenedor, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Observaciones meteorológicas — LPO")
        self.geometry("900x680")
        self.minsize(780, 560)

        self._imagenes = []  # mantiene referencias vivas para que Tkinter no las libere
        self.entradas = {}

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tab_cargar = ttk.Frame(notebook)
        tab_historico = ttk.Frame(notebook)
        tab_formulas = ttk.Frame(notebook)
        notebook.add(tab_cargar, text="Cargar")
        notebook.add(tab_historico, text="Histórico")
        notebook.add(tab_formulas, text="Fórmulas")

        self._armar_formulario(tab_cargar)
        self._armar_resultados(tab_cargar)
        self._armar_historial(tab_historico)
        self._armar_formulas(tab_formulas)
        self._armar_barra_estado()

        self._set_fecha_hora_actual()
        self._recalcular()
        self._refrescar_historial()
        self._sincronizar(automatico=True)

    # ---------- Pestaña: Cargar ----------

    def _armar_formulario(self, contenedor):
        frame = ttk.LabelFrame(contenedor, text="Datos de entrada")
        frame.pack(fill="x", padx=5, pady=(10, 5))

        for i, (clave, etiqueta, _obligatorio) in enumerate(CAMPOS):
            fila, col = divmod(i, 2)
            ttk.Label(frame, text=etiqueta).grid(row=fila, column=col * 2, sticky="w", padx=5, pady=3)
            entrada = ttk.Entry(frame, width=18)
            entrada.grid(row=fila, column=col * 2 + 1, sticky="w", padx=5, pady=3)
            entrada.bind("<KeyRelease>", lambda _e: self._recalcular())
            self.entradas[clave] = entrada

        botones = ttk.Frame(frame)
        botones.grid(row=len(CAMPOS) // 2 + 1, column=0, columnspan=4, pady=(8, 4))
        ttk.Button(botones, text="Guardar observación", command=self._guardar).pack(side="left", padx=5)
        ttk.Button(botones, text="Limpiar", command=self._limpiar).pack(side="left", padx=5)

    def _armar_resultados(self, contenedor):
        frame = ttk.LabelFrame(contenedor, text="Variables calculadas (en vivo)")
        frame.pack(fill="x", padx=5, pady=5)

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
            ttk.Label(frame, text=etiqueta + ":").grid(row=fila, column=col * 2, sticky="w", padx=5, pady=3)
            valor = ttk.Label(frame, text="--", font=("TkDefaultFont", 10, "bold"))
            valor.grid(row=fila, column=col * 2 + 1, sticky="w", padx=5, pady=3)
            self.resultado_labels[clave] = valor

        ttk.Label(
            contenedor,
            text="Cómo se calcula cada variable: pestaña Fórmulas.",
            foreground="#64748b",
        ).pack(anchor="w", padx=8, pady=(0, 5))

    # ---------- Pestaña: Histórico ----------

    def _armar_historial(self, contenedor):
        barra = ttk.Frame(contenedor)
        barra.pack(fill="x", padx=5, pady=(10, 0))
        ttk.Label(barra, text="Últimas observaciones guardadas (locales + de la Sheet)").pack(side="left")
        ttk.Button(barra, text="Actualizar", command=self._refrescar_historial).pack(side="right")

        frame = ttk.Frame(contenedor)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        columnas = (
            "fecha", "hora", "t_seca", "t_humeda", "t_adjunto", "barometro",
            "p_est_hpa", "pnm_hpa", "tension_vapor", "punto_rocio", "humedad_relativa",
            "lluvia", "sync_status",
        )
        titulos = {
            "fecha": "Fecha", "hora": "Hora", "t_seca": "T.Seca", "t_humeda": "T.Húmeda",
            "t_adjunto": "T.Adj.", "barometro": "Barómetro",
            "p_est_hpa": "P.Est (hPa)", "pnm_hpa": "P.N.M (hPa)",
            "tension_vapor": "T.Vapor", "punto_rocio": "P.Rocío", "humedad_relativa": "H.R. (%)",
            "lluvia": "Lluvia", "sync_status": "Estado",
        }
        self.tabla = ttk.Treeview(frame, columns=columnas, show="headings", height=18)
        for col in columnas:
            self.tabla.heading(col, text=titulos[col])
            self.tabla.column(col, width=85, anchor="center")

        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll_y.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

    # ---------- Pestaña: Fórmulas ----------

    def _cargar_imagen(self, nombre_archivo, ancho=320):
        ruta = os.path.join(DIR_IMAGENES, nombre_archivo)
        if not os.path.exists(ruta):
            return None
        img = Image.open(ruta)
        proporcion = ancho / img.width
        img = img.resize((ancho, int(img.height * proporcion)))
        foto = ImageTk.PhotoImage(img)
        self._imagenes.append(foto)  # evita que el garbage collector la borre
        return foto

    def _seccion_formula(self, contenedor, titulo, descripcion, formula, imagen=None, nota=None):
        card = ttk.LabelFrame(contenedor, text=titulo)
        card.pack(fill="x", padx=10, pady=6, ipady=4)
        if descripcion:
            ttk.Label(card, text=descripcion, wraplength=560, justify="left").pack(
                anchor="w", padx=8, pady=(6, 4)
            )
        if formula:
            marco_formula = tk.Frame(card, background="#f8fafc", highlightbackground="#e2e8f0", highlightthickness=1)
            marco_formula.pack(fill="x", padx=8, pady=4)
            tk.Label(
                marco_formula, text=formula, font=FUENTE_FORMULA, justify="left",
                background="#f8fafc", anchor="w",
            ).pack(fill="x", padx=8, pady=6)
        if nota:
            ttk.Label(card, text=nota, wraplength=560, justify="left", foreground="#64748b").pack(
                anchor="w", padx=8, pady=(0, 4)
            )
        if imagen:
            foto = self._cargar_imagen(imagen)
            if foto:
                ttk.Label(card, image=foto).pack(anchor="w", padx=8, pady=(2, 8))

    def _armar_formulas(self, contenedor):
        scroll = MarcoDesplazable(contenedor)
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        raiz = scroll.interior

        ttk.Label(
            raiz,
            text=(
                "Latitud -34.9°, elevación 15 m. Gravedad local g = 9.797207 m/s² vs. "
                "estándar g₀ = 9.80665 m/s². Presión de estación y Tabla D-4 verificadas "
                "contra las tablas oficiales del SMN (fotos abajo de cada sección)."
            ),
            wraplength=560, justify="left",
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self._seccion_formula(
            raiz,
            "1. Presión de estación",
            "Corrige el barómetro de mercurio por dilatación térmica y por gravedad local. "
            "Verificado contra la Tabla D-2 del SMN: coincide al centésimo.",
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

        tablas_ref = ttk.LabelFrame(raiz, text="Tablas SMN de referencia (tensión de vapor / punto de rocío / humedad)")
        tablas_ref.pack(fill="x", padx=10, pady=6, ipady=4)
        ttk.Label(
            tablas_ref,
            text="Se calculan con las fórmulas de arriba, no con lectura de tabla. Quedan de referencia visual.",
            wraplength=560, justify="left",
        ).pack(anchor="w", padx=8, pady=(6, 4))
        galeria = ttk.Frame(tablas_ref)
        galeria.pack(fill="x", padx=8, pady=(0, 8))
        for i, (archivo, etiqueta) in enumerate([
            ("tabla-i.jpg", "Tabla I"),
            ("tabla-ii-bulbo-congelado.jpg", "Tabla II — Bulbo Congelado"),
            ("tabla-iii-bulbo-sin-congelar.jpg", "Tabla III — Bulbo sin Congelar"),
            ("tabla-iv.jpg", "Tabla IV"),
        ]):
            columna = ttk.Frame(galeria)
            columna.grid(row=0, column=i, padx=4)
            foto = self._cargar_imagen(archivo, ancho=150)
            if foto:
                ttk.Label(columna, image=foto).pack()
            ttk.Label(columna, text=etiqueta, wraplength=150, justify="center").pack()

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
            nota="Si falta la T. Seca de 12hs antes, se aproxima con la T. Seca actual.",
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
        frame.pack(fill="x", padx=10, pady=10)
        self.estado_label = ttk.Label(frame, text="Iniciando...")
        self.estado_label.pack(side="left")
        ttk.Button(frame, text="Sincronizar ahora", command=lambda: self._sincronizar(automatico=False)).pack(
            side="right"
        )

    # ---------- Lógica ----------

    def _set_fecha_hora_actual(self):
        ahora = datetime.now()
        self.entradas["fecha"].insert(0, ahora.strftime("%Y-%m-%d"))
        self.entradas["hora"].insert(0, ahora.strftime("%H:%M"))

    def _leer_entrada(self, clave):
        texto = self.entradas[clave].get().strip()
        if not texto:
            return None
        try:
            return float(texto)
        except ValueError:
            return None

    def _leer_formulario(self):
        datos = {"fecha": self.entradas["fecha"].get().strip(), "hora": self.entradas["hora"].get().strip()}
        for clave, _etiqueta, _obligatorio in CAMPOS:
            if clave in ("fecha", "hora"):
                continue
            datos[clave] = self._leer_entrada(clave)
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
                "Faltan datos", "Completá T. Seca, T. Húmeda, T. Adjunto y Barómetro (con números válidos)."
            )
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
            entrada.delete(0, tk.END)
        self._recalcular()

    def _refrescar_historial(self):
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        for fila in db.listar_observaciones():
            self.tabla.insert(
                "",
                tk.END,
                values=(
                    fila["fecha"], fila["hora"], fila["t_seca"], fila["t_humeda"],
                    fila["t_adjunto"], fila["barometro"],
                    f"{fila['p_est_hpa']:.1f}" if fila["p_est_hpa"] is not None else "",
                    f"{fila['pnm_hpa']:.1f}" if fila["pnm_hpa"] is not None else "",
                    f"{fila['tension_vapor']:.1f}" if fila["tension_vapor"] is not None else "",
                    f"{fila['punto_rocio']:.1f}" if fila["punto_rocio"] is not None else "",
                    f"{fila['humedad_relativa']:.0f}" if fila["humedad_relativa"] is not None else "",
                    fila["lluvia"] if fila["lluvia"] is not None else "",
                    "✓ sincronizada" if fila["sync_status"] == "sincronizado" else "pendiente",
                ),
            )
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
