; Script de Inno Setup para ServiceReloj

[Setup]
AppName=ServiceReloj
AppVersion=1.0
DefaultDirName=C:\ServiceReloj\SRTime
DisableDirPage=yes
OutputDir=dist
OutputBaseFilename=ServiceRelojInstaller
SetupIconFile=dist/sr_icon.ico



[Files]
Source: "dist/main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist/attendance.db"; DestDir: "{app}"; Flags: ignoreversion uninsneveruninstall
Source: "dist/sr_icon.ico"; DestDir: "{app}"; Flags: ignoreversion


[Icons]
Name: "{group}\ServiceReloj"; Filename: "{app}\main.exe"; WorkingDir: "{app}"; IconFilename: "{app}\sr_icon.ico"
Name: "{userdesktop}\ServiceReloj"; Filename: "{app}\main.exe"; WorkingDir: "{app}"; IconFilename: "{app}\sr_icon.ico"


[Run]
Filename: "{app}\main.exe"; Description: "Iniciar ServiceReloj"; Flags: nowait postinstall skipifsilent
