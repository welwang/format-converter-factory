#define AppName "轉檔工廠"
#define AppVer "2.0.0"
[Setup]
AppId={{7B1E6C2A-9D41-4E7B-A3F0-ZDGC20261013}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}（試用版，免費、沒有期限）
AppPublisher=Wel Wang
DefaultDirName={localappdata}\Programs\ZhuanDangGongChang
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
OutputDir=E:\轉檔工廠\輸出
OutputBaseFilename=轉檔工廠安裝程式
Compression=lzma2/ultra64
SolidCompression=yes
; 256 MB dictionary: identical DLLs shipped by LibreOffice / Calibre / FFmpeg (ICU, OpenSSL, Python...) get stored once
LZMADictionarySize=262144
LZMANumFastBytes=273
LZMAUseSeparateProcess=yes
SetupIconFile=E:\轉檔工廠\_build\logo.ico
LZMANumBlockThreads=8
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\轉檔工廠.exe
LicenseFile=E:\轉檔工廠\授權說明.md
[Languages]
Name: "cht"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他捷徑："
Name: "sendto"; Description: "加入檔案總管右鍵「傳送到」"; GroupDescription: "其他捷徑："
Name: "ctxmenu"; Description: "在檔案與資料夾的右鍵選單加入「用轉檔工廠開啟」"; GroupDescription: "其他捷徑："
[Files]
Source: "E:\轉檔工廠\轉檔工廠.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "E:\轉檔工廠\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "E:\轉檔工廠\tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "E:\轉檔工廠\使用說明.md"; DestDir: "{app}"
Source: "E:\轉檔工廠\授權說明.md"; DestDir: "{app}"
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\轉檔工廠.exe"
Name: "{group}\解除安裝 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\轉檔工廠.exe"; Tasks: desktopicon
Name: "{usersendto}\{#AppName}"; Filename: "{app}\轉檔工廠.exe"; Tasks: sendto
[Registry]
Root: HKCU; Subkey: "Software\Classes\*\shell\ZhuanDangGongChang"; ValueType: string; ValueName: ""; ValueData: "用轉檔工廠開啟"; Flags: uninsdeletekey; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\ZhuanDangGongChang"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\轉檔工廠.exe"; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\ZhuanDangGongChang\command"; ValueType: string; ValueName: ""; ValueData: """{app}\轉檔工廠.exe"" ""%1"""; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\ZhuanDangGongChang"; ValueType: string; ValueName: ""; ValueData: "用轉檔工廠開啟"; Flags: uninsdeletekey; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\ZhuanDangGongChang"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\轉檔工廠.exe"; Tasks: ctxmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\ZhuanDangGongChang\command"; ValueType: string; ValueName: ""; ValueData: """{app}\轉檔工廠.exe"" ""%1"""; Tasks: ctxmenu
[Run]
Filename: "{app}\tools\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "正在安裝視窗元件 WebView2…"; Check: NeedWebView2; Flags: waituntilterminated skipifdoesntexist
Filename: "{app}\轉檔工廠.exe"; Description: "立即開啟轉檔工廠"; Flags: nowait postinstall skipifsilent
[UninstallDelete]
Type: files; Name: "{app}\settings.json"
Type: files; Name: "{app}\hw_cache.json"
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
