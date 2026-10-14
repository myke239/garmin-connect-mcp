#ifndef AppVersion
  #error AppVersion must be supplied
#endif
#ifndef BundleDir
  #error BundleDir must be supplied
#endif
#ifndef OutputPath
  #define OutputPath "..\dist\installer"
#endif
[Setup]
AppId=DasKreb.GarminConnectMCP.{#AppVersion}
AppName=Garmin Connect MCP
AppVersion={#AppVersion}
AppPublisher=Das Kreb
AppPublisherURL=https://github.com/myke239/garmin-connect-mcp
AppSupportURL=https://github.com/myke239/garmin-connect-mcp/issues
DefaultDirName={localappdata}\Programs\GarminConnectMCP\releases\{#AppVersion}-installer
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\branding\das-kreb-logo.ico
UninstallDisplayIcon={app}\garmin-connect-desktop.exe
OutputDir={#OutputPath}
OutputBaseFilename=garmin-connect-mcp-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter=garmin-connect.exe,garmin-connect-desktop.exe
#ifdef TrustedRelease
SignTool=dasKreb
SignedUninstaller=yes
#else
SignedUninstaller=no
#endif
[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{userprograms}\Garmin Connect MCP {#AppVersion} (Das Kreb)"; Filename: "{app}\garmin-connect-desktop.exe"
[Run]
Filename: "{app}\garmin-connect-desktop.exe"; Description: "Open Garmin Connect setup"; Flags: postinstall nowait skipifsilent
[UninstallRun]
Filename: "{app}\garmin-connect.exe"; Parameters: "installer-unregister"; RunOnceId: "unregister-bundle"; Flags: runhidden waituntilterminated
[UninstallDelete]
Type: files; Name: "{app}\installation.json"
Type: filesandordirs; Name: "{app}\marketplace"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
    if (not Exec(ExpandConstant('{app}\garmin-connect.exe'), 'installer-register', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)) or (ResultCode <> 0) then
      RaiseException('Runtime registration failed. Existing credentials and prior launcher were preserved.');
end;
