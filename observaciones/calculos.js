/**
 * Motor de cálculo de variables meteorológicas derivadas (tipo SYNOP).
 * Port directo del script Python/Tkinter original: mismas fórmulas y constantes,
 * para que los resultados coincidan con el histórico ya cargado a mano.
 *
 * Se usa tanto acá (preview en el navegador) como en apps-script/Code.gs
 * (cálculo autoritativo antes de guardar en la Sheet) — si cambiás una
 * fórmula, replicá el cambio en los dos lugares.
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

function prmslMmhg(pEstMmhg, tSeca, eHpa) {
  const eMmhg = eHpa * 0.750062;
  const tk = tSeca + 273.15;
  const tvK = pEstMmhg > 0 ? tk / (1 - 0.378 * (eMmhg / pEstMmhg)) : tk;
  const R = 287.05;
  const gradienteTemp = 0.0065;
  return (
    pEstMmhg *
    Math.pow(
      1 - (gradienteTemp * ESTACION.elevacion) / tvK,
      -ESTACION.gravedadLocal / (R * gradienteTemp)
    )
  );
}

/**
 * input: { tSeca, tHumeda, tMax, tMin, tAdjunto, barometro, lluvia } (números; opcionales pueden ser null)
 * devuelve todas las variables derivadas.
 */
function calcularObservacion(input) {
  const pEstMmhg = presionEstacionMmhg(input.barometro, input.tAdjunto);
  const pEstHpa = mmhgAHpa(pEstMmhg);
  const tv = tensionVaporHpa(input.tSeca, input.tHumeda, pEstHpa);
  const pr = puntoRocio(tv);
  const hr = humedadRelativa(tv, input.tSeca);
  const pnmMmhg = prmslMmhg(pEstMmhg, input.tSeca, tv);
  const pnmHpa = mmhgAHpa(pnmMmhg);

  return {
    pEstMmhg,
    pEstHpa,
    tensionVapor: tv,
    puntoRocio: pr,
    humedadRelativa: hr,
    pnmMmhg,
    pnmHpa,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { ESTACION, calcularObservacion, presionEstacionMmhg, mmhgAHpa, tensionVaporHpa, puntoRocio, humedadRelativa, prmslMmhg };
}
