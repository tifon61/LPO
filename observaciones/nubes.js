/**
 * Atlas de nubes — datos de los 10 géneros de la OMM (Atlas Internacional de
 * Nubes) con sus especies y variedades principales, más una ilustración
 * propia en SVG para cada género.
 *
 * Cómo reemplazar una ilustración por una foto propia de la estación: basta
 * con agregar un archivo img/nubes/<slug>.jpg (los slugs son "cirrus",
 * "cirrocumulus", "cirrostratus", "altocumulus", "altostratus",
 * "nimbostratus", "stratocumulus", "stratus", "cumulus", "cumulonimbus").
 * La página busca esa foto primero; si no existe, muestra esta ilustración.
 */

const NUBES = [
    {
        slug: "cirrus", abrev: "Ci", nombre: "Cirrus", etapa: "alta", altura: "5 a 13 km",
        descripcion: "Nubes separadas, en forma de filamentos blancos delicados o de bandas angostas, blancas o mayormente blancas. Tienen un aspecto fibroso (como cabello) o un brillo sedoso, o ambos.",
        reconocer: "Se distinguen de los demás géneros altos por su forma filamentosa bien definida, sin la textura granulada del Cirrocumulus ni el velo continuo del Cirrostratus. No suelen producir halo (eso es más típico del Cirrostratus).",
        especies: [
            { nombre: "fibratus", descripcion: "Filamentos casi rectos o algo curvados, sin ganchos ni penachos en los extremos." },
            { nombre: "uncinus", descripcion: "En forma de \"colas de caballo\", con ganchos o penachos terminales curvados hacia arriba." },
            { nombre: "spissatus", descripcion: "Densos, de aspecto grisáceo visto hacia el sol; suelen ser restos del yunque de un Cumulonimbus." },
            { nombre: "castellanus", descripcion: "Con pequeñas protuberancias en forma de torrecillas, indicio de inestabilidad en altura." },
            { nombre: "floccus", descripcion: "Pequeños mechones de bordes deshilachados, a veces con una ligera precipitación (virga) por debajo." },
        ],
        variedades: [
            { nombre: "intortus", descripcion: "Filamentos muy enredados e irregulares." },
            { nombre: "radiatus", descripcion: "Bandas paralelas que, por efecto de perspectiva, parecen converger en el horizonte." },
            { nombre: "vertebratus", descripcion: "Dispuestos como espina de pescado o costillas." },
            { nombre: "duplicatus", descripcion: "Capas superpuestas a distinta altura." },
        ],
    },
    {
        slug: "cirrocumulus", abrev: "Cc", nombre: "Cirrocumulus", etapa: "alta", altura: "5 a 13 km",
        descripcion: "Banco, manto o capa delgada y blanca, sin sombras propias, compuesta de elementos muy pequeños en forma de gránulos u ondulaciones, agrupados o no, parcialmente fusionados.",
        reconocer: "Los elementos individuales tienen un ancho aparente menor a 1°: es la textura más fina de las tres nubes altas. A veces muestra irisación (colores) cerca del sol.",
        especies: [
            { nombre: "stratiformis", descripcion: "En forma de manto o capa extendida." },
            { nombre: "lenticularis", descripcion: "Forma de lente o almendra, aislada y de bordes netos — típica de ondas orográficas." },
            { nombre: "castellanus", descripcion: "Pequeñas torrecillas que le dan un aspecto almenado." },
            { nombre: "floccus", descripcion: "Mechones pequeños con bordes algo deshilachados por debajo." },
        ],
        variedades: [
            { nombre: "undulatus", descripcion: "Con ondulaciones visibles." },
            { nombre: "lacunosus", descripcion: "Aspecto de red o panal, con huecos redondeados distribuidos con regularidad." },
        ],
    },
    {
        slug: "cirrostratus", abrev: "Cs", nombre: "Cirrostratus", etapa: "alta", altura: "5 a 13 km",
        descripcion: "Velo transparente y blanquecino, de aspecto fibroso (como cabello desordenado) o liso, que cubre total o parcialmente el cielo y que, generalmente, produce fenómenos de halo.",
        reconocer: "Si hay halo alrededor del sol o la luna, casi siempre es por Cirrostratus. A diferencia del Altostratus, deja pasar suficiente luz como para que los objetos en el suelo proyecten sombra.",
        especies: [
            { nombre: "fibratus", descripcion: "Velo fibroso, sin estructura definida." },
            { nombre: "nebulosus", descripcion: "Velo difuminado, sin detalle, que da un aspecto lechoso al cielo." },
        ],
        variedades: [
            { nombre: "duplicatus", descripcion: "Capas a distintos niveles." },
            { nombre: "undulatus", descripcion: "Con ondulaciones leves." },
        ],
    },
    {
        slug: "altocumulus", abrev: "Ac", nombre: "Altocumulus", etapa: "media", altura: "2 a 7 km",
        descripcion: "Banco, manto o capa blanca o gris (o ambas a la vez), generalmente con sombras propias, compuesta de glóbulos, guijarros o rollos, fusionados o no; la mayoría de los elementos tienen un ancho aparente entre 1° y 5°.",
        reconocer: "El tamaño de los elementos (1° a 5°, aproximadamente el ancho de un puño con el brazo extendido) es la clave para distinguirlo del Cirrocumulus (más chico) y del Stratocumulus (más grande).",
        especies: [
            { nombre: "stratiformis", descripcion: "Manto extendido en capa." },
            { nombre: "lenticularis", descripcion: "Forma de lente, bordes netos, típica de ondas orográficas." },
            { nombre: "castellanus", descripcion: "Pequeñas torrecillas en la parte superior, señal de inestabilidad en altura." },
            { nombre: "floccus", descripcion: "Mechones redondeados con bordes deshilachados." },
            { nombre: "volutus", descripcion: "En forma de rollo horizontal largo, que parece rodar sobre un eje." },
        ],
        variedades: [
            { nombre: "translucidus", descripcion: "Manto translúcido, deja ver el sol, la luna o el cielo." },
            { nombre: "perlucidus", descripcion: "Con huecos bien definidos entre los elementos, que dejan ver el cielo detrás." },
            { nombre: "opacus", descripcion: "Manto opaco, oculta completamente el sol o la luna." },
            { nombre: "duplicatus", descripcion: "Capas superpuestas." },
            { nombre: "undulatus", descripcion: "Con ondulaciones." },
            { nombre: "radiatus", descripcion: "En bandas paralelas." },
            { nombre: "lacunosus", descripcion: "Aspecto de panal o red." },
        ],
    },
    {
        slug: "altostratus", abrev: "As", nombre: "Altostratus", etapa: "media", altura: "2 a 7 km",
        descripcion: "Manto o capa grisáceo o azulado, de aspecto estriado, fibroso o uniforme, que cubre total o parcialmente el cielo y que presenta partes suficientemente finas para dejar ver el sol, al menos vagamente, como a través de un vidrio esmerilado.",
        reconocer: "A diferencia del Cirrostratus, no produce halo: el sol se ve difuso, sin un contorno neto, \"como a través de un vidrio esmerilado\". Suele preceder a la lluvia o nieve continua.",
        especies: [],
        variedades: [
            { nombre: "translucidus", descripcion: "Lo bastante fino para ver el sol débilmente, sin halo." },
            { nombre: "opacus", descripcion: "Lo bastante grueso para ocultar completamente el sol o la luna." },
        ],
    },
    {
        slug: "nimbostratus", abrev: "Ns", nombre: "Nimbostratus", etapa: "media", altura: "desde superficie hasta 7 km",
        descripcion: "Capa grisácea, con frecuencia de aspecto sombrío, cuyo aspecto queda velado por la precipitación más o menos continua de lluvia o nieve, que en la mayoría de los casos llega al suelo.",
        reconocer: "El sol y la luna no se ven nunca a través de ella (es siempre opaca). Suele acompañarse por debajo de jirones de Stratus fractus (\"pannus\"). No tiene especies ni variedades reconocidas.",
        especies: [],
        variedades: [],
    },
    {
        slug: "stratocumulus", abrev: "Sc", nombre: "Stratocumulus", etapa: "baja", altura: "superficie a 2 km",
        descripcion: "Banco, manto o capa gris o blanquecina (o ambas a la vez), que tiene casi siempre partes oscuras, compuesta de losas, guijarros o rollos, no fibrosos; la mayoría de los elementos ordenados tienen un ancho aparente mayor a 5°.",
        reconocer: "Elementos más grandes (más de 5°) y más bajos que el Altocumulus. A diferencia del Stratus, se distingue una estructura de masas o rollos, no una capa lisa y uniforme.",
        especies: [
            { nombre: "stratiformis", descripcion: "Manto extendido en capa." },
            { nombre: "lenticularis", descripcion: "Forma de lente." },
            { nombre: "castellanus", descripcion: "Pequeñas torrecillas." },
            { nombre: "volutus", descripcion: "En forma de rollo horizontal." },
        ],
        variedades: [
            { nombre: "translucidus", descripcion: "Deja ver el sol, la luna o el cielo." },
            { nombre: "perlucidus", descripcion: "Con huecos bien definidos entre los elementos." },
            { nombre: "opacus", descripcion: "Oculta completamente el sol o la luna." },
            { nombre: "duplicatus", descripcion: "Capas superpuestas." },
            { nombre: "undulatus", descripcion: "Con ondulaciones." },
            { nombre: "radiatus", descripcion: "En bandas paralelas." },
            { nombre: "lacunosus", descripcion: "Aspecto de panal o red." },
        ],
    },
    {
        slug: "stratus", abrev: "St", nombre: "Stratus", etapa: "baja", altura: "superficie a 2 km",
        descripcion: "Capa generalmente gris, de base bastante uniforme, que puede dar lugar a llovizna, cristales de hielo o nieve granular. Cuando el sol es visible a través de la capa, su contorno es neto.",
        reconocer: "Capa lisa y uniforme, sin la estructura de masas del Stratocumulus — es, en esencia, niebla que no llega al suelo. No produce halo, salvo a temperaturas muy bajas.",
        especies: [
            { nombre: "nebulosus", descripcion: "Capa uniforme, sin estructura definida, como una niebla elevada." },
            { nombre: "fractus", descripcion: "Bancos desgarrados, de aspecto cambiante — las típicas \"nubes de mal tiempo\" bajo precipitación o frentes." },
        ],
        variedades: [
            { nombre: "opacus", descripcion: "Oculta completamente el sol o la luna." },
            { nombre: "translucidus", descripcion: "Deja ver la posición del sol o la luna." },
            { nombre: "undulatus", descripcion: "Con ondulaciones leves." },
        ],
    },
    {
        slug: "cumulus", abrev: "Cu", nombre: "Cumulus", etapa: "baja", altura: "superficie a 2 km (base); desarrollo vertical variable",
        descripcion: "Nubes separadas, generalmente densas y de contornos bien definidos, que se desarrollan verticalmente en forma de protuberancias, cúpulas o torres, cuya parte superior a menudo se asemeja a una coliflor. La parte iluminada por el sol es con frecuencia de un blanco brillante; su base, relativamente oscura, es casi horizontal.",
        reconocer: "La especie (humilis / mediocris / congestus) indica directamente cuánto desarrollo vertical tiene, lo cual es útil para anticipar si puede derivar en chaparrones o tormenta.",
        especies: [
            { nombre: "humilis", descripcion: "Desarrollo vertical escaso, achatados — los \"cúmulos de buen tiempo\"." },
            { nombre: "mediocris", descripcion: "Desarrollo vertical moderado, con protuberancias poco pronunciadas." },
            { nombre: "congestus", descripcion: "Desarrollo vertical importante, bordes abultados como coliflor; con frecuencia produce chaparrones (también llamado \"torreón\")." },
            { nombre: "fractus", descripcion: "Jirones desgarrados, de aspecto cambiante." },
        ],
        variedades: [],
    },
    {
        slug: "cumulonimbus", abrev: "Cb", nombre: "Cumulonimbus", etapa: "baja", altura: "superficie a 2 km (base); desarrollo vertical hasta la tropopausa",
        descripcion: "Nube densa y potente, de considerable extensión vertical, en forma de montaña o de enormes torres. Una parte al menos de su región superior es generalmente lisa, fibrosa o estriada, y casi siempre aplanada; esta parte se extiende a menudo en forma de yunque o de amplio penacho.",
        reconocer: "La especie indica qué tan desarrollada está la tormenta: si la cima todavía se ve como coliflor (calvus) o ya es claramente fibrosa/en yunque (capillatus, con la tormenta ya en marcha). Puede traer actividad eléctrica, granizo y rachas fuertes.",
        especies: [
            { nombre: "calvus", descripcion: "La cúspide empieza a perder su contorno de coliflor, pero todavía no tiene forma fibrosa de yunque." },
            { nombre: "capillatus", descripcion: "La cúspide es claramente fibrosa o estriada, con frecuencia en forma de yunque — tormenta ya desarrollada." },
        ],
        variedades: [],
    },
];

