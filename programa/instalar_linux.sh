#!/bin/bash
# Instala Observaciones LPO en Linux: lo copia a una carpeta fija (fuera de
# Descargas, para que no se pierda si la vaciás) y crea el ícono tanto en
# el menú de aplicaciones como en el Escritorio.
#
# Uso: ./instalar_linux.sh [ruta/al/ObservacionesLPO]
# Si no se pasa ruta, busca "ObservacionesLPO" en la carpeta actual.
# Si hay un "icono.png" al lado (del repo, o bajado aparte), lo usa; si no,
# usa un ícono genérico del sistema.
set -e

ORIGEN="${1:-ObservacionesLPO}"
DESTINO_DIR="$HOME/.local/share/ObservacionesLPO"

if [ ! -f "$ORIGEN" ]; then
    echo "No se encontró '$ORIGEN'."
    echo "Corré este script en la misma carpeta donde uniste las partes"
    echo "(cat ObservacionesLPO.parte0 ObservacionesLPO.parte1 ObservacionesLPO.parte2 > ObservacionesLPO),"
    echo "o pasale la ruta: ./instalar_linux.sh /ruta/al/ObservacionesLPO"
    exit 1
fi

mkdir -p "$DESTINO_DIR"
cp "$ORIGEN" "$DESTINO_DIR/ObservacionesLPO"
chmod +x "$DESTINO_DIR/ObservacionesLPO"

ICONO_ORIGEN="$(dirname "$ORIGEN")/icono.png"
if [ -f "icono.png" ]; then
    ICONO_ORIGEN="icono.png"
fi
if [ -f "$ICONO_ORIGEN" ]; then
    cp "$ICONO_ORIGEN" "$DESTINO_DIR/icono.png"
    ICONO_FINAL="$DESTINO_DIR/icono.png"
else
    ICONO_FINAL="weather-clear"
fi

cat > "$DESTINO_DIR/ObservacionesLPO.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Observaciones LPO
Comment=Carga de observaciones meteorológicas — La Plata Observatorio
Exec=$DESTINO_DIR/ObservacionesLPO
Icon=$ICONO_FINAL
Terminal=false
Categories=Utility;
EOF
chmod +x "$DESTINO_DIR/ObservacionesLPO.desktop"

# Menú de aplicaciones
mkdir -p "$HOME/.local/share/applications"
cp "$DESTINO_DIR/ObservacionesLPO.desktop" "$HOME/.local/share/applications/"

# Escritorio (si existe la carpeta)
ESCRITORIO="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$ESCRITORIO" ]; then
    cp "$DESTINO_DIR/ObservacionesLPO.desktop" "$ESCRITORIO/"
    chmod +x "$ESCRITORIO/ObservacionesLPO.desktop"
    # En GNOME/Nautilus, un .desktop recién copiado no se puede abrir con
    # doble click hasta "confiar" en él — esto lo marca como confiable solo.
    gio set "$ESCRITORIO/ObservacionesLPO.desktop" "metadata::trusted" true 2>/dev/null || true
    echo "Listo. Ícono creado en el Escritorio ($ESCRITORIO) y en el menú de aplicaciones."
    echo "Si al hacer doble click en el Escritorio pide 'confiar' en el archivo, click derecho -> Permitir lanzar / Allow Launching (una sola vez)."
else
    echo "Listo en el menú de aplicaciones (buscá 'Observaciones LPO')."
    echo "No encontré una carpeta de Escritorio para copiar el ícono ahí también."
fi
