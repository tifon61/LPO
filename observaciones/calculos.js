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
    // "-" marca a propósito "sin dato" (ej. instrumento roto) — se acepta
    // tal cual, sin exigir un número ni rechazarlo como inválido.
    if (valor === "-") continue;
    if (valor === null || valor === undefined || valor === "") {
      errores.push(`Falta completar ${RANGOS[campo].etiqueta}.`);
      continue;
    }
    if (typeof valor !== "number" || Number.isNaN(valor)) {
      errores.push(`${RANGOS[campo].etiqueta}: no es un número válido.`);
      continue;
    }
    const { min, max, etiqueta } = RANGOS[campo];
    if (valor < min || valor > max) {
      errores.push(`${etiqueta} fuera de rango razonable (entre ${min} y ${max}). Revisá si hay un error de tipeo.`);
    }
  }

  if (!input.observador || !String(input.observador).trim()) {
    errores.push("Falta completar el nombre del observador.");
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

// Trata cualquier valor que no sea un número (null, "-", texto raro) como
// "sin dato", para que las cuentas de abajo sepan cuándo tienen que
// saltearse en vez de calcular con un dato inexistente.
function _num(v) {
  return typeof v === "number" && !Number.isNaN(v) ? v : null;
}

// Cada variable derivada se calcula solo si TODO lo que necesita está
// disponible — si algún instrumento se rompió y ese dato quedó marcado
// "-" (sin dato), la cuenta que dependía de él (y las que dependen de esa
// cuenta) queda en null, en vez de calcular con un dato inexistente o
// romper con un error. El resto de las variables que sí tienen todo lo
// que necesitan se siguen calculando normalmente.
function calcularObservacion(input) {
  const barometro = _num(input.barometro);
  const tAdjunto = _num(input.tAdjunto);
  const tSeca = _num(input.tSeca);
  const tHumeda = _num(input.tHumeda);

  const pEstMmhg = barometro != null && tAdjunto != null ? presionEstacionMmhg(barometro, tAdjunto) : null;
  const pEstHpa = pEstMmhg != null ? mmhgAHpa(pEstMmhg) : null;
  const tv = tSeca != null && tHumeda != null && pEstHpa != null ? tensionVaporHpa(tSeca, tHumeda, pEstHpa) : null;
  const pr = tv != null ? puntoRocio(tv) : null;
  const hr = tv != null && tSeca != null ? humedadRelativa(tv, tSeca) : null;

  const tSeca12hAntesDato = _num(input.tSeca12hAntes);
  const tSeca12hAntes = tSeca12hAntesDato != null ? tSeca12hAntesDato : tSeca;
  const tPromedio = tSeca != null && tSeca12hAntes != null ? (tSeca + tSeca12hAntes) / 2 : null;
  const corrD4 = tPromedio != null && pEstMmhg != null ? correccionD4(tPromedio, pEstMmhg) : null;
  const pnmMmhg = pEstMmhg != null && corrD4 != null ? pEstMmhg + corrD4 : null;
  const pnmHpa = pnmMmhg != null ? mmhgAHpa(pnmMmhg) : null;

  return {
    pEstMmhg: pEstMmhg != null ? redondear1_(pEstMmhg) : null,
    pEstHpa: pEstHpa != null ? redondear1_(pEstHpa) : null,
    tensionVapor: tv != null ? redondear1_(tv) : null,
    puntoRocio: pr != null ? redondear1_(pr) : null,
    humedadRelativa: hr != null ? redondear1_(hr) : null,
    pnmMmhg: pnmMmhg != null ? redondear1_(pnmMmhg) : null,
    pnmHpa: pnmHpa != null ? redondear1_(pnmHpa) : null,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    ESTACION, calcularObservacion, presionEstacionMmhg, mmhgAHpa, tensionVaporHpa,
    puntoRocio, humedadRelativa, TABLA_D4, correccionD4, RANGOS, validarObservacion,
  };
}
