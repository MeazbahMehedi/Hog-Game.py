; Run on Windows after: python tools/build_desktop.py
; Compile: ISCC.exe installers\windows\Hog.iss
#define AppVersion "4.0.0"
[Setup]
AppId=HogGame-MeazbahMehedi
AppName=Hog
AppVersion={#AppVersion}
AppPublisher=Md Meazbah Mehedi Prodhan
AppPublisherURL=https://github.com/MeazbahMehedi
DefaultDirName={localappdata}\Programs\Hog
DefaultGroupName=Hog
PrivilegesRequired=lowest
OutputDir=..\..\dist-installers
OutputBaseFilename=Hog-v{#AppVersion}-windows-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Hog.exe
[Files]
Source: "..\..\dist\Hog\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Hog"; Filename: "{app}\Hog.exe"
Name: "{autodesktop}\Hog"; Filename: "{app}\Hog.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\Hog.exe"; Description: "Open Hog"; Flags: nowait postinstall skipifsilent
; No [UninstallDelete]: user profiles, settings and backups remain in AppData.
