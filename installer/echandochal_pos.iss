#ifndef MyAppVersion
  #define MyAppVersion "1.0.0-rc1"
#endif

[Setup]
AppId={{73C9AB99-2794-4384-BCA5-D2EEB61E63EF}
AppName=Echando Chal POS
AppVersion={#MyAppVersion}
AppPublisher=Echando Chal
DefaultDirName={localappdata}\Programs\EchandoChalPOS
DefaultGroupName=Echando Chal POS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=EchandoChalPOS-Setup-{#MyAppVersion}
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
Name: "{autoprograms}\Echando Chal POS"; Filename: "{app}\EchandoChalPOS.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Echando Chal POS"; Filename: "{app}\EchandoChalPOS.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\EchandoChalPOS.exe"; Description: "Abrir Echando Chal POS"; Flags: nowait postinstall skipifsilent
