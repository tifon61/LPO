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

// Zona horaria de la estación, para volver a formatear fecha/hora si Google
// Sheets las auto-convirtió a un valor de fecha/hora al guardarlas (pasa
// solo por cómo Sheets interpreta el texto, no es algo que hagamos nosotros).
var ZONA_HORARIA = "America/Argentina/Buenos_Aires";

function formatearFecha_(valor) {
  if (Object.prototype.toString.call(valor) === "[object Date]") {
    return Utilities.formatDate(valor, ZONA_HORARIA, "yyyy-MM-dd");
  }
  return valor;
}

function formatearHora_(valor) {
  if (Object.prototype.toString.call(valor) === "[object Date]") {
    return Utilities.formatDate(valor, ZONA_HORARIA, "HH:mm");
  }
  return valor;
}

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
  { key: "observador", header: "Observador" },
  { key: "tSeca", header: "T. Bulbo Seco" },
  { key: "tHumeda", header: "T. Bulbo Húmedo" },
  { key: "tMax", header: "T. Máx" },
  { key: "tMin", header: "T. Mín" },
  { key: "tAdjunto", header: "T. Adjunto" },
  { key: "barometro", header: "Barómetro" },
  { key: "tSeca12hAntes", header: "T. Bulbo Seco (12hs antes)" },
  { key: "pEstMmhg", header: "P. Estación (mmHg)" },
  { key: "pEstHpa", header: "P. Estación (hPa)" },
  { key: "pnmMmhg", header: "P. Nivel Mar (mmHg)" },
  { key: "pnmHpa", header: "P. Nivel Mar (hPa)" },
  { key: "tensionVapor", header: "Tensión de Vapor (hPa)" },
  { key: "puntoRocio", header: "Punto de Rocío" },
  { key: "humedadRelativa", header: "Humedad Relativa" },
  { key: "lluvia", header: "Lluvia (mm)" },
  { key: "cargadoEl", header: "Cargado el" },
  { key: "descartada", header: "Descartada" },
  { key: "motivoDescarte", header: "Motivo descarte" },
  { key: "descartadoPor", header: "Descartado por" },
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

// Tabla D-4 del SMN (Oficina de Cálculos Generales), específica de esta
// estación (La Plata — latitud 34°55', altura 14.97 m): valores a SUMAR a
// la presión de estación (ya corregida) para obtener la presión a nivel
// del mar. Reemplaza la fórmula hipsométrica genérica.
var TABLA_D4 = [
  // tMin, tMax: rango de la temperatura PROMEDIO del termómetro seco (°C).
  // c730: columna "730.00 a 759.99 mmHg" · c760: columna "760.00 a 789.99 mmHg"
  { tMin: -10.0, tMax: -0.1, c730: 1.4, c760: 1.5 },
  { tMin: 0.0, tMax: 9.9, c730: 1.4, c760: 1.4 },
  { tMin: 10.0, tMax: 19.9, c730: 1.3, c760: 1.4 },
  { tMin: 20.0, tMax: 29.9, c730: 1.3, c760: 1.3 },
  { tMin: 30.0, tMax: 39.9, c730: 1.2, c760: 1.3 },
  { tMin: 40.0, tMax: 49.9, c730: 1.2, c760: 1.2 },
];

function correccionD4_(tPromedio, pEstMmhg) {
  var fila = null;
  for (var i = 0; i < TABLA_D4.length; i++) {
    if (tPromedio >= TABLA_D4[i].tMin && tPromedio <= TABLA_D4[i].tMax) {
      fila = TABLA_D4[i];
      break;
    }
  }
  if (!fila) {
    fila = tPromedio < TABLA_D4[0].tMin ? TABLA_D4[0] : TABLA_D4[TABLA_D4.length - 1];
  }
  return pEstMmhg < 760.0 ? fila.c730 : fila.c760;
}

