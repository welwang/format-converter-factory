"""Validated local file actions shared by the queue and downloader."""
import os, json, subprocess

def normalized(path):
    if not isinstance(path,str) or not path.strip():raise ValueError('沒有可開啟的檔案路徑')
    value=path.strip().lstrip('\ufeff')
    if value.startswith('"'):
        try:value=json.loads(value)
        except (ValueError,TypeError):value=value.strip('"')
    if not isinstance(value,str) or '\x00' in value or value in ('NA','None','null'):raise ValueError('下載元件沒有回報有效檔案路徑')
    return os.path.normpath(os.path.abspath(value))

def completed_path(line,folder):
    if not line.startswith('ZDGCFILE '):return None
    raw=line[len('ZDGCFILE '):].strip()
    try:
        value=json.loads(raw) if raw.startswith('"') else raw
        if not isinstance(value,str) or value in ('NA','None','null'):return None
        if not os.path.isabs(value):value=os.path.join(folder,value)
        path=normalized(value)
        return path if os.path.isfile(path) and os.path.getsize(path)>0 else None
    except (ValueError,OSError):return None

def existing(path):
    path=normalized(path)
    if not os.path.exists(path):raise FileNotFoundError('找不到成品，檔案可能已移動或刪除：'+path)
    return path

def reveal(path):
    path=existing(path)
    if os.path.isdir(path):os.startfile(path)
    else:
        explorer=os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'explorer.exe')
        subprocess.Popen([explorer,'/select,'+path])
    return True

def open_file(path):
    path=existing(path)
    try:os.startfile(path)
    except OSError:
        reveal(path)
        raise OSError('尚未設定此格式的預設開啟程式，已在資料夾中顯示檔案')
    return True
