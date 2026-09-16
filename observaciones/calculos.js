/**
 * Motor de cálculo de variables meteorológicas derivadas (tipo SYNOP).
 * Presión de estación, tensión de vapor, punto de rocío y humedad relativa:
 * port directo del script Python/Tkinter original (fórmulas Magnus-Tetens).
 * Presión a nivel del mar: tabla oficial D-4 del SMN, específica de esta
 * estación (ver TABLA_D4 más abajo) — reemplaza la fórmula hipsométrica
 * genérica que usaba el script Python, para coincidir con el procedimiento
 * en papel que siguen los observadores.
 *
 * Se usa tanto acá (preview en el navegador) como en apps-script/Code.gs
 * (cálculo autoritativo antes de guardar en la Sheet) — si cambiás algo acá,
 * replicá el cambio en los dos lugares.
 */

const ESTACION = {
  latitud: -34.9,
  elevacion: 15, // metros
  // Gravedad local (fórmula internacional de gravedad para latitud -34.9°) vs. estándar.
  gravedadLocal: 9.797207,
  gravedadEstandar: 9.80665,
};

function presionEstacionMmhg(barometro, tAdjunto) {
  // Corrección térmica (dilatación del mercurio y escala de latón)
  const cT = -barometro * 0.000163 * tAdjunto;
  const b0 = barometro + cT;
  // Corrección por gravedad local
  return b0 * (ESTACION.gravedadLocal / ESTACION.gravedadEstandar);
}

function mmhgAHpa(mmhg) {
  return mmhg * (4.0 / 3.0);
}

function tensionVaporHpa(tSeca, tHumeda, pEstacionHpa) {
  const esHumeda = 6.112 * Math.exp((17.67 * tHumeda) / (tHumeda + 243.5));
  // Constante ajustada para garita meteorológica estándar (sin ventilación forzada)
  const A = 0.0008;
  const e = esHumeda - A * pEstacionHpa * (tSeca - tHumeda);
  return Math.max(0, e);
}

function puntoRocio(eHpa) {
  if (eHpa <= 0) return 0.0;
  const numerador = Math.log(eHpa / 6.112) * 243.5;
  const denominador = 17.67 - Math.log(eHpa / 6.112);
  return numerador / denominador;
}

function humedadRelativa(eHpa, tSeca) {
  const esSeca = 6.112 * Math.exp((17.67 * tSeca) / (tSeca + 243.5));
  const hr = (eHpa / esSeca) * 100;
  return Math.max(0, Math.min(hr, 100));
}

/**
 * Tabla D-4 del SMN (Oficina de Cálculos Generales), específica de esta
 * estación (La Plata — latitud 34°55', altura 14.97 m): valores a SUMAR a
 * la presión de estación (ya corregida por Tabla D-2) para obtener la
 * presión a nivel del mar. Reemplaza la fórmula hipsométrica genérica por
 * la tabla oficial que usan los observadores en papel.
 */
const TABLA_D4 = [
  // tMin, tMax: rango de la temperatura PROMEDIO del termómetro seco (°C).
  // c730: columna "730.00 a 759.99 mmHg" · c760: columna "760.00 a 789.99 mmHg"
  { tMin: -10.0, tMax: -0.1, c730: 1.4, c760: 1.5 },
  { tMin: 0.0, tMax: 9.9, c730: 1.4, c760: 1.4 },
  { tMin: 10.0, tMax: 19.9, c730: 1.3, c760: 1.4 },
  { tMin: 20.0, tMax: 29.9, c730: 1.3, c760: 1.3 },
  { tMin: 30.0, tMax: 39.9, c730: 1.2, c760: 1.3 },
  { tMin: 40.0, tMax: 49.9, c730: 1.2, c760: 1.2 },
];

function correccionD4(tPromedio, pEstMmhg) {
  let fila = TABLA_D4.find((f) => tPromedio >= f.tMin && tPromedio <= f.tMax);
  if (!fila) {
    fila = tPromedio < TABLA_D4[0].tMin ? TABLA_D4[0] : TABLA_D4[TABLA_D4.length - 1];
  }
  return pEstMmhg < 760.0 ? fila.c730 : fila.c760;
}

/**
 * Rangos físicamente razonables para esta estación (La Plata). No son los
 * extremos absolutos posibles — son un colchón generoso pensado para
 * atajar errores de tipeo (ej. "225" en vez de "22.5"), no para rechazar
 * lecturas reales raras.
 */