// Rangos físicamente razonables para esta estación (La Plata). No son los
// extremos absolutos posibles — un colchón generoso para atajar errores de
// tipeo, no para rechazar lecturas reales raras. Mismos límites que
// observaciones/calculos.js y programa/calculos.py.
var RANGOS = {
  tSeca: { min: -15, max: 45, etiqueta: "T. Bulbo Seco" },
  tHumeda: { min: -15, max: 45, etiqueta: "T. Bulbo Húmedo" },
  tMax: { min: -15, max: 45, etiqueta: "T. Máx" },
  tMin: { min: -15, max: 45, etiqueta: "T. Mín" },
  tAdjunto: { min: -15, max: 45, etiqueta: "T. Adjunto" },
  tSeca12hAntes: { min: -15, max: 45, etiqueta: "T. Bulbo Seco 12hs antes" },
  barometro: { min: 700, max: 800, etiqueta: "Barómetro" },
  lluvia: { min: 0, max: 500, etiqueta: "Lluvia" },
};

// Esta estación solo toma observaciones a las tres horas sinópticas
// (12, 18 y 00 UTC), en hora local de Argentina (UTC-3).
var HORAS_VALIDAS = ["09:00", "15:00", "21:00"];

function validarObservacion_(input) {
  var errores = [];
  for (var campo in RANGOS) {
    var valor = input[campo];
    if (valor === null || valor === undefined || valor === "") continue;
    if (typeof valor !== "number" || isNaN(valor)) {
      errores.push(RANGOS[campo].etiqueta + ": no es un número válido.");
      continue;
    }
    var r = RANGOS[campo];
    if (valor < r.min || valor > r.max) {
      errores.push(r.etiqueta + " fuera de rango razonable (entre " + r.min + " y " + r.max + ").");
    }
  }
  if (typeof input.tSeca === "number" && typeof input.tHumeda === "number" && input.tHumeda > input.tSeca + 0.05) {
    errores.push("La T. Bulbo Húmedo no puede ser mayor que la T. Bulbo Seco.");
  }
  if (typeof input.tSeca === "number" && typeof input.tMax === "number" && input.tMax < input.tSeca - 0.05) {
    errores.push("La T. Máx no puede ser menor que la T. Bulbo Seco actual.");
  }
  if (typeof input.tSeca === "number" && typeof input.tMin === "number" && input.tMin > input.tSeca + 0.05) {
    errores.push("La T. Mín no puede ser mayor que la T. Bulbo Seco actual.");
  }
  if (input.hora && HORAS_VALIDAS.indexOf(input.hora) === -1) {
    errores.push("La hora debe ser una de las tres observaciones sinópticas: " + HORAS_VALIDAS.join(", ") + ".");
  }
  return errores;
}

// Redondea a 1 decimal — evita guardar el resultado crudo de la cuenta en
// punto flotante (con 8-10 decimales de ruido) en la celda de la Sheet.
function redondear1_(n) {
  return Math.round(n * 10) / 10;
}

