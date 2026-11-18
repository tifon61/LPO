; Script de Inno Setup para armar un instalador de Windows de verdad
; (asistente, acceso directo en el Escritorio y en el Menú Inicio,
; desinstalador en "Aplicaciones y características").
;
; Mismo criterio que programa\instalador.iss (ver ese archivo para más
; detalle) — instalador aparte, para que este programa y el de carga
; diaria queden como dos aplicaciones independientes, cada una con su
; propio ícono y su propio acceso directo.
;
; Requiere: haber generado antes dist\HistoricoLPO.exe con PyInstaller
; (ver README.md, sección "Empaquetarlo como .exe").
;
; Cómo compilarlo:
;   1. Instalá Inno Setup (gratis): https://jrsoftware.org/isinfo.php
;   2. Abrí este archivo (instalador.iss) con el Inno Setup Compiler.
;   3. Build > Compile (o F9).
;   4. Te deja el instalador en historico\Output\Instalador_HistoricoLPO.exe

#define MyAppName "Archivo Histórico LPO"
#define MyAppVersion "1.0"
#define MyAppExeName "HistoricoLPO.exe"

[Setup]
AppId={{E3A2F9D1-5B8C-4A6E-9F2D-1C7B8E4A90D3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Output
OutputBaseFilename=Instalador_HistoricoLPO
SetupIconFile=icono.ico
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; El acceso directo del Escritorio queda SIEMPRE (no es una casilla
; opcional que se pueda destildar) — mismo criterio que programa\.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
