; installer.iss - نصب‌کنندهٔ پیچا ویزیت (Inno Setup 6.5 به بعد) — فارسی و راست‌به‌چپ
; ════════════════════════════════════════════════
; ساخت (از ریشهٔ پروژه، بعد از PyInstaller):
;   iscc /DAppVersion=3.6 packaging\installer.iss
; لازم دارد:
;   dist\PeechaVisit\                        (خروجی PyInstaller)
;   packaging\winsw\PeechaVisitService.exe   (WinSW-x64.exe با نام جدید)
;   packaging\Persian.isl                    (پیام‌های فارسی نصب‌کننده)
;
; کارها:
;   - نصب برنامهٔ کامپایل‌شده در Program Files (بدون کد منبع)
;   - پوشهٔ داده: C:\ProgramData\PeechaVisit (settings.json، عکس‌ها، لاگ‌ها)
;   - تنظیم SQL Server با دکمهٔ «آزمایش اتصال» و ساخت خودکار دیتابیس و جدول‌ها
;   - ثبت سرویس ویندوز PeechaVisit (اجرای خودکار) و آیکون وضعیت کنار ساعت
;   - باز کردن پورت‌های 5000، 8000، 8501 و 8502 در فایروال
; ════════════════════════════════════════════════

#ifndef AppVersion
  #define AppVersion "3.0"
#endif
#define AppName "پیچا ویزیت"
#define DataDir "{commonappdata}\PeechaVisit"
#define Svc "{app}\PeechaVisitService.exe"

