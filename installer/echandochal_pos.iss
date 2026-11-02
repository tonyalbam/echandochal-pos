#ifndef MyAppVersion
  #define MyAppVersion "1.0.0-rc1"
#endif

[Setup]
#ifdef SandboxBuild
AppId={{6AC076C2-1A66-463C-995D-9600B43D4F54}
AppName=Echando Chal POS (PRUEBAS)
#else
AppId={{73C9AB99-2794-4384-BCA5-D2EEB61E63EF}
AppName=Echando Chal POS
#endif
AppVersion={#MyAppVersion}
AppPublisher=Echando Chal
#ifdef SandboxBuild
DefaultDirName={localappdata}\Programs\EchandoChalPOS-Sandbox
#else
DefaultDirName={localappdata}\Programs\EchandoChalPOS
#endif
#ifdef SandboxBuild
DefaultGroupName=Echando Chal POS (PRUEBAS)
#else
DefaultGroupName=Echando Chal POS
#endif
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
#ifdef SandboxBuild
OutputBaseFilename=EchandoChalPOS-SANDBOX-{#MyAppVersion}
#else
OutputBaseFilename=EchandoChalPOS-Setup-{#MyAppVersion}
#endif
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\EchandoChalPOS.exe
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos adicionales:"; Flags: unchecked

[Files]
Source: "..\dist\EchandoChalPOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
#ifdef SandboxBuild
Name: "{autoprograms}\Echando Chal POS (PRUEBAS)"; Filename: "{app}\EchandoChalPOS.exe"; WorkingDir: "{app}"
#else
Name: "{autoprograms}\Echando Chal POS"; Filename: "{app}\EchandoChalPOS.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Echando Chal POS"; Filename: "{app}\EchandoChalPOS.exe"; WorkingDir: "{app}"; Tasks: desktopicon
#endif

[Run]
#ifndef SandboxBuild
Filename: "{app}\EchandoChalPOS.exe"; Description: "Abrir Echando Chal POS"; Flags: nowait postinstall skipifsilent
#endif

; Protección de instalaciones antiguas que todavía guardan datos en {app}.
; La actualización debe realizarse únicamente después de migrar la base
; a una carpeta externa y verificar su respaldo.
[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  LegacyDatabase: String;
  LegacyDataDir: String;
begin
  Result := '';
  LegacyDataDir := ExpandConstant('{app}\data');
  LegacyDatabase := LegacyDataDir + '\echandochal.db';

  if FileExists(LegacyDatabase) or
     FileExists(LegacyDatabase + '-wal') or
     FileExists(LegacyDatabase + '-shm') or
     DirExists(ExpandConstant('{app}\backups')) then
  begin
    Result :=
      'Se detectaron datos o respaldos de una instalación anterior ' +
      'dentro de la carpeta del programa.' + #13#10 + #13#10 +
      'Por seguridad, la instalación se ha detenido sin modificar esos archivos.' + #13#10 + #13#10 +
      'Primero migre la base de datos a una carpeta externa y confirme ' +
      'que tiene un respaldo válido. Después vuelva a ejecutar el instalador.';
  end;
end;
