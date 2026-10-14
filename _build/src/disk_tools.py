"""Reviewable Windows disk operations. Never repair or recover during startup."""
import os, re, json, time, uuid, ctypes, subprocess, shutil
import engine as E

HELP = dict(check='https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/chkdsk')

def inventory():
    if os.name != 'nt': return dict(drives=[])
    numbers={}
    ps=os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'System32','WindowsPowerShell','v1.0','powershell.exe')
    try:
        r=E.run([ps,'-NoProfile','-NonInteractive','-Command',"Get-Partition -ErrorAction Stop | Where-Object DriveLetter | Select-Object DriveLetter,DiskNumber | ConvertTo-Json -Compress"],timeout=12)
        values=json.loads(r.stdout)
        if isinstance(values,dict):values=[values]
        numbers={str(v['DriveLetter']).upper():int(v['DiskNumber']) for v in values}
    except Exception: pass
    drives=[]
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        root=letter+':\\'
        if ctypes.windll.kernel32.GetDriveTypeW(root) not in (2,3):continue
        fs=ctypes.create_unicode_buffer(64)
        try: ctypes.windll.kernel32.GetVolumeInformationW(root,None,0,None,None,None,fs,64)
        except Exception: pass
        try:du=shutil.disk_usage(root)
        except OSError:continue
        drives.append(dict(drive=letter+':',filesystem=fs.value or '未知',disk_number=numbers.get(letter),free=du.free))
    return dict(drives=drives)

def plan(mode, source, destination='', file_group='documents', recovery_mode='regular', devices=None):
    devices=devices or inventory()
    # Only Windows' own chkdsk: file recovery needed a Microsoft Store app that cannot ship with 四維八德.
    if mode not in ('check','repair'):raise ValueError('不支援的磁碟操作')
    if not isinstance(source,str) or not re.fullmatch(r'[A-Za-z]:',source):raise ValueError('請選擇磁碟')
    source=source.upper();by={d['drive']:d for d in devices['drives']}
    if source not in by:raise ValueError('不是可用的本機磁碟')
    system=os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'System32')
    warnings=[]
    command=[os.path.join(system,'chkdsk.exe'),source]
    if mode=='repair':
        command.append('/f');warnings.append('修復會修改檔案系統。請先備份重要資料；使用中的磁碟可能需要在 Windows 視窗中選擇下次重新啟動時執行。')
    else:warnings.append('此檢查不帶修復參數，不修正錯誤；使用中的磁碟可能出現需再次確認的錯誤報告。')
    description=f'{"檢查" if mode=="check" else "修復"} {source} 的檔案系統'
    available=True
    return dict(token=uuid.uuid4().hex,created=time.time(),mode=mode,source=source,destination=destination,file_group=file_group,recovery_mode=recovery_mode,
                description=description,warnings=warnings,available=available,command=command)

def launch(preview, token, confirmed):
    if not confirmed or token!=preview.get('token') or time.time()-preview.get('created',0)>600:raise ValueError('請重新預覽並確認磁碟操作')
    current=plan(preview['mode'],preview['source'],preview['destination'],preview['file_group'],preview['recovery_mode'])
    # Values reaching the Windows command shell are fixed operation names, drive letters and predefined patterns.
    for arg in current['command']:
        if any(c in arg for c in '&|<>^%!"\r\n'):raise ValueError('磁碟參數不合法')
    cmd=os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'System32','cmd.exe')
    params='/k '+subprocess.list2cmdline(current['command'])
    shell=ctypes.windll.shell32.ShellExecuteW
    shell.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_int]
    shell.restype=ctypes.c_void_p
    result=shell(None,'runas',cmd,params,None,1)
    if not result or result<=32:raise RuntimeError('未啟動磁碟工具；可能取消了系統管理員權限要求')
    preview['created']=0
    return '已開啟 Windows 磁碟工具視窗；操作是否完成與結果請查看該視窗。'
