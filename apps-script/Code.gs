/**
 * Backend de Google Apps Script para el módulo de observaciones (LPO).
 *
 * Recibe observaciones crudas por POST, recalcula las variables derivadas
 * de forma autoritativa (no confía en lo que mande el navegador) y las
 * guarda en la hoja "Observaciones" de la Sheet a la que este script está
 * vinculado. También expone un GET (JSONP) para leer el histórico.
 *
 * Instrucciones de despliegue: ver apps-script/README.md
 */

// ---- Configuración de la estación (debe coincidir con observaciones/calculos.js) ----
var ESTACION = {
  elevacion: 15, // metros
  gravedadLocal: 9.797207,
  gravedadEstandar: 9.80665,
};

var SHEET_NAME = "Observaciones";

// Token compartido simple para evitar que cualquiera con la URL escriba
// datos falsos. Se configura en Project Settings > Script Properties (clave TOKEN).
// Si no se configura ninguno, no se exige token (no recomendado).
function getToken_() {
  return PropertiesService.getScriptProperties().getProperty("TOKEN") || "";
}

// Columnas de la Sheet, en orden. "key" es el nombre que usa el JSON
// (payload del POST y respuesta del GET); "header" es el título visible.
var COLUMNAS = [
  { key: "fecha", header: "Fecha" },
  { key: "hora", header: "Hora" },
  { key: "tSeca", header: "T. Seca" },
  { key: "tHumeda", header: "T. Húmeda" },
  { key: "tMax", header: "T. Máx" },
  { key: "tMin", header: "T. Mín" },
  { key: "tAdjunto", header: "T. Adjunto" },
  { key: "barometro", header: "Barómetro" },
  { key: "pEstMmhg", header: "P. Estación (mmHg)" },
  { key: "pEstHpa", header: "P. Estación (hPa)" },
  { key: "pnmMmhg", header: "P. Nivel Mar (mmHg)" },
  { key: "pnmHpa", header: "P. Nivel Mar (hPa)" },
  { key: "tensionVapor", header: "Tensión de Vapor (hPa)" },
  { key: "puntoRocio", header: "Punto de Rocío" },
  { key: "humedadRelativa", header: "Humedad Relativa" },
  { key: "lluvia", header: "Lluvia (mm)" },
  { key: "cargadoEl", header: "Cargado el" },
];

// ---- Motor de cálculo (mismo que observaciones/calculos.js) ----

function presionEstacionMmhg_(barometro, tAdjunto) {
  var cT = -barometro * 0.000163 * tAdjunto;
  var b0 = barometro + cT;
  return b0 * (ESTACION.gravedadLocal / ESTACION.gravedadEstandar);
}

function mmhgAHpa_(mmhg) {
  return mmhg * (4.0 / 3.0);
}

function tensionVaporHpa_(tSeca, tHumeda, pEstacionHpa) {
  var esHumeda = 6.112 * Math.exp((17.67 * tHumeda) / (tHumeda + 243.5));
  var A = 0.0008;
  var e = esHumeda - A * pEstacionHpa * (tSeca - tHumeda);
  return Math.max(0, e);
}

function puntoRocio_(eHpa) {
  if (eHpa <= 0) return 0.0;
  var numerador = Math.log(eHpa / 6.112) * 243.5;
  var denominador = 17.67 - Math.log(eHpa / 6.112);
  return numerador / denominador;
}

function humedadRelativa_(eHpa, tSeca) {
  var esSeca = 6.112 * Math.exp((17.67 * tSeca) / (tSeca + 243.5));
  var hr = (eHpa / esSeca) * 100;
  return Math.max(0, Math.min(hr, 100));
}

function prmslMmhg_(pEstMmhg, tSeca, eHpa) {
  var eMmhg = eHpa * 0.750062;
  var tk = tSeca + 273.15;
  var tvK = pEstMmhg > 0 ? tk / (1 - 0.378 * (eMmhg / pEstMmhg)) : tk;
  var R = 287.05;
  var gradienteTemp = 0.0065;
  return (
    pEstMmhg *
    Math.pow(
      1 - (gradienteTemp * ESTACION.elevacion) / tvK,
      -ESTACION.gravedadLocal / (R * gradienteTemp)
    )
  );
}

