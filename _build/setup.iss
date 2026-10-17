#define AppName "四維八德"
#define AppVer "1.0"
#ifndef ReleaseRoot
#define ReleaseRoot AddBackslash(SourcePath) + ".."
#endif
[Setup]
AppId={{7B1E6C2A-9D41-4E7B-A3F0-ZDGC20261013}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}（開源離線版）
AppPublisher=Wel Wang
DefaultDirName={localappdata}\Programs\SiWeiBaDe
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
; 已有安裝時走「更新」：沿用原目錄、不顯示目錄頁、偵測執行中的程式。
DisableDirPage=auto
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no
AppMutex=Local\SiWeiBaDe.SingleInstance
OutputDir={#ReleaseRoot}\輸出
OutputBaseFilename=四維八德_{#AppVer}_離線安裝程式
Compression=lzma2/max
SolidCompression=yes
; 64 MB dictionary limits installer extraction memory use.
LZMADictionarySize=65536
LZMANumFastBytes=273
SetupIconFile={#AddBackslash(SourcePath)}logo.ico
LZMANumBlockThreads=4
WizardStyle=modern
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\四維八德.exe
LicenseFile={#ReleaseRoot}\使用授權條款.md
[Languages]
Name: "cht"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他捷徑："
Name: "sendto"; Description: "加入檔案總管右鍵「傳送到」"; GroupDescription: "其他捷徑："
Name: "ctxmenu"; Description: "在檔案與資料夾的右鍵選單加入「用四維八德開啟」"; GroupDescription: "其他捷徑："
[Types]
Name: "full"; Description: "完整功能"
Name: "compact"; Description: "完整離線功能"
Name: "custom"; Description: "自行選擇"; Flags: iscustom
[Components]
Name: "core"; Description: "主程式、影音、圖片與 PDF"; Types: full compact custom; Flags: fixed
Name: "office"; Description: "離線 Office 文件、簡報與 PDF 轉檔"; Types: full compact custom; Flags: fixed
Name: "ebook"; Description: "離線電子書轉檔"; Types: full compact custom; Flags: fixed
[Files]
Source: "{#ReleaseRoot}\四維八德.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseRoot}\swbd-core.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseRoot}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseRoot}\tools\*"; DestDir: "{app}\tools"; Excludes: "libreoffice\*,calibre\*,*.part,*.tmp,ghostscript\vcredist_x64.exe,ghostscript\$PLUGINSDIR\*"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: core
Source: "{#ReleaseRoot}\tools\libreoffice\*"; DestDir: "{app}\tools\libreoffice"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: office
Source: "{#ReleaseRoot}\tools\calibre\*"; DestDir: "{app}\tools\calibre"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: ebook
Source: "{#ReleaseRoot}\README.md"; DestDir: "{app}"
Source: "{#ReleaseRoot}\CHANGELOG.md"; DestDir: "{app}"
Source: "{#ReleaseRoot}\授權說明.md"; DestDir: "{app}"
Source: "{#ReleaseRoot}\使用授權條款.md"; DestDir: "{app}"
Source: "{#ReleaseRoot}\LICENSE"; DestDir: "{app}"
Source: "{#ReleaseRoot}\COPYING.AGPL-3.0"; DestDir: "{app}"
Source: "{#ReleaseRoot}\開源與散布說明.md"; DestDir: "{app}"
Source: "{#ReleaseRoot}\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseRoot}\source\*"; DestDir: "{app}\source"; Excludes: "upstream\*"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\四維八德.exe"
Name: "{group}\解除安裝 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\四維八德.exe"; Tasks: desktopicon
Name: "{usersendto}\{#AppName}"; Filename: "{app}\四維八德.exe"; Tasks: sendto
[Registry]
Root: HKCU; Subkey: "Software\Classes\*\shell\ZhuanDangGongChang"; ValueType: string; ValueName: ""; ValueData: "用四維八德開啟"; Flags: uninsdeletekey; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\ZhuanDangGongChang"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\四維八德.exe"; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\ZhuanDangGongChang\command"; ValueType: string; ValueName: ""; ValueData: """{app}\四維八德.exe"" ""%1"""; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\ZhuanDangGongChang"; ValueType: string; ValueName: ""; ValueData: "用四維八德開啟"; Flags: uninsdeletekey; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\ZhuanDangGongChang"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\四維八德.exe"; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\ZhuanDangGongChang\command"; ValueType: string; ValueName: ""; ValueData: """{app}\四維八德.exe"" ""%1"""; Tasks: ctxmenu
[Run]
Filename: "{app}\tools\WebView2-offline-x64.exe"; Parameters: "/silent /install"; StatusMsg: "正在安裝視窗元件 WebView2…"; Check: NeedWebView2; Flags: waituntilterminated skipifdoesntexist
Filename: "{app}\四維八德.exe"; Description: "立即開啟四維八德"; Flags: nowait postinstall skipifsilent
[InstallDelete]
; 舊版安裝遺留的說明與測試報告（升級安裝時清掉）
Type: files; Name: "{app}\使用說明.md"
Type: files; Name: "{app}\版本更新.md"
Type: files; Name: "{app}\PDF功能清單.md"
Type: files; Name: "{app}\TEST_RESULTS.md"
Type: files; Name: "{app}\測試報告.html"
Type: files; Name: "{app}\工程技術說明書.md"
Type: files; Name: "{app}\assets\logo-sm.png"
Type: files; Name: "{app}\_internal\ui\logo-sm.png"
[UninstallDelete]
Type: files; Name: "{app}\settings.json"
Type: files; Name: "{app}\hw_cache.json"
Type: files; Name: "{app}\ffmpeg_caps.json"
Type: files; Name: "{app}\window.ini"
Type: filesandordirs; Name: "{app}\hardware-tests"
Type: filesandordirs; Name: "{app}\掃描原圖"
Type: filesandordirs; Name: "{app}\HTML原稿"
Type: files; Name: "{app}\.zdgc_write_test"
Type: files; Name: "{app}\watch_state.json"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\settings.json.tmp"
Type: files; Name: "{app}\tools\deno.exe"
[Code]
function NeedWebView2: Boolean;
var v: String;
begin
  Result := not ((RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v) and (v <> '') and (v <> '0.0.0.0'))
    or (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v) and (v <> '') and (v <> '0.0.0.0')));
end;
{ ── 更新既有安裝時保留使用者資料 ─────────────────────────────────────────
  Inno 在升級時會先執行舊版的解除安裝程式，而舊版的 [UninstallDelete] 會刪除
  settings.json、window.ini、watch_state.json、hw_cache*.json、ffmpeg_caps.json、
  logs\、hardware-tests\、models\、掃描原圖\、HTML原稿\。
  若不先備份，使用者一更新就會失去設定、已存流程、健康檢查報告與輸出成品。
  這裡在 PrepareToInstall（舊版解除安裝之前）備份到暫存目錄，安裝完成後還原。 }
var
  UpgradeBackup: String;
  UpgradeNeeded: Boolean;

function HasPreviousInstall: Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\unins000.exe')) or
            DirExists(ExpandConstant('{app}\_internal'));
end;

procedure CopyTree(const Src, Dst: String);
var
  FindRec: TFindRec;
  Sub: String;
begin
  if not DirExists(Src) then Exit;
  ForceDirectories(Dst);
  if FindFirst(Src + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          Sub := Src + '\' + FindRec.Name;
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            CopyTree(Sub, Dst + '\' + FindRec.Name)
          else
            CopyFile(Sub, Dst + '\' + FindRec.Name, False);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure CopyUserData(const FromDir, ToDir: String);
begin
  ForceDirectories(ToDir);
  if FileExists(FromDir + '\settings.json') then CopyFile(FromDir + '\settings.json', ToDir + '\settings.json', False);
  if FileExists(FromDir + '\window.ini') then CopyFile(FromDir + '\window.ini', ToDir + '\window.ini', False);
  if FileExists(FromDir + '\watch_state.json') then CopyFile(FromDir + '\watch_state.json', ToDir + '\watch_state.json', False);
  if FileExists(FromDir + '\hw_cache.json') then CopyFile(FromDir + '\hw_cache.json', ToDir + '\hw_cache.json', False);
  if FileExists(FromDir + '\hw_cache_c.json') then CopyFile(FromDir + '\hw_cache_c.json', ToDir + '\hw_cache_c.json', False);
  if FileExists(FromDir + '\ffmpeg_caps.json') then CopyFile(FromDir + '\ffmpeg_caps.json', ToDir + '\ffmpeg_caps.json', False);
  CopyTree(FromDir + '\logs', ToDir + '\logs');
  CopyTree(FromDir + '\hardware-tests', ToDir + '\hardware-tests');
  CopyTree(FromDir + '\models', ToDir + '\models');
  CopyTree(FromDir + '\掃描原圖', ToDir + '\掃描原圖');
  CopyTree(FromDir + '\HTML原稿', ToDir + '\HTML原稿');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  UpgradeNeeded := HasPreviousInstall;
  if not UpgradeNeeded then Exit;
  UpgradeBackup := ExpandConstant('{tmp}\upgrade-backup');
  CopyUserData(ExpandConstant('{app}'), UpgradeBackup);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and UpgradeNeeded then
    CopyUserData(UpgradeBackup, ExpandConstant('{app}'));
end;
