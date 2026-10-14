"""Bounded hardware checks and preview-first cleanup of known temporary files."""
import os, sys, time, json, tempfile, hashlib, shutil, stat, uuid, subprocess
from pathlib import Path
import engine as E

CLEANUP = [
    dict(id='app_temp', name='四維八德舊暫存', desc='7 天以上的處理暫存；保留設定、模型與成品', default=True),
    dict(id='download_parts', name='未完成的模型下載', desc='1 天以上的下載片段；保留已完成模型', default=True),
    dict(id='logs', name='舊診斷記錄', desc='7 天以上的記錄檔', default=False),
    dict(id='user_temp', name='使用者暫存', desc='暫存資料夾內 7 天以上的散落檔案；不包含子資料夾', default=False),
]

def hardware_info():
    info = E.platform_info()
    cpu = ''
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                cpu = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
        except OSError: pass
    info['cpu'] = cpu or '未取得處理器名稱'
    info['gpu_encoders'] = E.detect_hw()
    info['disks'] = []
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.name == 'nt' else ['/']
    for letter in letters:
        path = letter + ':\\' if os.name == 'nt' else letter
        if os.name == 'nt':
            import ctypes
            if ctypes.windll.kernel32.GetDriveTypeW(path) not in (2,3): continue
        try:
            du = shutil.disk_usage(path)
            info['disks'].append(dict(path=path, total=du.total, free=du.free))
        except OSError: pass
    return info

def run_tests(eng, job):
    folder = job.opt.get('out_dir') or os.path.join(E.data_dir(), 'hardware-tests')
    os.makedirs(folder, exist_ok=True)
    out = E.unique_path(os.path.join(folder, '硬體短測_' + time.strftime('%Y%m%d_%H%M%S') + '.json'))
    result = dict(info=hardware_info(), tests=[], note='短時間功能與效能測試；不判定完整硬碟健康、溫度或整部記憶體。磁碟讀取可能受到系統快取影響。')
    def check_cancel():
        if job.cancelled: raise InterruptedError
    def test(name, action):
        check_cancel(); job.msg = name
        try: result['tests'].append(dict(name=name, state='done', **action()))
        except InterruptedError: raise
        except Exception as ex: result['tests'].append(dict(name=name, state='error', detail=str(ex)[:200])); job.warnings.append(name + '未通過')
        job.progress = len(result['tests']) / 4
    def cpu():
        block = b'ZDGC' * 8192; count=0; start=time.perf_counter()
        while time.perf_counter()-start < 1.2:
            hashlib.sha256(block).digest(); count+=1
            if count % 100 == 0: check_cancel()
        return dict(mbps=round(count*len(block)/(time.perf_counter()-start)/1048576,1), detail='單執行緒 SHA-256 吞吐量')
    def memory():
        size=16*1048576; a=bytearray(b'\x5a')*size; b=bytearray(size);start=time.perf_counter();count=0
        while time.perf_counter()-start < .6:
            b[:]=a;count+=1;check_cancel()
        elapsed=time.perf_counter()-start
        if b != a: raise RuntimeError('測試區域資料不一致')
        return dict(mbps=round(count*size/elapsed/1048576,1),detail='16 MB 測試區域複製與一致性檢查')
    def disk():
        fd,p=tempfile.mkstemp(prefix='zdgc_disk_',suffix='.tmp',dir=folder)
        try:
            block=b'\xa5'*1048576; start=time.perf_counter()
            with os.fdopen(fd,'wb') as fh:
                for _ in range(16):check_cancel();fh.write(block)
                fh.flush();os.fsync(fh.fileno())
            write=time.perf_counter()-start;start=time.perf_counter()
            with open(p,'rb') as fh:
                for _ in range(16):
                    check_cancel()
                    if fh.read(1048576)!=block:raise RuntimeError('磁碟測試資料不一致')
            read=time.perf_counter()-start
            return dict(write_mbps=round(16/max(write,.001),1),read_mbps=round(16/max(read,.001),1),detail='16 MB 順序讀寫 · ' + os.path.splitdrive(folder)[0])
        finally:
            try:os.remove(p)
            except OSError:pass
    def gpu():
        hw = E.detect_hw(); encoder = hw[0] if hw else 'libx264'; start=time.perf_counter()
        eng._proc(job,[E.FFMPEG,'-hide_banner','-nostdin','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=1','-c:v',encoder,'-threads','1','-f','null','-'],'GPU／影音編碼短測')
        return dict(seconds=round(time.perf_counter()-start,3),encoder=encoder,detail='GPU 編碼可用性' if hw else '未偵測到可用硬體編碼，CPU 編碼通過')
    try:
        test('CPU 短測',cpu);test('記憶體短測',memory);test('磁碟讀寫短測',disk);test('GPU／影音編碼短測',gpu)
    finally:
        result['cancelled']=job.cancelled
        with open(out,'w',encoding='utf-8') as fh:json.dump(result,fh,ensure_ascii=False,indent=2)
        txt=os.path.splitext(out)[0]+'.txt'
        with open(txt,'w',encoding='utf-8-sig') as fh:
            fh.write('四維八德硬體短測\n'+result['note']+'\n')
            for r in result['tests']:fh.write(r['name']+'：'+json.dumps(r,ensure_ascii=False)+'\n')
        job.output=out;job.keep_output=True;job.encoder='電腦硬體短測'

