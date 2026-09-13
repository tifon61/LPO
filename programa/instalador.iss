; Script de Inno Setup para armar un instalador de Windows de verdad
; (asistente, acceso directo en el Escritorio y en el Menú Inicio,
; desinstalador en "Aplicaciones y características").
;
; Requiere: haber generado antes dist\ObservacionesLPO.exe con PyInstaller
; (ver README.md, sección "Empaquetarlo como .exe").
;
; Cómo compilarlo:
;   1. Instalá Inno Setup (gratis): https://jrsoftware.org/isinfo.php
;   2. Abrí este archivo (instalador.iss) con el Inno Setup Compiler.
;   3. Build > Compile (o F9).
;   4. Te deja el instalador en programa\Output\Instalador_ObservacionesLPO.exe

#define MyAppName "Observaciones LPO"
#define MyAppVersion "1.0"
#define MyAppExeName "ObservacionesLPO.exe"

[Setup]
AppId={{B7C1B6C4-6E1E-4C9D-9C7B-3F6E7B6B4A20}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Output
OutputBaseFilename=Instalador_ObservacionesLPO
SetupIconFile=icono.ico
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
