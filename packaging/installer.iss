; installer.iss - PeechaVisit Windows installer (Inno Setup 6)
; ════════════════════════════════════════════════
; Build (from project root, after PyInstaller):
;   iscc /DAppVersion=3.0 packaging\installer.iss
; Needs:
;   dist\PeechaVisit\                 (PyInstaller output)
;   packaging\winsw\PeechaVisitService.exe   (WinSW-x64.exe renamed)
;
; What it does:
;   - installs the compiled program to Program Files (no source code)
;   - data folder: C:\ProgramData\PeechaVisit (settings.json, photos, logs)
;   - asks for SQL Server connection on first install
;   - registers the Windows service "PeechaVisit" (automatic start)
;   - opens firewall ports 5000, 8000, 8501, 8502
; ════════════════════════════════════════════════

#ifndef AppVersion
  #define AppVersion "3.0"
#endif
#define AppName "PeechaVisit"
#define DataDir "{commonappdata}\PeechaVisit"
#define Svc "{app}\PeechaVisitService.exe"

[Setup]
AppId={{6E0F3C52-6F4B-4C1B-9B3E-50E1C9A1B7D4}
AppName={#AppName}
AppVerName={#AppName} {#AppVersion}
AppVersion={#AppVersion}
AppPublisher=Peecha
AppPublisherURL=https://peecha.ir
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=PeechaVisit-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName} Server
CloseApplications=no

[Dirs]
Name: "{#DataDir}"
Name: "{#DataDir}\static"
Name: "{#DataDir}\logs"

[Files]
Source: "..\dist\PeechaVisit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "winsw\PeechaVisitService.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "PeechaVisitService.xml"; DestDir: "{app}"; Flags: ignoreversion
Source: "grant_service_sql.sql"; DestDir: "{app}"; Flags: ignoreversion

[INI]
Filename: "{app}\Dashboard.url"; Section: "InternetShortcut"; Key: "URL"; String: "http://localhost:8501"
Filename: "{app}\Admin Panel.url"; Section: "InternetShortcut"; Key: "URL"; String: "http://localhost:8502"

[Icons]
Name: "{group}\PeechaVisit Dashboard"; Filename: "{app}\Dashboard.url"
Name: "{group}\PeechaVisit Admin Panel"; Filename: "{app}\Admin Panel.url"
Name: "{group}\Data folder (settings, photos, logs)"; Filename: "{#DataDir}"
Name: "{group}\Uninstall PeechaVisit"; Filename: "{uninstallexe}"
Name: "{commondesktop}\PeechaVisit Dashboard"; Filename: "{app}\Dashboard.url"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut for the dashboard"

[Run]
; tighten data folder: settings.json holds the DB password
Filename: "{sys}\icacls.exe"; Parameters: """{#DataDir}"" /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F *S-1-5-32-544:(OI)(CI)F"; Flags: runhidden waituntilterminated; StatusMsg: "Securing data folder..."
Filename: "{app}\PeechaVisit.exe"; Parameters: "{code:ConfigureParams}"; Flags: runhidden waituntilterminated; StatusMsg: "Saving database settings..."; Check: NeedConfig
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PeechaVisit"""; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""PeechaVisit"" dir=in action=allow protocol=TCP localport=5000,8000,8501,8502"; Flags: runhidden waituntilterminated; StatusMsg: "Opening firewall ports..."
Filename: "{#Svc}"; Parameters: "install"; Flags: runhidden waituntilterminated; StatusMsg: "Registering Windows service..."
Filename: "{#Svc}"; Parameters: "start"; Flags: runhidden waituntilterminated; StatusMsg: "Starting service..."
Filename: "{app}\Admin Panel.url"; Description: "Open the admin panel"; Flags: postinstall shellexec nowait skipifsilent

[UninstallRun]
Filename: "{#Svc}"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "SvcStop"
Filename: "{#Svc}"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "SvcRemove"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PeechaVisit"""; Flags: runhidden waituntilterminated; RunOnceId: "Firewall"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{#DataDir}\run"

[Code]
var
  DbPage: TInputQueryWizardPage;

function SettingsFile: String;
begin
  Result := ExpandConstant('{commonappdata}\PeechaVisit\settings.json');
end;

function NeedConfig: Boolean;
begin
  { upgrade: keep the existing settings }
  Result := not FileExists(SettingsFile);
end;

procedure InitializeWizard;
begin
  DbPage := CreateInputQueryPage(wpSelectDir,
    'Database connection',
    'SQL Server used by PeechaVisit',
    'Enter the SQL Server name (as in SQL Server Management Studio, e.g. SERVER\SQLEXPRESS or .\RAD).' + #13#10 +
    'Leave user name empty to use Windows authentication (then run grant_service_sql.sql once, see docs).');
  DbPage.Add('SQL Server name:', False);
  DbPage.Add('SQL user name (empty = Windows authentication):', False);
  DbPage.Add('SQL password:', True);
  DbPage.Add('PeechaVisit database:', False);
  DbPage.Add('Sales database (customers / products):', False);
  DbPage.Values[0] := 'localhost';
  DbPage.Values[3] := 'tracking';
  DbPage.Values[4] := 'dejavuDB1';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = DbPage.ID) and not NeedConfig;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = DbPage.ID) and (Trim(DbPage.Values[0]) = '') then
  begin
    MsgBox('SQL Server name is required.', mbError, MB_OK);
    Result := False;
  end;
end;

function Q(const S: String): String;
var
  T: String;
begin
  T := S;
  StringChangeEx(T, '"', '\"', True);
  Result := '"' + T + '"';
end;

function ConfigureParams(Param: String): String;
begin
  { --name=value: a value starting with '-' is still read as a value }
  Result := '--configure --server=' + Q(Trim(DbPage.Values[0])) +
            ' --user=' + Q(Trim(DbPage.Values[1])) +
            ' --password=' + Q(DbPage.Values[2]) +
            ' --tracking=' + Q(Trim(DbPage.Values[3])) +
            ' --sales=' + Q(Trim(DbPage.Values[4]));
end;

{ upgrade: stop the running service before files are replaced }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Svc: String;
begin
  Result := '';
  Svc := ExpandConstant('{app}\PeechaVisitService.exe');
  if FileExists(Svc) then
  begin
    Exec(Svc, 'stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Exec(Svc, 'uninstall', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Sleep(2000);
  end;
end;