function calcularObservacion_(input) {
  var pEstMmhg = presionEstacionMmhg_(input.barometro, input.tAdjunto);
  var pEstHpa = mmhgAHpa_(pEstMmhg);
  var tv = tensionVaporHpa_(input.tSeca, input.tHumeda, pEstHpa);
  var pr = puntoRocio_(tv);
  var hr = humedadRelativa_(tv, input.tSeca);

  var tSeca12hAntes = input.tSeca12hAntes != null ? input.tSeca12hAntes : input.tSeca;
  var tPromedio = (input.tSeca + tSeca12hAntes) / 2;
  var corrD4 = correccionD4_(tPromedio, pEstMmhg);
  var pnmMmhg = pEstMmhg + corrD4;
  var pnmHpa = mmhgAHpa_(pnmMmhg);

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

// Busca la fila (1-indexada, incluyendo el encabezado) cuya fecha+hora
// coincida. Devuelve -1 si no la encuentra.
function buscarFilaPorClave_(sheet, fecha, hora) {
  var colFecha = COLUMNAS.findIndex(function (c) { return c.key === "fecha"; }) + 1;
  var colHora = COLUMNAS.findIndex(function (c) { return c.key === "hora"; }) + 1;
  var valores = sheet.getDataRange().getValues();
  for (var i = 1; i < valores.length; i++) {
    var filaFecha = formatearFecha_(valores[i][colFecha - 1]);
    var filaHora = formatearHora_(valores[i][colHora - 1]);
    if (filaFecha === fecha && filaHora === hora) {
      return i + 1; // +1 porque getValues() es 0-indexado y las filas de Sheets son 1-indexadas
    }
  }
  return -1;
}

function marcarDescarte_(body) {
  if (!body.fecha || !body.hora) {
    return { ok: false, error: "Faltan fecha y hora para identificar la observación." };
  }
  var descartada = !!body.descartada;
  if (descartada && !body.motivo) {
    return { ok: false, error: "Hace falta un motivo para descartar una observación." };
  }

  var sheet = getSheet_();
  var numeroFila = buscarFilaPorClave_(sheet, body.fecha, body.hora);
  if (numeroFila === -1) {
    return { ok: false, error: "No se encontró ninguna observación con esa fecha y hora." };
  }

  var colDescartada = COLUMNAS.findIndex(function (c) { return c.key === "descartada"; }) + 1;
  var colMotivo = COLUMNAS.findIndex(function (c) { return c.key === "motivoDescarte"; }) + 1;
  var colDescartadoPor = COLUMNAS.findIndex(function (c) { return c.key === "descartadoPor"; }) + 1;
  sheet.getRange(numeroFila, colDescartada).setValue(descartada);
  sheet.getRange(numeroFila, colMotivo).setValue(descartada ? body.motivo : "");
  sheet.getRange(numeroFila, colDescartadoPor).setValue(descartada ? (body.descartadoPor || "") : "");

  return {
    ok: true,
    fila: {
      fecha: body.fecha, hora: body.hora, descartada: descartada,
      motivoDescarte: descartada ? body.motivo : "",
      descartadoPor: descartada ? (body.descartadoPor || "") : "",
    },
  };
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

    if (body.accion === "marcar_descarte") {
      return jsonOut_(marcarDescarte_(body));
    }

    var numOrNull = function (v) {
      return v === "" || v == null ? null : Number(v);
    };

    var input = {
      tSeca: Number(body.tSeca),
      tHumeda: Number(body.tHumeda),
      tAdjunto: Number(body.tAdjunto),
      barometro: Number(body.barometro),
      tSeca12hAntes: numOrNull(body.tSeca12hAntes),
    };
    if ([input.tSeca, input.tHumeda, input.tAdjunto, input.barometro].some(isNaN)) {
      return jsonOut_({ ok: false, error: "Faltan datos obligatorios (T. Bulbo Seco, T. Bulbo Húmedo, T. Adjunto, Barómetro)." });
    }

    var tMax = numOrNull(body.tMax);
    var tMin = numOrNull(body.tMin);
    var lluvia = numOrNull(body.lluvia);

    var errores = validarObservacion_({
      tSeca: input.tSeca, tHumeda: input.tHumeda, tAdjunto: input.tAdjunto,
      barometro: input.barometro, tSeca12hAntes: input.tSeca12hAntes,
      tMax: tMax, tMin: tMin, lluvia: lluvia,
    });
    if (errores.length > 0) {
      return jsonOut_({ ok: false, error: errores.join(" ") });
    }

    var calculado = calcularObservacion_(input);

    var fila = {
      fecha: body.fecha || "",
      hora: body.hora || "",
      observador: body.observador || "",
      tSeca: input.tSeca,
      tHumeda: input.tHumeda,
      tMax: tMax === null ? "" : tMax,
      tMin: tMin === null ? "" : tMin,
      tAdjunto: input.tAdjunto,
      barometro: input.barometro,
      tSeca12hAntes: input.tSeca12hAntes == null ? "" : input.tSeca12hAntes,
      pEstMmhg: calculado.pEstMmhg,
      pEstHpa: calculado.pEstHpa,
      pnmMmhg: calculado.pnmMmhg,
      pnmHpa: calculado.pnmHpa,
      tensionVapor: calculado.tensionVapor,
      puntoRocio: calculado.puntoRocio,
      humedadRelativa: calculado.humedadRelativa,
      lluvia: lluvia === null ? "" : lluvia,
      cargadoEl: new Date().toISOString(),
      descartada: false,
      motivoDescarte: "",
      descartadoPor: "",
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
        var valor = row[idx];
        if (c.key === "fecha") valor = formatearFecha_(valor);
        if (c.key === "hora") valor = formatearHora_(valor);
        obj[c.key] = valor;
      });
      filas.push(obj);
    }
    return jsonpOut_({ ok: true, filas: filas }, callback);
  } catch (err) {
    return jsonpOut_({ ok: false, error: String(err) }, callback);
  }
}