const RANGOS = {
  tSeca: { min: -15, max: 45, etiqueta: "T. Bulbo Seco" },
  tHumeda: { min: -15, max: 45, etiqueta: "T. Bulbo Húmedo" },
  tMax: { min: -15, max: 45, etiqueta: "T. Máx" },
  tMin: { min: -15, max: 45, etiqueta: "T. Mín" },
  tAdjunto: { min: -15, max: 45, etiqueta: "T. Adjunto" },
  tSeca12hAntes: { min: -15, max: 45, etiqueta: "T. Bulbo Seco 12hs antes" },
  barometro: { min: 700, max: 800, etiqueta: "Barómetro" },
  lluvia: { min: 0, max: 500, etiqueta: "Lluvia" },
};

/** Esta estación solo toma observaciones a las tres horas sinópticas
 * (12, 18 y 00 UTC), en hora local de Argentina (UTC-3). */
const HORAS_VALIDAS = ["09:00", "15:00", "21:00"];

/**
 * Valida una observación antes de calcular/guardar. input: mismas claves
 * que RANGOS (los campos opcionales pueden venir null/undefined/"" — se
 * saltean). Devuelve un array de mensajes de error (vacío si está todo bien).
 */
function validarObservacion(input) {
  const errores = [];
  for (const campo in RANGOS) {
    const valor = input[campo];
    if (valor === null || valor === undefined || valor === "") continue;
    if (typeof valor !== "number" || Number.isNaN(valor)) {
      errores.push(`${RANGOS[campo].etiqueta}: no es un número válido.`);
      continue;
    }
    const { min, max, etiqueta } = RANGOS[campo];
    if (valor < min || valor > max) {
      errores.push(`${etiqueta} fuera de rango razonable (entre ${min} y ${max}). Revisá si hay un error de tipeo.`);
    }
  }

  const tSeca = input.tSeca;
  const tHumeda = input.tHumeda;
  if (typeof tSeca === "number" && typeof tHumeda === "number" && tHumeda > tSeca + 0.05) {
    errores.push("La T. Bulbo Húmedo no puede ser mayor que la T. Bulbo Seco.");
  }
  if (typeof tSeca === "number" && typeof input.tMax === "number" && input.tMax < tSeca - 0.05) {
    errores.push("La T. Máx no puede ser menor que la T. Bulbo Seco actual.");
  }
  if (typeof tSeca === "number" && typeof input.tMin === "number" && input.tMin > tSeca + 0.05) {
    errores.push("La T. Mín no puede ser mayor que la T. Bulbo Seco actual.");
  }
  if (input.hora && !HORAS_VALIDAS.includes(input.hora)) {
    errores.push(`La hora debe ser una de las tres observaciones sinópticas: ${HORAS_VALIDAS.join(", ")}.`);
  }

  return errores;
}

/**
 * input: { tSeca, tHumeda, tMax, tMin, tAdjunto, barometro, lluvia, tSeca12hAntes }
 * (números; opcionales pueden ser null). tSeca12hAntes es la T. Seca de la
 * observación de 12hs antes, para promediarla con la actual (Tabla D-4);
 * si no se manda, se usa la T. Seca actual como aproximación.
 * Devuelve todas las variables derivadas.
 */
// Redondea a 1 decimal — evita guardar el resultado crudo de la cuenta en
// punto flotante (con 8-10 decimales de ruido) en la Sheet/base local.
function redondear1_(n) {
  return Math.round(n * 10) / 10;
}

function calcularObservacion(input) {
  const pEstMmhg = presionEstacionMmhg(input.barometro, input.tAdjunto);
  const pEstHpa = mmhgAHpa(pEstMmhg);
  const tv = tensionVaporHpa(input.tSeca, input.tHumeda, pEstHpa);
  const pr = puntoRocio(tv);
  const hr = humedadRelativa(tv, input.tSeca);

  const tSeca12hAntes = input.tSeca12hAntes != null ? input.tSeca12hAntes : input.tSeca;
  const tPromedio = (input.tSeca + tSeca12hAntes) / 2;
  const corrD4 = correccionD4(tPromedio, pEstMmhg);
  const pnmMmhg = pEstMmhg + corrD4;
  const pnmHpa = mmhgAHpa(pnmMmhg);

  return {
    pEstMmhg: redondear1_(pEstMmhg),
    pEstHpa: redondear1_(pEstHpa),
    tensionVapor: redondear1_(tv),
    puntoRocio: redondear1_(pr),
    humedadRelativa: redondear1_(hr),
    pnmMmhg: redondear1_(pnmMmhg),
    pnmHpa: redondear1_(pnmHpa),
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    ESTACION, calcularObservacion, presionEstacionMmhg, mmhgAHpa, tensionVaporHpa,
    puntoRocio, humedadRelativa, TABLA_D4, correccionD4, RANGOS, validarObservacion,
  };
}
