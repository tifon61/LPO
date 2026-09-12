"""
Programa de escritorio para cargar observaciones meteorológicas.
Funciona sin internet (guarda local en SQLite) y sincroniza con la misma
Google Sheet que usa la página web cuando hay conexión.
"""
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

import calculos
import db
import sync

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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Observaciones meteorológicas — LPO")
        self.geometry("880x640")
        self.minsize(760, 560)

        self.entradas = {}
        self._armar_formulario()
        self._armar_resultados()
        self._armar_historial()
        self._armar_barra_estado()

        self._set_fecha_hora_actual()
        self._recalcular()
        self._refrescar_historial()
        self._sincronizar(automatico=True)

    # ---------- UI ----------

    def _armar_formulario(self):
        frame = ttk.LabelFrame(self, text="Datos de entrada")
        frame.pack(fill="x", padx=10, pady=(10, 5))

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

    def _armar_resultados(self):
        frame = ttk.LabelFrame(self, text="Variables calculadas (en vivo)")
        frame.pack(fill="x", padx=10, pady=5)

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

    def _armar_historial(self):
        frame = ttk.LabelFrame(self, text="Últimas observaciones")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        columnas = ("fecha", "hora", "t_seca", "t_humeda", "pnm_hpa", "humedad_relativa", "sync_status")
        self.tabla = ttk.Treeview(frame, columns=columnas, show="headings", height=10)
        titulos = {
            "fecha": "Fecha", "hora": "Hora", "t_seca": "T.Seca", "t_humeda": "T.Húmeda",
            "pnm_hpa": "P.N.M (hPa)", "humedad_relativa": "H.R. (%)", "sync_status": "Estado",
        }
        for col in columnas:
            self.tabla.heading(col, text=titulos[col])
            self.tabla.column(col, width=100, anchor="center")
        self.tabla.pack(fill="both", expand=True, padx=5, pady=5)

    def _armar_barra_estado(self):
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=(0, 10))
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
                    fila["fecha"], fila["hora"],
                    fila["t_seca"], fila["t_humeda"],
                    f"{fila['pnm_hpa']:.1f}" if fila["pnm_hpa"] is not None else "",
                    f"{fila['humedad_relativa']:.0f}" if fila["humedad_relativa"] is not None else "",
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
