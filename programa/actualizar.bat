@echo off
rem Regenera el .exe y el instalador después de bajar cambios nuevos del
rem repositorio (GitHub) — hace los mismos dos pasos que se hacen a mano
rem (PyInstaller + Inno Setup), pero con un solo doble clic. Pensado para
rem correr en esta misma compu, donde Python 3.10 (32-bit) y las
rem dependencias ya están instaladas (ver README.md, sección "Si la
rem compu es de 32 bits").
setlocal
cd /d "%~dp0"

echo ============================================
echo  Actualizando Observaciones LPO...
echo ============================================
echo.

echo [1/2] Generando ObservacionesLPO.exe...
py -3.10 -m PyInstaller --onefile --windowed --name ObservacionesLPO --icon icono.ico --hidden-import PIL._tkinter_finder --add-data "img;img" --add-data "icono.ico;." main.py
if errorlevel 1 (
    echo.
    echo ERROR: no se pudo generar el .exe. Mira el mensaje de arriba.
    pause
    exit /b 1
)

echo.
echo [2/2] Compilando el instalador con Inno Setup...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo.
    echo No encontre Inno Setup instalado en la ubicacion esperada:
    echo %ISCC%
    echo Abri instalador.iss manualmente con Inno Setup Compiler y apreta F9.
    pause
    exit /b 1
)
%ISCC% instalador.iss
if errorlevel 1 (
    echo.
    echo ERROR: fallo la compilacion del instalador. Mira el mensaje de arriba.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Listo! El instalador nuevo quedo en:
echo  %~dp0Output\Instalador_ObservacionesLPO.exe
echo ============================================
echo.
echo Corre ese instalador para actualizar el programa en esta compu.
pause
