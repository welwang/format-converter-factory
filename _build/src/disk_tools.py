"""Reviewable Windows disk operations. Never repair or recover during startup."""
import os, re, json, time, uuid, ctypes, subprocess, shutil
import engine as E

HELP = dict(check='https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/chkdsk',
            recovery='https://support.microsoft.com/en-us/windows/experience/backup-recovery/windows-file-recovery')

def winfr_path():
    path = os.path.join(os.environ.get('LOCALAPPDATA',''), 'Microsoft', 'WindowsApps', 'winfr.exe')
    return path if os.path.isfile(path) else None

def inventory():
    if os.name != 'nt': return dict(drives=[], recovery=False)
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
    return dict(drives=drives,recovery=bool(winfr_path()))

def plan(mode, source, destination='', file_group='documents', recovery_mode='regular', devices=None):
    devices=devices or inventory()
    if mode not in ('check','repair','recovery'):raise ValueError('不支援的磁碟操作')
    if not isinstance(source,str) or not re.fullmatch(r'[A-Za-z]:',source):raise ValueError('請選擇來源磁碟')
    source=source.upper();by={d['drive']:d for d in devices['drives']}
    if source not in by:raise ValueError('來源不是可用的本機磁碟')
    system=os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'System32')
    warnings=[]
    if mode in ('check','repair'):
        command=[os.path.join(system,'chkdsk.exe'),source]
        if mode=='repair':
            command.append('/f');warnings.append('修復會修改檔案系統。請先備份或救援重要資料；使用中的磁碟可能需要在 Windows 視窗中選擇下次重新啟動時執行。')
        else:warnings.append('此檢查不帶修復參數，不修正錯誤；使用中的磁碟可能出現需再次確認的錯誤報告。')
        description=f'{"檢查" if mode=="check" else "修復"} {source} 的檔案系統'
        available=True
    else:
        if not isinstance(destination,str) or not re.fullmatch(r'[A-Za-z]:',destination):raise ValueError('請選擇救援資料的目的磁碟')
        destination=destination.upper()
        if source==destination:raise ValueError('來源與目的磁碟必須不同，避免覆寫待救援資料')
        if destination not in by:raise ValueError('目的不是可用的本機磁碟')
        sn,dn=by[source].get('disk_number'),by[destination].get('disk_number')
        if sn is not None and dn is not None and sn==dn:raise ValueError('請使用另一顆實體硬碟或 USB 裝置作為救援目的地')
        if sn is None or dn is None:warnings.append('無法確認實體磁碟編號，請自行確認目的地是另一顆磁碟或 USB 裝置。')
        if by[destination]['free']<1048576:raise ValueError('目的磁碟空間不足')
        if recovery_mode not in ('regular','extensive'):raise ValueError('不支援的救援模式')
        if recovery_mode=='regular' and by[source]['filesystem']!='NTFS':raise ValueError('一般模式只適用 NTFS；這個磁碟請選深入掃描')
        groups=dict(documents=['*.pdf','*.docx','*.xlsx','*.pptx','*.txt'],photos=['*.jpg','*.jpeg','*.png','*.heic'],video=['*.mp4','*.mov','*.mkv'],all=['*'])
        if file_group not in groups:raise ValueError('不支援的檔案類型')
        exe=winfr_path();available=bool(exe)
        command=[exe or 'winfr.exe',source,destination,'/'+recovery_mode]
        for pattern in groups[file_group]:command+=['/n',pattern]
        warnings.append('停止在來源磁碟儲存新資料；結果寫到目的磁碟。Windows 工具會再次詢問是否開始，SSD 資料已覆寫時可能無法恢復。')
        if not available:warnings.append('尚未安裝 Microsoft Windows File Recovery，請先使用官方說明中的 Microsoft Store 連結安裝，再重新預覽。')
        description=f'從 {source} 救援到 {destination}，使用{"一般" if recovery_mode=="regular" else "深入"}模式'
    return dict(token=uuid.uuid4().hex,created=time.time(),mode=mode,source=source,destination=destination,file_group=file_group,recovery_mode=recovery_mode,
                description=description,warnings=warnings,available=available,command=command)

def launch(preview, token, confirmed):
    if not confirmed or token!=preview.get('token') or time.time()-preview.get('created',0)>600:raise ValueError('請重新預覽並確認磁碟操作')
    current=plan(preview['mode'],preview['source'],preview['destination'],preview['file_group'],preview['recovery_mode'])
    if not current['available']:raise ValueError('請先安裝官方救援工具，再重新預覽')
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
