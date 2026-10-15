$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$source=Get-Content -LiteralPath (Join-Path $root 'shell\main.cpp') -Raw -Encoding UTF8
$begin=$source.IndexOf('static BOOL trusted_ui_uri(')
$end=$source.IndexOf('HRESULT STDMETHODCALLTYPE MsgHandler::Invoke(', $begin)
if($begin -lt 0 -or $end -lt 0){throw '找不到來源函式'}
$function=$source.Substring($begin,$end-$begin)
$prefix=@'
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <shlwapi.h>
#include <stdio.h>
static wchar_t g_pagePath[MAX_PATH];
'@
$tests=@'
static void uri(const wchar_t *path,wchar_t *result) {
 char bytes[MAX_PATH*3];WideCharToMultiByte(CP_UTF8,0,path,-1,bytes,sizeof bytes,NULL,NULL);
 wcscpy(result,L"file:///");int n=(int)wcslen(result);
 for(int i=0;bytes[i];i++) {unsigned char c=(unsigned char)bytes[i];if(c=='\\')c='/';
  if((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='/'||c==':'||c=='.'||c=='-'||c=='_')result[n++]=c;
  else {swprintf(result+n,4,L"%%%02X",c);n+=3;}}
 result[n]=0;
}
int main(void) {
 const wchar_t *paths[]={L"C:\\App\\_internal\\ui\\index.html",L"C:\\四維八德\\_internal\\ui\\index.html",L"C:\\中文 空白\\_internal\\ui\\index.html",L"C:\\資料%20 #繁體\\_internal\\ui\\index.html",L"C:\\使用者é日本語\\_internal\\ui\\index.html"};
 int good=0;wchar_t url[MAX_PATH*9];
 for(int i=0;i<5;i++){wcscpy(g_pagePath,paths[i]);uri(g_pagePath,url);if(trusted_ui_uri(url))good++;else printf("FAIL path %d\n",i);}
 wcscpy(g_pagePath,paths[0]);
 if(!trusted_ui_uri(L"https://example.com/_internal/ui/index.html"))good++;
 if(!trusted_ui_uri(L"file:///C:/App/_internal/ui/other.html"))good++;
 if(!trusted_ui_uri(L"file://evil-server/C:/App/_internal/ui/index.html"))good++;
 printf("PASSED %d / 8\n",good);return good==8?0:1;
}
'@
$output=Join-Path $root 'shell\out'
[IO.File]::WriteAllText((Join-Path $output 'test-uri.c'),$prefix+"`n"+$function+"`n"+$tests,[Text.UTF8Encoding]::new($false))
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vs=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$batch=Join-Path $output 'compile-uri.cmd'
$lines=@('@echo off','chcp 65001 >nul',('call "'+$vs+'\VC\Auxiliary\Build\vcvars64.bat" >nul'),('cd /d "'+$output+'"'),'cl /nologo /utf-8 /MT test-uri.c /link shlwapi.lib','exit /b %errorlevel%')
[IO.File]::WriteAllText($batch,($lines -join "`r`n"),[Text.UTF8Encoding]::new($false))
& cmd.exe /d /c $batch
if($LASTEXITCODE -ne 0){throw 'URI 測試編譯失敗'}
& (Join-Path $output 'test-uri.exe')
if($LASTEXITCODE -ne 0){throw 'URI 測試失敗'}