def _safe_root(path, root):
    try:
        return os.path.commonpath([os.path.normcase(os.path.realpath(path)),os.path.normcase(os.path.realpath(root))])==os.path.normcase(os.path.realpath(root)) and os.path.abspath(path)!=os.path.abspath(root)
    except (ValueError,OSError):return False

def _plain_file(path, root):
    if not _safe_root(path,root):return None
    try:
        p=Path(path)
        # Every ancestor inside the selected root must be a plain directory, never a junction.
        cur=p
        while str(cur)!=str(Path(root)):
            st=os.lstat(cur)
            if stat.S_ISLNK(st.st_mode) or getattr(st,'st_file_attributes',0)&0x400:return None
            if cur.parent==cur:return None
            cur=cur.parent
        st=os.stat(path)
        return st if stat.S_ISREG(st.st_mode) else None
    except OSError:return None

def scan_cleanup(categories):
    known={c['id'] for c in CLEANUP}
    if not set(categories).issubset(known):raise ValueError('不支援的清理項目')
    temp=os.path.abspath(tempfile.gettempdir());data=os.path.abspath(E.data_dir());now=time.time();items=[]
    def add(path,root,category,age):
        st=_plain_file(path,root)
        if st and now-st.st_mtime>=age and len(items)<10000:items.append(dict(path=str(path),root=root,category=category,size=st.st_size,mtime=st.st_mtime))
    for category in categories:
        if category=='app_temp':
            try:dirs=list(Path(temp).iterdir())
            except OSError:dirs=[]
            for d in dirs:
                if not d.name.startswith('zdgc_') or not d.is_dir() or d.is_symlink():continue
                if getattr(os.lstat(d),'st_file_attributes',0)&0x400:continue
                for r,ds,fs in os.walk(d,followlinks=False):
                    ds[:]=[n for n in ds if not getattr(os.lstat(os.path.join(r,n)),'st_file_attributes',0)&0x400]
                    for f in fs:add(os.path.join(r,f),temp,category,7*86400)
        elif category=='download_parts':
            for sub in ('models','tools'):
                folder=Path(data)/sub
                if folder.is_dir():
                    for f in folder.glob('*.part'):add(str(f),data,category,86400)
        elif category=='logs':
            folder=Path(data)/'logs'
            if folder.is_dir():
                for f in folder.iterdir():
                    if f.name.startswith('zdgc.log'):add(str(f),data,category,7*86400)
        elif category=='user_temp':
            try:files=list(Path(temp).iterdir())
            except OSError:files=[]
            for f in files:add(str(f),temp,category,7*86400)
    unique={os.path.normcase(i['path']):i for i in items}
    return dict(token=uuid.uuid4().hex,created=now,items=list(unique.values()))

def cleanup_preview(plan):
    return dict(token=plan['token'],count=len(plan['items']),bytes=sum(i['size'] for i in plan['items']),categories=[dict(id=c['id'],name=c['name'],count=sum(i['category']==c['id'] for i in plan['items']),bytes=sum(i['size'] for i in plan['items'] if i['category']==c['id'])) for c in CLEANUP],examples=[os.path.basename(i['path']) for i in plan['items'][:20]])

def execute_cleanup(plan, token):
    if token!=plan.get('token') or time.time()-plan.get('created',0)>600:raise ValueError('清理預覽已過期，請重新掃描')
    freed=0;removed=0;skipped=0
    for i in plan['items']:
        st=_plain_file(i['path'],i['root'])
        if not st or st.st_size!=i['size'] or st.st_mtime!=i['mtime']:skipped+=1;continue
        try:os.remove(i['path']);freed+=i['size'];removed+=1
        except OSError:skipped+=1
    plan['created']=0
    return dict(removed=removed,skipped=skipped,bytes=freed)