const ETAPAS = {
    alta: { nombre: "Nubes altas", rango: "5 a 13 km", color: "#2563eb" },
    media: { nombre: "Nubes medias", rango: "2 a 7 km", color: "#0891b2" },
    baja: { nombre: "Nubes bajas / desarrollo vertical", rango: "superficie a 2 km", color: "#475569" },
};

// Ilustraciones propias en SVG (se usan solo si no existe una foto real en
// img/nubes/<slug>.jpg — ver nota al principio del archivo).
const ILUSTRACIONES = {
    cirrus: `
        <defs><linearGradient id="cieloCi" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#eaf4ff"/><stop offset="1" stop-color="#cfe6fb"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloCi)"/>
        <g stroke="#ffffff" stroke-width="5" fill="none" stroke-linecap="round" opacity="0.95">
            <path d="M30,80 Q120,60 190,78 T330,70"/>
            <path d="M60,110 Q150,90 220,108 T360,100"/>
            <path d="M20,150 Q110,135 170,148 T300,140"/>
            <path d="M90,185 Q170,172 230,183 T350,176"/>
        </g>
        <g stroke="#dce9f5" stroke-width="2" fill="none" stroke-linecap="round" opacity="0.8">
            <path d="M40,82 Q130,64 195,80"/>
            <path d="M70,113 Q155,94 222,111"/>
        </g>`,
    cirrocumulus: `
        <defs><linearGradient id="cieloCc" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#eaf4ff"/><stop offset="1" stop-color="#cfe6fb"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloCc)"/>
        <g fill="#ffffff" opacity="0.95">
            ${Array.from({ length: 70 }).map((_, i) => {
                const col = i % 10, row = Math.floor(i / 10);
                const x = 20 + col * 38 + (row % 2 === 0 ? 0 : 18);
                const y = 40 + row * 26;
                return `<circle cx="${x}" cy="${y}" r="7"/>`;
            }).join("")}
        </g>`,
    cirrostratus: `
        <defs><linearGradient id="cieloCs" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#eef6ff"/><stop offset="1" stop-color="#d7ebfa"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloCs)"/>
        <rect x="0" y="40" width="400" height="160" fill="#ffffff" opacity="0.55"/>
        <circle cx="200" cy="120" r="26" fill="#fff6d8" opacity="0.9"/>
        <circle cx="200" cy="120" r="55" fill="none" stroke="#ffffff" stroke-width="3" opacity="0.8"/>
        <circle cx="200" cy="120" r="75" fill="none" stroke="#ffffff" stroke-width="2" opacity="0.5"/>`,
    altocumulus: `
        <defs><linearGradient id="cieloAc" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#dfe9f2"/><stop offset="1" stop-color="#c3d6e6"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloAc)"/>
        <g fill="#ffffff" opacity="0.92">
            ${Array.from({ length: 24 }).map((_, i) => {
                const col = i % 6, row = Math.floor(i / 6);
                const x = 35 + col * 62 + (row % 2 === 0 ? 0 : 28);
                const y = 55 + row * 42;
                return `<ellipse cx="${x}" cy="${y}" rx="26" ry="16"/>`;
            }).join("")}
        </g>
        <g fill="#9fb3c4" opacity="0.5">
            ${Array.from({ length: 24 }).map((_, i) => {
                const col = i % 6, row = Math.floor(i / 6);
                const x = 35 + col * 62 + (row % 2 === 0 ? 0 : 28);
                const y = 60 + row * 42;
                return `<ellipse cx="${x}" cy="${y}" rx="22" ry="7"/>`;
            }).join("")}
        </g>`,
    altostratus: `
        <defs><linearGradient id="cieloAs" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#b9c4ce"/><stop offset="1" stop-color="#9fadbb"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloAs)"/>
        <rect x="0" y="0" width="400" height="240" fill="#cdd6de" opacity="0.65"/>
        <circle cx="200" cy="115" r="30" fill="#e8e2c8" opacity="0.55"/>`,
    nimbostratus: `
        <defs><linearGradient id="cieloNs" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#6b7684"/><stop offset="1" stop-color="#4f5967"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloNs)"/>
        <g stroke="#dfe4e8" stroke-width="2" opacity="0.55">
            ${Array.from({ length: 16 }).map((_, i) =>
                `<line x1="${20 + i * 26}" y1="150" x2="${5 + i * 26}" y2="230"/>`
            ).join("")}
        </g>`,
    stratocumulus: `
        <defs><linearGradient id="cieloSc" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#c7ccd1"/><stop offset="1" stop-color="#a7adb4"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloSc)"/>
        <g fill="#eef0f2" opacity="0.95">
            ${Array.from({ length: 12 }).map((_, i) => {
                const col = i % 4, row = Math.floor(i / 4);
                const x = 55 + col * 100 + (row % 2 === 0 ? 0 : 45);
                const y = 65 + row * 55;
                return `<ellipse cx="${x}" cy="${y}" rx="48" ry="26"/>`;
            }).join("")}
        </g>
        <g fill="#8a9099" opacity="0.6">
            ${Array.from({ length: 12 }).map((_, i) => {
                const col = i % 4, row = Math.floor(i / 4);
                const x = 55 + col * 100 + (row % 2 === 0 ? 0 : 45);
                const y = 78 + row * 55;
                return `<ellipse cx="${x}" cy="${y}" rx="40" ry="10"/>`;
            }).join("")}
        </g>`,
    stratus: `
        <defs><linearGradient id="cieloSt" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#c9cfd4"/><stop offset="1" stop-color="#b3bac0"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloSt)"/>
        <rect x="0" y="60" width="400" height="140" fill="#dde1e4" opacity="0.8"/>`,
    cumulus: `
        <defs><linearGradient id="cieloCu" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#aee0ff"/><stop offset="1" stop-color="#8fd1f7"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloCu)"/>
        <g fill="#ffffff">
            <ellipse cx="120" cy="175" rx="70" ry="22"/>
            <circle cx="90" cy="150" r="34"/>
            <circle cx="130" cy="140" r="42"/>
            <circle cx="170" cy="155" r="30"/>
            <ellipse cx="290" cy="185" rx="55" ry="18"/>
            <circle cx="270" cy="165" r="26"/>
            <circle cx="300" cy="158" r="30"/>
        </g>
        <g fill="#c7d6de" opacity="0.6">
            <ellipse cx="120" cy="188" rx="62" ry="10"/>
            <ellipse cx="288" cy="196" rx="48" ry="8"/>
        </g>`,
    cumulonimbus: `
        <defs><linearGradient id="cieloCb" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#8fa8c0"/><stop offset="1" stop-color="#5c7391"/>
        </linearGradient></defs>
        <rect width="400" height="240" fill="url(#cieloCb)"/>
        <path d="M80,230 Q90,120 150,90 Q160,40 220,45 Q260,10 320,40 Q370,55 360,90
                 Q400,100 390,130 Q405,160 370,170 Q380,200 320,205
                 Q300,225 220,215 Q160,230 80,230 Z" fill="#eef1f4"/>
        <path d="M100,230 Q120,150 170,130 Q220,170 260,150 Q310,180 340,170 Q360,205 300,215
                 Q260,230 190,222 Q140,232 100,230 Z" fill="#4a5568" opacity="0.85"/>
        <g stroke="#dfe6ec" stroke-width="3" opacity="0.7">
            <line x1="160" y1="205" x2="150" y2="240"/>
            <line x1="200" y1="210" x2="192" y2="240"/>
            <line x1="240" y1="208" x2="232" y2="240"/>
        </g>`,
};
