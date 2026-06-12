[Setup]
AppName=Game Dev Manager
AppVersion=1.0.0
AppPublisher=oliveryin
DefaultDirName={autopf}\Game Dev Manager
DefaultGroupName=Game Dev Manager
OutputDir=installer
OutputBaseFilename=GameDevManager_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\GameDevManager.exe

[Files]
Source: "dist\GameDevManager.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Game Dev Manager"; Filename: "{app}\GameDevManager.exe"
Name: "{group}\Uninstall Game Dev Manager"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Game Dev Manager"; Filename: "{app}\GameDevManager.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional options:"

[Run]
Filename: "{app}\GameDevManager.exe"; Description: "Launch Game Dev Manager"; Flags: nowait postinstall skipifsilent