[Setup]
AppId={{6E0F3C52-6F4B-4C1B-9B3E-50E1C9A1B7D4}
AppName={#AppName}
AppVerName={#AppName} {#AppVersion}
AppVersion={#AppVersion}
AppPublisher=Peecha
AppPublisherURL=https://peecha.ir
; مسیر نصب انگلیسی می‌ماند (مسیر فارسی برای سرویس و پایتون دردسر دارد)
DefaultDirName={autopf}\PeechaVisit
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
WizardSizePercent=120
ShowLanguageDialog=no
UninstallDisplayName={#AppName} (سرور)
UninstallDisplayIcon={app}\PeechaVisit.exe
; لوگوی پیچا: آیکون فایل نصب و تصویرهای صفحه‌های نصب (packaging/make_icons.py)
SetupIconFile=peecha.ico
WizardImageFile=wizard_large_164.bmp,wizard_large_246.bmp,wizard_large_328.bmp
WizardSmallImageFile=wizard_small_58.bmp,wizard_small_87.bmp,wizard_small_116.bmp
CloseApplications=no

[Languages]
Name: "fa"; MessagesFile: "Persian.isl"

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

[InstallDelete]
; میان‌برهای انگلیسی نسخه‌های قبل
Type: files; Name: "{commondesktop}\PeechaVisit Status.lnk"
Type: files; Name: "{commondesktop}\PeechaVisit Dashboard.lnk"
Type: files; Name: "{commondesktop}\PeechaVisit Admin Panel.lnk"
Type: files; Name: "{commonstartup}\PeechaVisit Tray.lnk"
Type: filesandordirs; Name: "{commonprograms}\PeechaVisit"

[Icons]
Name: "{group}\وضعیت سرویس و آدرس‌ها"; Filename: "{app}\PeechaVisitTray.exe"; Parameters: "--page"
Name: "{group}\داشبورد"; Filename: "{app}\Dashboard.url"; IconFilename: "{app}\PeechaVisit.exe"
Name: "{group}\پنل مدیریت"; Filename: "{app}\Admin Panel.url"; IconFilename: "{app}\PeechaVisit.exe"
Name: "{group}\پوشهٔ داده‌ها (تنظیمات، عکس‌ها، لاگ‌ها)"; Filename: "{#DataDir}"
Name: "{group}\حذف پیچا ویزیت"; Filename: "{uninstallexe}"
Name: "{commonstartup}\پیچا ویزیت - آیکون وضعیت"; Filename: "{app}\PeechaVisitTray.exe"
Name: "{commondesktop}\پیچا ویزیت - وضعیت و آدرس‌ها"; Filename: "{app}\PeechaVisitTray.exe"; Parameters: "--page"
Name: "{commondesktop}\پیچا ویزیت - داشبورد"; Filename: "{app}\Dashboard.url"; IconFilename: "{app}\PeechaVisit.exe"
Name: "{commondesktop}\پیچا ویزیت - پنل مدیریت"; Filename: "{app}\Admin Panel.url"; IconFilename: "{app}\PeechaVisit.exe"

[Run]
; پوشهٔ داده فقط برای مدیر و سیستم (settings.json رمز دیتابیس را دارد)
Filename: "{sys}\icacls.exe"; Parameters: """{#DataDir}"" /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F *S-1-5-32-544:(OI)(CI)F"; Flags: runhidden waituntilterminated; StatusMsg: "ایمن کردن پوشهٔ داده‌ها..."
Filename: "{app}\PeechaVisit.exe"; Parameters: "{code:ConfigureParams}"; Flags: runhidden waituntilterminated; StatusMsg: "ذخیرهٔ تنظیمات دیتابیس..."
Filename: "{app}\PeechaVisit.exe"; Parameters: "--setup-db"; Check: WantSetupDb; Flags: runhidden waituntilterminated; StatusMsg: "آماده‌سازی دیتابیس و جدول‌ها..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PeechaVisit"""; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""PeechaVisit"" dir=in action=allow protocol=TCP localport=5000,8000,8501,8502"; Flags: runhidden waituntilterminated; StatusMsg: "باز کردن پورت‌ها در فایروال..."
Filename: "{#Svc}"; Parameters: "install"; Flags: runhidden waituntilterminated; StatusMsg: "ثبت سرویس ویندوز..."
Filename: "{#Svc}"; Parameters: "start"; Flags: runhidden waituntilterminated; StatusMsg: "روشن کردن سرویس..."
Filename: "{app}\PeechaVisitTray.exe"; Parameters: "--page"; Description: "نمایش وضعیت سرویس و آدرس‌ها"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM PeechaVisitTray.exe /F"; Flags: runhidden waituntilterminated; RunOnceId: "TrayStop"
Filename: "{#Svc}"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "SvcStop"
Filename: "{#Svc}"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "SvcRemove"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PeechaVisit"""; Flags: runhidden waituntilterminated; RunOnceId: "Firewall"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{#DataDir}\run"

[Code]
var
  SqlPage: TWizardPage;
  DbPage: TInputQueryWizardPage;
  ServerEdit, UserEdit: TNewEdit;
  PassEdit: TPasswordEdit;
  WinAuthChk, CreateDbChk: TNewCheckBox;
  UserLbl, PassLbl, TestResult: TNewStaticText;
  SettingsText: String;
  SqlTestedOk: Boolean;

function SettingsFile: String;
begin
  Result := ExpandConstant('{commonappdata}\PeechaVisit\settings.json');
end;

{ خواندن "KEY": "value" از settings.json }
function JsonStr(const S, Key: String): String;
var
  P, I: Integer;
  T: String;
begin
  Result := '';
  P := Pos('"' + Key + '": "', S);
  if P = 0 then Exit;
  I := P + Length(Key) + 5;
  T := '';
  while (I <= Length(S)) and (S[I] <> '"') do
  begin
    if (S[I] = '\') and (I < Length(S)) then I := I + 1;
    T := T + S[I];
    I := I + 1;
  end;
  Result := T;
end;

function NewLabel(Parent: TWizardPage; const Caption: String; Top: Integer): TNewStaticText;
begin
  Result := TNewStaticText.Create(Parent);
  Result.Parent := Parent.Surface;
  Result.Caption := Caption;
  Result.AutoSize := False;
  Result.WordWrap := True;
  Result.Top := ScaleY(Top);
  Result.Left := 0;
  Result.Width := Parent.SurfaceWidth;
  Result.Height := ScaleY(17);
end;

function NewEditAt(Parent: TWizardPage; Top: Integer): TNewEdit;
begin
  Result := TNewEdit.Create(Parent);
  Result.Parent := Parent.Surface;
  Result.Top := ScaleY(Top);
  Result.Left := 0;
  Result.Width := Parent.SurfaceWidth;
end;

procedure UpdateAuthControls;
var
  En: Boolean;
begin
  En := not WinAuthChk.Checked;
  UserEdit.Enabled := En;
  PassEdit.Enabled := En;
  UserLbl.Enabled := En;
  PassLbl.Enabled := En;
end;

procedure WinAuthClick(Sender: TObject);
begin
  UpdateAuthControls;
  SqlTestedOk := False;
end;

{ مقدار داخل رشتهٔ اتصال OLE DB (با " دور آن) }
function CsVal(const S: String): String;
var
  T: String;
begin
  T := S;
  StringChangeEx(T, '"', '""', True);
  Result := '"' + T + '"';
end;

function SqlPassword: String;
begin
  Result := PassEdit.Text;
  { در به‌روزرسانی، رمز خالی یعنی همان رمز قبلی }
  if (Result = '') and (Trim(UserEdit.Text) = JsonStr(SettingsText, 'USER')) then
    Result := JsonStr(SettingsText, 'PASSWORD');
end;

function ConnString(const Provider: String): String;
begin
  Result := 'Provider=' + Provider + ';Data Source=' + CsVal(Trim(ServerEdit.Text)) +
            ';Initial Catalog=master;';
  if WinAuthChk.Checked then
    Result := Result + 'Integrated Security=SSPI;'
  else
    Result := Result + 'User ID=' + CsVal(Trim(UserEdit.Text)) + ';Password=' + CsVal(SqlPassword) + ';';
end;

{ اتصال آزمایشی به SQL Server؛ اول درایور قدیمی ویندوز، بعد درایور جدید }
function OpenSql(var Conn: Variant; var Err: String): Boolean;
var
  I: Integer;
  P: String;
begin
  Result := False;
  Err := '';
  for I := 0 to 2 do
  begin
    if Result then Break;
    case I of
      0: P := 'SQLOLEDB';
      1: P := 'MSOLEDBSQL';
      2: P := 'MSOLEDBSQL19';
    end;
    try
      Conn := CreateOleObject('ADODB.Connection');
      Conn.ConnectionTimeout := 8;
      Conn.Open(ConnString(P));
      Result := True;
    except
      if Err = '' then Err := GetExceptionMessage;
    end;
  end;
end;

function DbExists(Conn: Variant; const Name: String): Boolean;
var
  Rs: Variant;
  T: String;
begin
  T := Name;
  StringChangeEx(T, '''', '''''', True);
  Rs := Conn.Execute('SELECT 1 AS x WHERE DB_ID(N''' + T + ''') IS NOT NULL');
  Result := not Rs.EOF;
  Rs.Close;
end;

function TestSql(ShowOk: Boolean): Boolean;
var
  Conn: Variant;
  Err: String;
begin
  TestResult.Caption := 'در حال آزمایش اتصال...';
  WizardForm.Refresh;
  Result := OpenSql(Conn, Err);
  if Result then
  begin
    Conn.Close;
    TestResult.Font.Color := clGreen;
    TestResult.Caption := '✔ اتصال به SQL Server برقرار است.';
    if ShowOk then
      MsgBox('اتصال به SQL Server برقرار است.', mbInformation, MB_OK);
  end
  else
  begin
    TestResult.Font.Color := clRed;
    TestResult.Caption := '✖ اتصال برقرار نشد.';
    MsgBox('اتصال به SQL Server برقرار نشد.' + #13#10#13#10 +
           'نام سرور، نام کاربری و رمز را بررسی کنید و مطمئن شوید SQL Server روشن است.' + #13#10#13#10 +
           'پیام خطا:' + #13#10 + Err, mbError, MB_OK);
  end;
  SqlTestedOk := Result;
end;

procedure TestButtonClick(Sender: TObject);
begin
  TestSql(True);
end;

procedure InitializeWizard;
var
  Raw: AnsiString;
  V: String;
  Btn: TNewButton;
  Hint: TNewStaticText;
  Y: Integer;
begin
  SettingsText := '';
  if LoadStringFromFile(SettingsFile, Raw) then SettingsText := String(Raw);

  { ── صفحهٔ ۱: اتصال به SQL Server ── }
  SqlPage := CreateCustomPage(wpSelectDir, 'اتصال به SQL Server',
    'نام سرور و روش ورود به SQL Server را وارد کنید.');
  NewLabel(SqlPage, 'نام SQL Server (مثل SERWIN\RAD یا .\SQLEXPRESS):', 0);
  ServerEdit := NewEditAt(SqlPage, 18);
  WinAuthChk := TNewCheckBox.Create(SqlPage);
  WinAuthChk.Parent := SqlPage.Surface;
  WinAuthChk.Top := ScaleY(52);
  WinAuthChk.Width := SqlPage.SurfaceWidth;
  WinAuthChk.Caption := 'ورود با حساب ویندوز (بدون نام کاربری و رمز SQL)';
  WinAuthChk.OnClick := @WinAuthClick;
  UserLbl := NewLabel(SqlPage, 'نام کاربری SQL (مثلاً sa):', 80);
  UserEdit := NewEditAt(SqlPage, 98);
  PassLbl := NewLabel(SqlPage, 'رمز SQL (خالی = همان رمز قبلی):', 128);
  PassEdit := TPasswordEdit.Create(SqlPage);
  PassEdit.Parent := SqlPage.Surface;
  PassEdit.Top := ScaleY(146);
  PassEdit.Width := SqlPage.SurfaceWidth;
  Btn := TNewButton.Create(SqlPage);
  Btn.Parent := SqlPage.Surface;
  Btn.Top := ScaleY(182);
  Btn.Width := ScaleX(130);
  Btn.Height := ScaleY(26);
  Btn.Caption := 'آزمایش اتصال';
  Btn.OnClick := @TestButtonClick;
  TestResult := NewLabel(SqlPage, '', 188);
  TestResult.Left := Btn.Width + ScaleX(12);
  TestResult.Width := SqlPage.SurfaceWidth - Btn.Width - ScaleX(12);
  Hint := NewLabel(SqlPage, 'با «بعدی» هم اتصال خودکار آزمایش می‌شود.', 218);
  Hint.Font.Color := clGray;

  { ── صفحهٔ ۲: دیتابیس‌ها ── }
  DbPage := CreateInputQueryPage(SqlPage.ID, 'دیتابیس‌ها',
    'نام دیتابیس پیچا ویزیت و دیتابیس فروش را وارد کنید.',
    'دیتابیس پیچا ویزیت ویزیت‌ها و سفارش‌ها را نگه می‌دارد. اگر وجود نداشته باشد، ساخته می‌شود.' + #13#10 +
    'از دیتابیس فروش فقط مشتری‌ها، کالاها و عکس‌ها خوانده می‌شود.');
  DbPage.Add('نام دیتابیس پیچا ویزیت:', False);
  DbPage.Add('نام دیتابیس فروش (مشتری و کالا):', False);
  Y := DbPage.Edits[1].Top + DbPage.Edits[1].Height + ScaleY(16);
  CreateDbChk := TNewCheckBox.Create(DbPage);
  CreateDbChk.Parent := DbPage.Surface;
  CreateDbChk.Top := Y;
  CreateDbChk.Width := DbPage.SurfaceWidth;
  CreateDbChk.Caption := 'ساخت یا به‌روزرسانی خودکار دیتابیس و جدول‌های پیچا ویزیت (پیشنهادی)';
  CreateDbChk.Checked := True;

  { مقدارهای پیش‌فرض؛ در به‌روزرسانی مقدارهای فعلی }
  ServerEdit.Text := 'localhost';
  DbPage.Values[0] := 'tracking';
  DbPage.Values[1] := 'dejavuDB1';
  if SettingsText <> '' then
  begin
    V := JsonStr(SettingsText, 'SERVER_NAME'); if V <> '' then ServerEdit.Text := V else ServerEdit.Text := 'SERWIN\RAD';
    UserEdit.Text := JsonStr(SettingsText, 'USER');
    V := JsonStr(SettingsText, 'TRACKING_DB'); if V <> '' then DbPage.Values[0] := V;
    V := JsonStr(SettingsText, 'SALES_DB'); if V <> '' then DbPage.Values[1] := V;
    WinAuthChk.Checked := UserEdit.Text = '';
  end
  else
    UserEdit.Text := 'sa';
  UpdateAuthControls;
  SqlTestedOk := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Conn: Variant;
  Err, Missing: String;
begin
  Result := True;
  if CurPageID = SqlPage.ID then
  begin
    if Trim(ServerEdit.Text) = '' then
    begin
      MsgBox('نام SQL Server را وارد کنید.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if (not WinAuthChk.Checked) and (Trim(UserEdit.Text) = '') then
    begin
      MsgBox('نام کاربری SQL را وارد کنید یا «ورود با حساب ویندوز» را بزنید.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not TestSql(False) then
      Result := MsgBox('اتصال به SQL Server برقرار نشد.' + #13#10 +
                       'اگر مطمئن هستید تنظیمات درست است (مثلاً SQL Server الان خاموش است)، می‌توانید ادامه دهید و بعداً از پنل مدیریت درستش کنید.' + #13#10#13#10 +
                       'بدون اتصال ادامه می‌دهید؟', mbConfirmation, MB_YESNO) = IDYES;
  end
  else if CurPageID = DbPage.ID then
  begin
    if (Trim(DbPage.Values[0]) = '') or (Trim(DbPage.Values[1]) = '') then
    begin
      MsgBox('نام هر دو دیتابیس را وارد کنید.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not SqlTestedOk then Exit;
    if not OpenSql(Conn, Err) then Exit;
    Missing := '';
    try
      if not DbExists(Conn, Trim(DbPage.Values[1])) then
        Missing := Missing + '• دیتابیس فروش «' + Trim(DbPage.Values[1]) + '» پیدا نشد.' + #13#10;
      if (not CreateDbChk.Checked) and (not DbExists(Conn, Trim(DbPage.Values[0]))) then
        Missing := Missing + '• دیتابیس پیچا ویزیت «' + Trim(DbPage.Values[0]) + '» پیدا نشد و ساخت خودکار خاموش است.' + #13#10;
      Conn.Close;
    except
      Missing := '';
    end;
    if Missing <> '' then
      Result := MsgBox(Missing + #13#10 + 'نام دیتابیس را بررسی کنید.' + #13#10#13#10 + 'با همین نام‌ها ادامه می‌دهید؟',
                       mbConfirmation, MB_YESNO) = IDYES;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  Auth: String;
begin
  if WinAuthChk.Checked then Auth := 'حساب ویندوز' else Auth := 'کاربر SQL: ' + Trim(UserEdit.Text);
  Result := MemoDirInfo + NewLine + NewLine +
            'SQL Server:' + NewLine + Space + Trim(ServerEdit.Text) + ' (' + Auth + ')' + NewLine + NewLine +
            'دیتابیس‌ها:' + NewLine +
            Space + 'پیچا ویزیت: ' + Trim(DbPage.Values[0]) + NewLine +
            Space + 'فروش: ' + Trim(DbPage.Values[1]);
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
  { --name=value: مقداری که با «-» شروع شود هم مقدار حساب می‌شود }
  Result := '--configure --server=' + Q(Trim(ServerEdit.Text)) +
            ' --tracking=' + Q(Trim(DbPage.Values[0])) +
            ' --sales=' + Q(Trim(DbPage.Values[1]));
  if WinAuthChk.Checked then
    Result := Result + ' --user="" --password=""'
  else
  begin
    Result := Result + ' --user=' + Q(Trim(UserEdit.Text));
    if PassEdit.Text <> '' then
      Result := Result + ' --password=' + Q(PassEdit.Text);
  end;
end;

function WantSetupDb: Boolean;
begin
  Result := CreateDbChk.Checked;
end;

{ به‌روزرسانی: قبل از جایگزینی فایل‌ها سرویس و آیکون وضعیت بسته می‌شوند }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Svc: String;
begin
  Result := '';
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM PeechaVisitTray.exe /F', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Svc := ExpandConstant('{app}\PeechaVisitService.exe');
  if FileExists(Svc) then
  begin
    Exec(Svc, 'stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Exec(Svc, 'uninstall', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Sleep(2000);
  end;
end;
