/**
 * Backend de Google Apps Script para el Control de Calidad (QC) del
 * Laboratorio de Análisis de EMAs (informe-verde.html).
 *
 * Es un backend INDEPENDIENTE del que usa el módulo de observaciones
 * (apps-script/Code.gs) — Sheet propia, deployment propio, token propio.
 * Guarda qué lecturas puntuales de las EMAs (Verde/Blanca/Campbell/Daza) se
 * marcaron como anómalas para excluirlas del análisis, y expone un GET para
 * que el informe las lea y las aplique antes de armar los gráficos/estadísticas.
 *
 * Instrucciones de despliegue: ver apps-script-qc/README.md
 */

var SHEET_NAME = "QC_EMAs";

// Token compartido simple (mismo mecanismo que apps-script/Code.gs). Se
// configura en Project Settings > Script Properties (clave TOKEN).
function getToken_() {
  return PropertiesService.getScriptProperties().getProperty("TOKEN") || "";
}

// Columnas de la Sheet, en orden.
var COLUMNAS = [
  { key: "estacion", header: "Estación" },       // verde | blanca | campbell | daza
  { key: "variable", header: "Variable" },        // temp | hum | pres | lluvia
  { key: "timestampIso", header: "Timestamp (ISO)" }, // instante exacto de la lectura original marcada
  { key: "valor", header: "Valor original" },
  { key: "motivo", header: "Motivo" },
  { key: "marcadoPor", header: "Marcado por" },
  { key: "fechaMarcado", header: "Fecha de marcado" },
];

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

function claveFila_(estacion, variable, timestampIso) {
  return estacion + "|" + variable + "|" + timestampIso;
}

// Devuelve un mapa clave->numeroDeFila (1-indexado) de todo lo que ya está
// marcado, para no duplicar ni tener que recorrer la Sheet por cada punto.
function indiceExistente_(sheet) {
  var valores = sheet.getDataRange().getValues();
  var colEstacion = COLUMNAS.findIndex(function (c) { return c.key === "estacion"; });
  var colVariable = COLUMNAS.findIndex(function (c) { return c.key === "variable"; });
  var colTs = COLUMNAS.findIndex(function (c) { return c.key === "timestampIso"; });
  var indice = {};
  for (var i = 1; i < valores.length; i++) {
    var clave = claveFila_(valores[i][colEstacion], valores[i][colVariable], valores[i][colTs]);
    indice[clave] = i + 1; // fila real en la Sheet (1-indexada)
  }
  return indice;
}

// Marca uno o varios puntos como anómalos. body.puntos: array de
// { estacion, variable, timestampIso, valor, motivo }. body.marcadoPor: opcional.
function marcarPuntos_(body) {
  var puntos = body.puntos;
  if (!Array.isArray(puntos) || puntos.length === 0) {
    return { ok: false, error: "No se recibió ningún punto para marcar." };
  }

  var sheet = getSheet_();
  var indice = indiceExistente_(sheet);
  var ahora = new Date().toISOString();
  var filasNuevas = [];
  var yaMarcados = 0;

  puntos.forEach(function (p) {
    if (!p.estacion || !p.variable || !p.timestampIso) return;
    var clave = claveFila_(p.estacion, p.variable, p.timestampIso);
    if (indice[clave]) { yaMarcados++; return; } // ya estaba marcado, no duplicar

    filasNuevas.push([
      p.estacion,
      p.variable,
      p.timestampIso,
      p.valor != null ? p.valor : "",
      p.motivo || "",
      body.marcadoPor || "",
      ahora,
    ]);
  });

  if (filasNuevas.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, filasNuevas.length, COLUMNAS.length).setValues(filasNuevas);
  }

  return { ok: true, marcados: filasNuevas.length, yaMarcados: yaMarcados };
}

// Desmarca (elimina la fila de) un punto. body: { estacion, variable, timestampIso }.
function desmarcarPunto_(body) {
  if (!body.estacion || !body.variable || !body.timestampIso) {
    return { ok: false, error: "Faltan estacion/variable/timestampIso para identificar el punto." };
  }
  var sheet = getSheet_();
  var indice = indiceExistente_(sheet);
  var clave = claveFila_(body.estacion, body.variable, body.timestampIso);
  var fila = indice[clave];
  if (!fila) {
    return { ok: false, error: "Ese punto no estaba marcado." };
  }
  sheet.deleteRow(fila);
  return { ok: true };
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

    if (body.accion === "desmarcar") {
      return jsonOut_(desmarcarPunto_(body));
    }
    // Por defecto (o accion === "marcar"): marcar uno o varios puntos.
    return jsonOut_(marcarPuntos_(body));
  } catch (err) {
    return jsonOut_({ ok: false, error: String(err) });
  }
}

// GET: devuelve todos los puntos marcados (opcionalmente filtrados por
// estacion/variable via query params) para que el informe los aplique.
// Formato JSONP si viene ?callback=... (igual que el otro backend), porque
// GitHub Pages + Apps Script no siempre negocian bien CORS para GET con
// fetch() directo en todos los navegadores.
function doGet(e) {
  var callback = e.parameter.callback;
  try {
    var expectedToken = getToken_();
    if (expectedToken && e.parameter.token !== expectedToken) {
      return jsonpOut_({ ok: false, error: "Token inválido." }, callback);
    }

    var sheet = getSheet_();
    var valores = sheet.getDataRange().getValues();
    var puntos = [];
    for (var i = 1; i < valores.length; i++) {
      var fila = valores[i];
      var obj = {};
      COLUMNAS.forEach(function (c, idx) { obj[c.key] = fila[idx]; });
      if (e.parameter.estacion && obj.estacion !== e.parameter.estacion) continue;
      if (e.parameter.variable && obj.variable !== e.parameter.variable) continue;
      puntos.push(obj);
    }
    return jsonpOut_({ ok: true, puntos: puntos }, callback);
  } catch (err) {
    return jsonpOut_({ ok: false, error: String(err) }, callback);
  }
}
