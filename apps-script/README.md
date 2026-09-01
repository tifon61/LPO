# Despliegue del backend (Google Apps Script + Google Sheet)

Este backend es independiente de cualquier otro proyecto/Sheet que ya uses.
Vas a crear una Sheet nueva solo para esto.

## 1. Crear la Google Sheet

1. Andá a [sheets.google.com](https://sheets.google.com) y creá una planilla nueva.
   Nombrala como quieras, por ejemplo "LPO — Observaciones meteorológicas".
2. No hace falta crear ninguna hoja/columna a mano: el script crea la hoja
   "Observaciones" con los encabezados la primera vez que se ejecuta.

## 2. Crear el proyecto de Apps Script

1. En la Sheet, andá a **Extensiones > Apps Script**. Esto crea un proyecto
   de Apps Script vinculado a esa planilla (así `SpreadsheetApp.getActiveSpreadsheet()`
   apunta directo a ella, sin necesidad de ID).
2. Borrá el contenido del archivo `Code.gs` que abre por defecto y pegá ahí
   todo el contenido de [`Code.gs`](./Code.gs) de este repo.
3. Guardá (ícono de disco o Ctrl+S).

## 3. Configurar el token de seguridad

El Web App queda accesible por URL para cualquiera (es la única forma de que
un formulario en GitHub Pages le pueda escribir sin backend propio), así que
usamos un token simple para que no cualquiera pueda mandar datos falsos.

1. En el editor de Apps Script: **Project Settings** (ícono de engranaje) >
   **Script Properties** > **Add script property**.
2. Property: `TOKEN`. Value: inventá un string largo y difícil de adivinar
   (por ejemplo, generalo con `openssl rand -hex 16` o cualquier generador
   de contraseñas).
3. Guardá ese mismo valor: lo vas a necesitar en el paso 5.

## 4. Desplegar como Web App

1. En el editor de Apps Script: **Deploy > New deployment**.
2. Tipo: **Web app**.
3. Configuración:
   - **Execute as**: Me (tu cuenta) — así el script escribe en la Sheet con
     tus permisos, sin importar quién llame a la URL.
   - **Who has access**: **Anyone** (no "Anyone with Google account" —
     necesitamos que funcione sin login, y además así el propio Google agrega
     los headers CORS que hacen falta para que el formulario en GitHub Pages
     pueda llamar a esta URL).
4. Deploy. La primera vez te va a pedir autorizar permisos (acceso a tus
   propias Sheets) — es tu propio script, es seguro autorizarlo.
5. Copiá la **Web app URL** que te da (termina en `/exec`).

## 5. Conectar el frontend

En `observaciones/config.js` (en este repo):

```js
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycb.../exec";
const APPS_SCRIPT_TOKEN = "el-mismo-token-del-paso-3";
```

Commiteá y pusheá. Si el repo está publicado con GitHub Pages, `observaciones/index.html`
ya va a poder cargar observaciones y `observaciones/historico.html` va a poder leerlas.

## 6. Volver a desplegar después de editar Code.gs

Apps Script no actualiza el Web App en vivo cuando editás el código: cada vez
que cambies `Code.gs`, tenés que ir a **Deploy > Manage deployments**, elegir
la deployment activa, y usar el ícono de lápiz para crear una **nueva versión**
(no hace falta cambiar la URL, esta se mantiene igual entre versiones).

## Notas

- El cálculo de las variables derivadas se hace en el propio Apps Script
  (server-side), no confía en lo que calcule el navegador — así el histórico
  queda consistente aunque cambies la UI del formulario.
- Si en algún momento cambiás una fórmula, replicala en los dos lugares:
  `observaciones/calculos.js` (preview en el navegador) y `apps-script/Code.gs`
  (cálculo autoritativo que se guarda).
- Este backend es de un solo usuario/estación. Si más adelante necesitás
  varias estaciones, hay que agregar una columna "estación" y parametrizar
  latitud/elevación por fila en vez de la constante `ESTACION` fija.
