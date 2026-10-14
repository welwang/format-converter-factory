param($th)
$cs=@"
using System;using System.Runtime.InteropServices;using System.Drawing;
public class Cap3{[DllImport("user32.dll")]static extern bool GetWindowRect(IntPtr h,out RECT r);[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();[DllImport("user32.dll")]static extern bool PrintWindow(IntPtr h,IntPtr dc,uint f);
public struct RECT{public int L,T,R,B;}
public static string Shot(IntPtr h,string p){SetProcessDPIAware();RECT r;GetWindowRect(h,out r);int w=r.R-r.L,ht=r.B-r.T;var b=new Bitmap(w,ht);using(var g=Graphics.FromImage(b)){var dc=g.GetHdc();PrintWindow(h,dc,2);g.ReleaseHdc(dc);}b.Save(p);return w+"x"+ht;}}
"@; Add-Type -TypeDefinition $cs -ReferencedAssemblies System.Drawing
$S='E:\轉檔工廠\_build\samples'
'{"theme":"'+$th+'","preset":"balanced","out_mode":"source","out_dir":"","hwaccel":true,"workers":2}' | Set-Content -Encoding utf8 E:\轉檔工廠\settings.json
$old=$env:PATH; $env:PATH='C:\Windows\System32;C:\Windows'
Start-Process E:\轉檔工廠\轉檔工廠.exe -ArgumentList "$S\v.mp4","$S\i.heic","$S\b.epub","$S\d.docx","$S\x.zip","$S\c.srt","$S\m.stl","$S\z.kfx"; $env:PATH=$old
Start-Sleep 20; $w=Get-Process | ? { $_.MainWindowTitle -eq '轉檔工廠' } | select -first 1; [Cap3]::SetForegroundWindow($w.MainWindowHandle)|Out-Null; Start-Sleep 1; [Cap3]::Shot($w.MainWindowHandle,"$env:USERPROFILE\zdgc_$th.png"); Stop-Process -Id $w.Id -Force; Start-Sleep 2
'{"theme":"light","preset":"balanced","out_mode":"source","out_dir":"","hwaccel":true,"workers":2}' | Set-Content -Encoding utf8 E:\轉檔工廠\settings.json