function calcularObservacion_(input) {
  var pEstMmhg = presionEstacionMmhg_(input.barometro, input.tAdjunto);
  var pEstHpa = mmhgAHpa_(pEstMmhg);
  var tv = tensionVaporHpa_(input.tSeca, input.tHumeda, pEstHpa);
  var pr = puntoRocio_(tv);
  var hr = humedadRelativa_(tv, input.tSeca);
  var pnmMmhg = prmslMmhg_(pEstMmhg, input.tSeca, tv);
  var pnmHpa = mmhgAHpa_(pnmMmhg);
  return {
    pEstMmhg: pEstMmhg,
    pEstHpa: pEstHpa,
    tensionVapor: tv,
    puntoRocio: pr,
    humedadRelativa: hr,
    pnmMmhg: pnmMmhg,
    pnmHpa: pnmHpa,
  };
}

// ---- Helpers de la Sheet ----

function getSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(COLUMNAS.map(function (c) { return c.header; }));
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}

function jsonpOut_(obj, callback) {
  var body = callback ? callback + "(" + JSON.stringify(obj) + ");" : JSON.stringify(obj);
  return ContentService.createTextOutput(body).setMimeType(
    callback ? ContentService.MimeType.JAVASCRIPT : ContentService.MimeType.JSON
  );
}

// ---- Endpoints ----

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);

    var expectedToken = getToken_();
    if (expectedToken && body.token !== expectedToken) {
      return jsonOut_({ ok: false, error: "Token inválido." });
    }

    var input = {
      tSeca: Number(body.tSeca),
      tHumeda: Number(body.tHumeda),
      tAdjunto: Number(body.tAdjunto),
      barometro: Number(body.barometro),
    };
    if ([input.tSeca, input.tHumeda, input.tAdjunto, input.barometro].some(isNaN)) {
      return jsonOut_({ ok: false, error: "Faltan datos obligatorios (T. Seca, T. Húmeda, T. Adjunto, Barómetro)." });
    }

    var calculado = calcularObservacion_(input);

    var fila = {
      fecha: body.fecha || "",
      hora: body.hora || "",
      tSeca: input.tSeca,
      tHumeda: input.tHumeda,
      tMax: body.tMax === "" || body.tMax == null ? "" : Number(body.tMax),
      tMin: body.tMin === "" || body.tMin == null ? "" : Number(body.tMin),
      tAdjunto: input.tAdjunto,
      barometro: input.barometro,
      pEstMmhg: calculado.pEstMmhg,
      pEstHpa: calculado.pEstHpa,
      pnmMmhg: calculado.pnmMmhg,
      pnmHpa: calculado.pnmHpa,
      tensionVapor: calculado.tensionVapor,
      puntoRocio: calculado.puntoRocio,
      humedadRelativa: calculado.humedadRelativa,
      lluvia: body.lluvia === "" || body.lluvia == null ? "" : Number(body.lluvia),
      cargadoEl: new Date().toISOString(),
    };

    var sheet = getSheet_();
    sheet.appendRow(COLUMNAS.map(function (c) { return fila[c.key]; }));

    return jsonOut_({ ok: true, fila: fila });
  } catch (err) {
    return jsonOut_({ ok: false, error: String(err) });
  }
}

function doGet(e) {
  var callback = e.parameter.callback;
  try {
    var expectedToken = getToken_();
    if (expectedToken && e.parameter.token !== expectedToken) {
      return jsonpOut_({ ok: false, error: "Token inválido." }, callback);
    }

    var sheet = getSheet_();
    var values = sheet.getDataRange().getValues();
    var filas = [];
    for (var i = 1; i < values.length; i++) {
      var row = values[i];
      var obj = {};
      COLUMNAS.forEach(function (c, idx) {
        obj[c.key] = row[idx];
      });
      filas.push(obj);
    }
    return jsonpOut_({ ok: true, filas: filas }, callback);
  } catch (err) {
    return jsonpOut_({ ok: false, error: String(err) }, callback);
  }
}
