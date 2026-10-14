#define AppName "四維八德"
#define AppVer "2.1.0"
#ifndef ReleaseRoot
#define ReleaseRoot AddBackslash(SourcePath) + ".."
#endif
[Setup]
AppId={{7B1E6C2A-9D41-4E7B-A3F0-ZDGC20261013}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}（試用版，免費、沒有期限）
AppPublisher=Wel Wang
DefaultDirName={localappdata}\Programs\SiWeiBaDe
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
OutputDir={#ReleaseRoot}\輸出
OutputBaseFilename=四維八德安裝程式
Compression=lzma2/ultra64
SolidCompression=yes
; 256 MB dictionary: identical DLLs shipped by LibreOffice / Calibre / FFmpeg (ICU, OpenSSL, Python...) get stored once
LZMADictionarySize=262144
LZMANumFastBytes=273
LZMAUseSeparateProcess=yes
SetupIconFile={#ReleaseRoot}\_build\logo.ico
LZMANumBlockThreads=8
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
Name: "compact"; Description: "影音、圖片與 PDF（較省磁碟空間）"
Name: "custom"; Description: "自行選擇"; Flags: iscustom
[Components]
Name: "core"; Description: "主程式、影音、圖片與 PDF"; Types: full compact custom; Flags: fixed
Name: "office"; Description: "Office 文件與簡報轉檔（約 519 MB）"; Types: full
Name: "ebook"; Description: "電子書轉檔（約 573 MB）"; Types: full
[Files]
Source: "{#ReleaseRoot}\四維八德.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseRoot}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseRoot}\tools\*"; DestDir: "{app}\tools"; Excludes: "libreoffice\*,calibre\*"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: core
Source: "{#ReleaseRoot}\tools\libreoffice\*"; DestDir: "{app}\tools\libreoffice"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: office
Source: "{#ReleaseRoot}\tools\calibre\*"; DestDir: "{app}\tools\calibre"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: ebook
Source: "{#ReleaseRoot}\使用說明.md"; DestDir: "{app}"
Source: "{#ReleaseRoot}\授權說明.md"; DestDir: "{app}"
Source: "{#ReleaseRoot}\使用授權條款.md"; DestDir: "{app}"
Source: "{#ReleaseRoot}\LICENSE"; DestDir: "{app}"
Source: "{#ReleaseRoot}\版本更新.md"; DestDir: "{app}"
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
Filename: "{app}\tools\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "正在安裝視窗元件 WebView2…"; Check: NeedWebView2; Flags: waituntilterminated skipifdoesntexist
Filename: "{app}\四維八德.exe"; Description: "立即開啟四維八德"; Flags: nowait postinstall skipifsilent
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
