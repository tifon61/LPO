# Despliegue del backend de QC (Google Apps Script + Google Sheet)

Backend **independiente** del de `apps-script/` (observaciones) — Sheet
propia, deployment propio, token propio. Guarda qué lecturas puntuales de
las EMAs (Verde/Blanca/Campbell/Daza) se marcaron como anómalas desde el
Laboratorio de Análisis (`informe-verde.html`), para excluirlas del
análisis la próxima vez que se genere el informe.

## 1. Crear la Google Sheet

1. Andá a [sheets.google.com](https://sheets.google.com) y creá una planilla nueva,
   por ejemplo "LPO — QC EMAs".
2. No hace falta crear ninguna hoja/columna a mano: el script crea la hoja
   "QC_EMAs" con los encabezados la primera vez que se ejecuta.

## 2. Crear el proyecto de Apps Script

1. En la Sheet, andá a **Extensiones > Apps Script**.
2. Borrá el contenido del `Code.gs` que abre por defecto y pegá ahí todo el
   contenido de [`Code.gs`](./Code.gs) de esta carpeta.
3. Guardá (ícono de disco o Ctrl+S).

## 3. Configurar el token de seguridad

1. En el editor de Apps Script: **Project Settings** (ícono de engranaje) >
   **Script Properties** > **Add script property**.
2. Property: `TOKEN`. Value: un string largo y difícil de adivinar (por
   ejemplo, generalo con `openssl rand -hex 16`). Puede ser un token
   distinto al que ya usás en `apps-script/` — de hecho conviene que lo sea,
   ya que es un backend separado.
3. Guardá ese valor: lo vas a necesitar en el paso 5.

## 4. Desplegar como Web App

1. **Deploy > New deployment**. Tipo: **Web app**.
2. **Execute as**: Me (tu cuenta). **Who has access**: **Anyone**.
3. Deploy, autorizá los permisos la primera vez.
4. Copiá la **Web app URL** (termina en `/exec`).

## 5. Conectar el frontend

En `apps-script-qc/qc-config.js` (en este repo):

```js
const QC_APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycb.../exec";
const QC_APPS_SCRIPT_TOKEN = "el-mismo-token-del-paso-3";
```

Commiteá y pusheá. Hasta que esto no esté configurado, la sección de QC del
Laboratorio de Análisis queda deshabilitada (avisa en la propia página) pero
el resto del informe funciona igual.

## 6. Volver a desplegar después de editar Code.gs

Igual que con el otro backend: Apps Script no actualiza el Web App en vivo.
Cada vez que cambie `Code.gs` (por ejemplo, si en el futuro se agrega una
nueva acción), hay que ir a **Deploy > Manage deployments**, elegir la
deployment activa, y usar el ícono de lápiz para crear una **nueva versión**
(la URL no cambia entre versiones).

## Cómo funciona desde el informe

- **Sugerencias de outliers**: al generar el informe, por cada variable
  continua (temperatura/humedad/presión) se calculan los residuos de la
  estación bajo prueba contra Campbell y se listan los puntos cuyo residuo
  se aparta más de 2.5 desvíos estándar del resto — es una sugerencia
  estadística, no un veredicto. El uso decide cuáles marcar.
- **Marcar**: tildar los puntos sospechosos en la tabla y confirmar los
  manda al backend (`accion: "marcar"`, puede ir más de un punto junto).
- **Aplicar**: al generar el informe, primero se trae la lista de puntos ya
  marcados (`GET` a este backend) y esas lecturas se excluyen ANTES de
  agrupar en buckets — quedan afuera sin importar qué resolución
  (diario/horario/crudo) se elija después.
- Los puntos se identifican por estación + variable + timestamp exacto de
  la lectura original (no por el bucket de tiempo mostrado en el gráfico),
  así que la marca es válida sin importar la resolución con la que se
  generó el informe cuando se marcó.
