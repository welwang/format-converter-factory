"""四維八德 conversion engine (no UI)."""
import os, sys, re, json, time, shutil, subprocess, threading, tempfile, uuid
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

PDFIUM_LOCK = threading.RLock()
def pdfium_serial(fn):
    @wraps(fn)
    def guarded(*args, **kwargs):
        with PDFIUM_LOCK:
            return fn(*args, **kwargs)
    return guarded

def public_options(opt):
    return {k: ('[已隱藏]' if k.lower() in ('pw', 'password', 'token', 'cookie', 'cookies') else v)
            for k, v in opt.items() if not k.startswith('_')}

def kill_process(proc):
    if not proc or proc.poll() is not None: return
    try:
        if os.name == 'nt':
            subprocess.run([os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'System32', 'taskkill.exe'), '/PID', str(proc.pid), '/T', '/F'], capture_output=True, creationflags=NOWIN, timeout=5)
        else: proc.kill()
    except Exception:
        try: proc.kill()
        except OSError: pass

NOWIN = 0x08000000 if os.name == 'nt' else 0
LOWPRI = NOWIN | (0x00004000 if os.name == 'nt' else 0)     # BELOW_NORMAL_PRIORITY_CLASS: the PC stays responsive while converting

def base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def E_isurl(s): return bool(re.match(r'^[a-z]+://', s or ''))

_DATA = None
def data_dir():
    """Where settings, logs and downloaded models go: next to the program (portable use, e.g. on a USB drive),
    or %LOCALAPPDATA%\\ZhuanDangGongChang when that folder is read-only (e.g. copied into Program Files)."""
    global _DATA
    if _DATA: return _DATA
    for d in (base_dir(), os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'ZhuanDangGongChang')):
        try:
            os.makedirs(d, exist_ok=True)
            t = os.path.join(d, '.zdgc_write_test')
            with open(t, 'w') as fh: fh.write('1')
            os.remove(t); _DATA = d; return d
        except OSError: continue
    _DATA = tempfile.gettempdir(); return _DATA

def bundled(*parts):
    """Path inside the program's own tools folder (read-only resources shipped with the app)."""
    return os.path.join(base_dir(), 'tools', *parts)

def find_tool(name):
    for p in (os.path.join(base_dir(), 'tools', name + '.exe'), os.path.join(base_dir(), 'tools', name)):
        if os.path.isfile(p):
            return p
    return shutil.which(name)

FFMPEG = find_tool('ffmpeg'); FFPROBE = find_tool('ffprobe')

def find_soffice():
    for p in [os.path.join(base_dir(), 'tools', 'libreoffice', 'program', 'soffice.exe'),os.environ.get('ProgramFiles', r'C:\Program Files') + r'\LibreOffice\program\soffice.exe',
              os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)') + r'\LibreOffice\program\soffice.exe']:
        if os.path.isfile(p):
            return p
    return shutil.which('soffice')

SOFFICE = find_soffice()
SEVENZIP = find_tool('7z') or (r'C:\Program Files\7-Zip\7z.exe' if os.path.isfile(r'C:\Program Files\7-Zip\7z.exe') else None)
PANDOC = find_tool('pandoc')
def _calibre():
    for p in [os.path.join(base_dir(), 'tools', 'calibre', 'ebook-convert.exe'), r'C:\Program Files\Calibre2\ebook-convert.exe']:
        if os.path.isfile(p): return p
    return shutil.which('ebook-convert')
CALIBRE = _calibre()

VIDEO = ['mp4', 'mkv', 'webm', 'mov', 'avi', 'gif']
AUDIO = ['mp3', 'aac', 'm4a', 'wav', 'flac', 'ogg', 'opus']
IMAGE = ['jpg', 'png', 'webp', 'avif', 'ico', 'bmp', 'tiff', 'pdf']
EXT_CAT = {}
for e in ['mp4', 'mkv', 'webm', 'mov', 'avi', 'flv', 'wmv', 'm4v', 'ts', 'mts', '3gp', 'mpg', 'mpeg']: EXT_CAT[e] = 'video'
for e in ['mp3', 'aac', 'm4a', 'wav', 'flac', 'ogg', 'opus', 'wma', 'amr', 'aiff']: EXT_CAT[e] = 'audio'
for e in ['jpg', 'jpeg', 'png', 'webp', 'avif', 'heic', 'heif', 'ico', 'bmp', 'tif', 'tiff']: EXT_CAT[e] = 'image'
EXT_CAT['gif'] = 'video'; EXT_CAT['pdf'] = 'pdf'
RAW = ['cr2', 'cr3', 'nef', 'arw', 'dng', 'orf', 'rw2', 'raf', 'pef', 'srw']
for e in RAW + ['psd', 'svg', 'tga', 'jp2', 'jfif', 'pcx', 'dds', 'qoi']: EXT_CAT[e] = 'image'
for e in ['doc', 'docx', 'odt', 'rtf', 'txt', 'md', 'markdown', 'html', 'htm', 'tex', 'rst', 'org', 'wps']: EXT_CAT[e] = 'doc'
for e in ['xls', 'xlsx', 'ods', 'csv', 'ppt', 'pptx', 'odp', 'key', 'numbers']: EXT_CAT[e] = 'sheet'
for e in ['epub', 'mobi', 'azw3', 'azw', 'fb2', 'kfx']: EXT_CAT[e] = 'ebook'
for e in ['zip', '7z', 'rar', 'tar', 'gz', 'tgz', 'bz2', 'xz', 'zst', 'cab', 'iso']: EXT_CAT[e] = 'archive'
for e in ['srt', 'ass', 'ssa', 'vtt', 'sub', 'lrc']: EXT_CAT[e] = 'subtitle'
for e in ['obj', 'stl', 'ply', 'glb', 'gltf', 'off', '3mf']: EXT_CAT[e] = 'model'
UNSUPPORTED = {'kfx': '亞馬遜 KFX 有 DRM，無法轉換', 'key': 'Apple Keynote 專有格式，請先在 Keynote 匯出', 'numbers': 'Apple Numbers 專有格式，請先匯出',
               'wps': 'WPS 舊格式支援有限', 'azw': '舊 Kindle 格式多半有 DRM'}
PANDOC_IN = {'docx', 'odt', 'rtf', 'txt', 'md', 'markdown', 'html', 'htm', 'tex', 'rst', 'org', 'epub', 'fb2'}

def targets_for(cat, ext=''):
    if ext in UNSUPPORTED and ext in ('kfx', 'key', 'numbers'): return []
    if cat == 'video': return VIDEO + AUDIO + ['srt']
    if cat == 'audio': return AUDIO
    if cat == 'image': return IMAGE
    if cat == 'pdf': return ['png', 'jpg', 'pdf'] + (['docx', 'epub'] if CALIBRE else []) + (['txt'])
    if cat == 'doc':
        t = []
        if ext in PANDOC_IN and PANDOC: t += ['docx', 'odt', 'html', 'md', 'txt', 'epub', 'rtf']
        if SOFFICE: t += ['pdf'] + ([] if ext in ('docx',) else ['docx'])
        return [x for x in dict.fromkeys(t) if x != ext]
    if cat == 'sheet':
        t = (['pdf'] if SOFFICE else [])
        if SOFFICE and ext in ('xls', 'xlsx', 'ods', 'csv'): t += ['xlsx', 'ods', 'csv']
        if SOFFICE and ext in ('ppt', 'pptx', 'odp'): t += ['pptx', 'odp']
        return [x for x in t if x != ext]
    if cat == 'ebook':
        t = []
        if CALIBRE: t += ['epub', 'mobi', 'azw3', 'pdf', 'docx', 'txt']
        elif ext in PANDOC_IN and PANDOC: t += ['docx', 'html', 'md', 'txt', 'odt']
        return [x for x in t if x != ext]
    if cat == 'archive': return (['extract', 'zip', '7z'] if SEVENZIP else [])
    if cat == 'subtitle': return [x for x in ['srt', 'ass', 'vtt'] if x != ext]
    if cat == 'model': return [x for x in ['glb', 'obj', 'stl', 'ply'] if x != ext]
    return []

def suggest(cat, ext):
    t = targets_for(cat, ext)
    if not t: return None
    pref = {'doc': 'pdf' if 'pdf' in t else 'docx', 'sheet': 'pdf', 'ebook': 'epub' if 'epub' in t else 'docx', 'archive': 'extract',
            'subtitle': 'srt' if ext != 'srt' else 'vtt', 'model': 'glb' if ext != 'glb' else 'stl'}.get(cat)
    if pref in t: return pref
    return {'video': 'mp4' if ext != 'mp4' else 'webm', 'audio': 'mp3' if ext != 'mp3' else 'm4a',
            'image': 'webp' if ext not in ('webp',) else 'png', 'pdf': 'png', 'office': 'pdf'}.get(cat)

def classify(path):
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    cat = EXT_CAT.get(ext)
    return cat, ext

def expand(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for r, _, fs in os.walk(p):
                for f in sorted(fs):
                    fp = os.path.join(r, f)
                    if classify(fp)[0]: out.append(fp)
        elif os.path.isfile(p) and classify(p)[0]:
            out.append(p)
    return out

_RESERVED = set(); _RES_LOCK = threading.Lock()
def unique_path(path, avoid=()):
    """Free output name.  Names handed out are reserved for the session, so two jobs running at the same time
    (e.g. clip.mov and clip.mkv both -> clip.mp4) can never write into the same file."""
    root, ext = os.path.splitext(path); n = 1; cand = path
    avoid = {os.path.normcase(os.path.abspath(a)) for a in avoid}
    with _RES_LOCK:
        while True:
            key = os.path.normcase(os.path.abspath(cand))
            if not os.path.exists(cand) and key not in avoid and key not in _RESERVED: break
            cand = f'{root} ({n}){ext}'; n += 1
        _RESERVED.add(key)
    return cand

def log_dir():
    for d in (os.path.join(data_dir(), 'logs'), os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ZhuanDangGongChang', 'logs')):
        try: os.makedirs(d, exist_ok=True); return d
        except OSError: continue
    return tempfile.gettempdir()

_LOG_LOCK = threading.Lock()
def log(msg):
    try:
        p = os.path.join(log_dir(), 'zdgc.log')
        with _LOG_LOCK:
            if os.path.isfile(p) and os.path.getsize(p) > 2_000_000: os.replace(p, p + '.1')
            with open(p, 'a', encoding='utf-8') as fh: fh.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg.rstrip() + '\n')
    except Exception: pass

def log_error(j):
    err = (getattr(j, '_err', '') or '').strip()
    log(f'FAIL {j.tool or j.target} {j.files} -> {j.output}\n  msg: {j.msg}\n  opt: {public_options(j.opt)}\n  stderr: ' + err[-1500:].replace('\n', '\n    '))

def decode_with_ffmpeg(path):
    """HEIC / HEIF (iPhone photos, including 512x512 tile grids) decoded by the separate ffmpeg program,
    so no HEVC/x265 library is ever loaded into 四維八德 itself."""
    from PIL import Image
    import io
    if not FFMPEG: raise RuntimeError('找不到 ffmpeg，無法讀取 HEIC')
    info = run([FFMPEG, '-hide_banner', '-i', path]).stderr
    mp = ['-map', '0:g:0'] if 'Tile Grid' in info or 'tile_grid' in info.lower() else ['-map', '0:v:0']
    r = subprocess.run([FFMPEG, '-hide_banner', '-v', 'error', '-i', path] + mp + ['-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'image2pipe', '-c:v', 'png', '-'],
                       capture_output=True, creationflags=NOWIN)
    if r.returncode != 0 and mp[1] != '0:v:0':
        r = subprocess.run([FFMPEG, '-hide_banner', '-v', 'error', '-i', path, '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'image2pipe', '-c:v', 'png', '-'],
                           capture_output=True, creationflags=NOWIN)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError('無法讀取這張 HEIC 照片：' + r.stderr.decode('utf-8', 'replace').strip().splitlines()[-1:][0][:150] if r.stderr else '無法讀取這張 HEIC 照片')
    im = Image.open(io.BytesIO(r.stdout)); im.load(); return im

def flatten(im, bg=(255, 255, 255)):
    """RGB copy with transparency composited onto white (plain convert('RGB') turns it black)."""
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        from PIL import Image
        im = im.convert('RGBA'); base = Image.new('RGB', im.size, bg); base.paste(im, mask=im.split()[3]); return base
    return im if im.mode in ('RGB', 'L') else im.convert('RGB')

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=NOWIN, **kw)

_PROBE = {}; _PROBE_LOCK = threading.Lock()
def probe_info(path):
    """dict(dur, streams, height, akbps, acodec) via ffmpeg -i (no ffprobe needed, saves ~210 MB).
    Cached per file+mtime so one job never runs ffmpeg -i twice on the same file."""
    if not FFMPEG: return dict(dur=0.0, streams=[], height=0, width=0, akbps=0, acodec='', hdr='')
    try: key = (os.path.abspath(path), os.path.getmtime(path), os.path.getsize(path))
    except OSError: key = None
    if key:
        with _PROBE_LOCK:
            if key in _PROBE: return _PROBE[key]
    r = run([FFMPEG, '-hide_banner', '-i', path])
    dur = 0.0
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', r.stderr)
    if m: dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    streams = [(t.lower(), c) for t, c in re.findall(r'Stream #\d+:\d+.*?: (Video|Audio|Subtitle): (\w+)', r.stderr)]
    h = w = akbps = 0; acodec = ''; hdr = ''
    for line in r.stderr.splitlines():
        if not h and ': Video:' in line and 'attached pic' not in line:
            mm = re.search(r', (\d{2,5})x(\d{2,5})', line)
            if mm: w = int(mm.group(1)); h = int(mm.group(2))
            # e.g. "yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67" -> HLG (iPhone), smpte2084 -> HDR10 / PQ
            if 'arib-std-b67' in line: hdr = 'hlg'
            elif 'smpte2084' in line: hdr = 'pq'
        if not acodec and ': Audio:' in line:
            acodec = re.search(r'Audio: (\w+)', line).group(1)
            mm = re.search(r'(\d+) kb/s', line)
            if mm: akbps = int(mm.group(1))
    res = dict(dur=dur, streams=streams, height=h, width=w, akbps=akbps, acodec=acodec, hdr=hdr)
    if key:
        with _PROBE_LOCK: _PROBE[key] = res
    return res

def hdr_filters(path):
    """HDR (HLG / PQ) -> SDR BT.709 tone mapping, so iPhone / Android HDR clips don't come out grey and washed out
    when re-encoded to 8-bit H.264. Empty list for normal SDR sources."""
    k = probe_info(path).get('hdr')
    if not k: return []
    return ['zscale=t=linear:npl=100', 'format=gbrpf32le', 'zscale=p=bt709', 'tonemap=tonemap=hable:desat=0',
            'zscale=t=bt709:m=bt709:r=tv', 'format=yuv420p']

def probe(path):
    i = probe_info(path); return i['dur'], i['streams']

def probe_duration(path):
    return probe_info(path)['dur']

def mem_gb():
    """Installed RAM in GB (Windows), used to scale parallel work on low-end office PCs."""
    try:
        import ctypes
        class M(ctypes.Structure):
            _fields_ = [('l', ctypes.c_ulong), ('load', ctypes.c_ulong), ('total', ctypes.c_ulonglong), ('avail', ctypes.c_ulonglong),
                        ('tp', ctypes.c_ulonglong), ('ap', ctypes.c_ulonglong), ('tv', ctypes.c_ulonglong), ('av', ctypes.c_ulonglong), ('ae', ctypes.c_ulonglong)]
        m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); return m.total / 2 ** 30
    except Exception:
        try: return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2 ** 30
        except Exception: return 8.0

def low_end():
    """Typical office PC: 4 threads or fewer, or 8 GB RAM or less."""
    return (os.cpu_count() or 4) <= 4 or mem_gb() <= 8.5

def auto_workers():
    """Parallel ffmpeg jobs (each ffmpeg already uses many threads). One at a time on small PCs keeps them responsive."""
    n = os.cpu_count() or 4
    if n <= 4 or mem_gb() <= 6: return 1
    return max(2, min(4, n // 4))

def light_workers():
    """Parallel jobs for mostly single-threaded work (images, PDF, documents, e-books)."""
    n = os.cpu_count() or 4
    if mem_gb() <= 4.5: return 1
    if mem_gb() <= 8.5: return 2
    return max(2, min(6, n // 2))

def work_slots():
    if mem_gb() <= 4.5 or (os.cpu_count() or 2) <= 2: return 1
    if mem_gb() <= 8.5: return 2
    return 4

def encoder_threads(opt=None):
    cores = os.cpu_count() or 2
    if (opt or {}).get('resource_mode') == 'quiet': return max(1, min(2, cores // 2))
    return max(1, min(8, cores // max(2, auto_workers())))

def platform_info():
    import platform
    version = sys.getwindowsversion() if os.name == 'nt' else None
    machine = os.environ.get('PROCESSOR_ARCHITEW6432') or os.environ.get('PROCESSOR_ARCHITECTURE') or platform.machine()
    return dict(system='Windows 11' if version and version.build >= 22000 else 'Windows 10' if version and version.major >= 10 else platform.system(),
                supported=bool(version and version.major >= 10 and sys.maxsize > 2**32), arch=machine, emulated='ARM' in machine.upper(),
                ram=round(mem_gb(),1), cores=os.cpu_count() or 2, heavy=auto_workers(), light=light_workers(), slots=work_slots())

# LibreOffice / Calibre each take 300-600 MB of RAM: limit how many run together
OFFICE_SLOTS = threading.Semaphore(1 if mem_gb() <= 8.5 else 2)

_HW = None; _HW_BUSY = False; _HW_LOCK = threading.Lock()
_HW_CACHE = None   # set lazily (data_dir) - see detect_hw
def detect_hw():
    """Probe GPU encoders once; result cached for 7 days so later launches skip 3 ffmpeg test runs."""
    global _HW, _HW_BUSY
    with _HW_LOCK:
      if _HW is not None and not _HW_BUSY: return _HW
      _HW_BUSY = True; _HW = []
      global _HW_CACHE
      _HW_CACHE = _HW_CACHE or os.path.join(data_dir(), 'hw_cache.json')
      try:
          c = json.load(open(_HW_CACHE, encoding='utf-8'))
          if FFMPEG and c.get('ffmpeg') == os.path.getmtime(FFMPEG) and time.time() - c.get('t', 0) < 7 * 86400:
              _HW = list(c.get('hw', [])); _HW_BUSY = False; return _HW
      except Exception: pass
      if FFMPEG:
        for enc in ['h264_nvenc', 'h264_qsv', 'h264_amf']:
            try:
                r = run([FFMPEG, '-hide_banner', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=256x256:d=0.2', '-c:v', enc, '-f', 'null', '-'], timeout=8)
                if r.returncode == 0: _HW.append(enc)
            except Exception: pass
        try: json.dump(dict(hw=_HW, t=time.time(), ffmpeg=os.path.getmtime(FFMPEG)), open(_HW_CACHE, 'w', encoding='utf-8'))
        except Exception: pass
      _HW_BUSY = False
      return _HW

# crf = x264, cq = GPU, x264 = CPU preset, ab = audio-file kbps (mp3), aac/opus kbps, vab = audio inside video, q = image quality
PRESET = {
    'high':     dict(crf=20, cq=22, x264='medium', ab=256, aac=192, opus=160, vab=192, q=90, vp9=30, pdfq=90, pdfdpi=300),
    'balanced': dict(crf=23, cq=26, x264='veryfast', ab=192, aac=160, opus=128, vab=128, q=80, vp9=34, pdfq=85, pdfdpi=200),
    'small':    dict(crf=28, cq=30, x264='medium', ab=128, aac=112, opus=80,  vab=96,  q=68, vp9=38, pdfq=70, pdfdpi=150),
}

def video_args(target, opt, dur, hw):
    p = PRESET[opt.get('preset', 'balanced')]
    tsize = float(opt.get('target_mb') or 0)
    vab = p['vab']; vbr = None
    if tsize > 0 and dur > 0:
        total_k = tsize * 8192 * 0.92 / dur          # headroom for container overhead + VBV overshoot
        if total_k < 600: vab = 64                   # tiny budget: give the picture the bits
        vbr = max(80, int((total_k - vab - 8) * float(opt.get('_vbr_scale') or 1)))
    strict = bool(opt.get('_vbr_scale'))      # 2nd attempt after overshooting: plain bitrate mode
    rate = lambda: ['-b:v', f'{vbr}k', '-maxrate', f'{int(vbr*1.5)}k', '-bufsize', f'{vbr*2}k']
    # size-capped quality: aim for the 'high' quality level, but never above the bitrate the target size allows.
    # Easy footage ends up smaller than the target, hard footage lands right on it.
    capped = lambda q: ['-crf', str(q), '-maxrate', f'{vbr}k', '-bufsize', f'{vbr*2}k']
    a = []
    if target in ('mp4', 'mov', 'mkv'):
        codec = opt.get('codec', 'auto')
        if codec == 'auto': codec = 'h264'
        if codec not in ('h264', 'hevc', 'av1'): raise ValueError('不支援的影片編碼')
        enc = hw[0] if (hw and opt.get('hwaccel', True) and codec == 'h264') else {'h264': 'libx264', 'hevc': 'libx265', 'av1': 'libsvtav1'}[codec]
        a += ['-c:v', enc]
        a += ['-threads', str(encoder_threads(opt))]
        if enc in ('libx264', 'libx265'):
            a += ['-preset', p['x264']] + ((rate() if strict else capped(PRESET['high']['crf'])) if vbr else ['-crf', str(p['crf'])])
            if enc == 'libx265':
                a += ['-x265-params', f'log-level=error:pools={encoder_threads(opt)}:frame-threads={min(3, encoder_threads(opt))}']
                if target in ('mp4', 'mov'): a += ['-tag:v', 'hvc1']
        elif enc == 'libsvtav1':
            a += ['-preset', '8', '-crf', str(p['crf'] + 7)] + (rate() if vbr else [])
        elif enc == 'h264_nvenc':
            a += ['-preset', 'p5', '-tune', 'hq', '-spatial-aq', '1', '-rc-lookahead', '20', '-bf', '3']
            a += ((['-rc', 'vbr'] + rate() if strict else ['-rc', 'vbr', '-cq', str(PRESET['high']['cq']), '-b:v', f'{vbr}k', '-maxrate', f'{vbr}k', '-bufsize', f'{vbr*2}k'])
                  if vbr else ['-rc', 'vbr', '-cq', str(p['cq']), '-b:v', '0'])
        elif enc == 'h264_qsv':
            a += ['-preset', 'slow'] + (rate() if vbr else ['-global_quality', str(p['cq'])])
        else:
            a += ['-quality', 'quality'] + (['-rc', 'vbr_peak'] + rate() if vbr else ['-rc', 'cqp', '-qp_i', str(p['cq']), '-qp_p', str(p['cq']), '-qp_b', str(p['cq'] + 2)])
        a += ['-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', f'{vab}k']
        if target in ('mp4', 'mov'): a += ['-movflags', '+faststart']
        return a, enc
    if target == 'webm':
        a += ['-c:v', 'libvpx-vp9', '-threads', str(encoder_threads(opt)), '-row-mt', '1', '-tile-columns', '2', '-deadline', 'good', '-cpu-used', '4' if opt.get('preset') != 'small' else '3']
        a += ((rate() if strict else ['-crf', str(PRESET['high']['vp9']), '-b:v', f'{vbr}k']) if vbr else ['-crf', str(p['vp9']), '-b:v', '0'])
        return a + ['-c:a', 'libopus', '-b:a', f"{min(vab, p['opus'])}k"], 'libvpx-vp9'
    if target == 'avi':
        return a + ['-c:v', 'mpeg4', '-q:v', '4' if opt.get('preset') != 'small' else '8', '-c:a', 'libmp3lame', '-b:a', f'{vab}k'], 'mpeg4'
    return a, None

def audio_args(target, opt):
    p = PRESET[opt.get('preset', 'balanced')]
    return {'mp3': ['-c:a', 'libmp3lame', '-b:a', f"{p['ab']}k"], 'aac': ['-c:a', 'aac', '-b:a', f"{p['aac']}k", '-f', 'adts'],
            'm4a': ['-c:a', 'aac', '-b:a', f"{p['aac']}k"], 'wav': ['-c:a', 'pcm_s16le'], 'flac': ['-c:a', 'flac', '-compression_level', '8'],
            'ogg': ['-c:a', 'libvorbis', '-q:a', '6' if p['ab'] >= 256 else '5' if p['ab'] >= 192 else '3'],
            'opus': ['-c:a', 'libopus', '-b:a', f"{p['opus']}k"]}[target]

def audio_kbps(target, opt):
    p = PRESET[opt.get('preset', 'balanced')]
    return {'mp3': p['ab'], 'aac': p['aac'], 'm4a': p['aac'], 'opus': p['opus']}.get(target, 0)

# source codec that can be copied as-is into each audio target
AUDIO_COPY = {'mp3': {'mp3'}, 'aac': {'aac'}, 'm4a': {'aac', 'alac'}, 'opus': {'opus'}, 'ogg': {'vorbis'}, 'flac': {'flac'}}


class Job:
    def __init__(self, files, target, opt, merge=False, tool=None, label=None):
        self.id = uuid.uuid4().hex[:8]; self.files = files; self.target = target; self.opt = dict(opt)
        self.merge = merge; self.state = 'queued'; self.progress = 0.0; self.speed = ''; self.eta = None
        self.msg = ''; self.output = ''; self.proc = None; self.cancelled = False; self.started = None
        self.encoder = ''; self.elapsed = 0.0; self.out_size = 0; self.finished = 0
        self.in_size = 0
        for f in files:
            try: self.in_size += os.path.getsize(f) if os.path.isfile(f) else 0
            except OSError: pass
        self.cat = 'tool' if tool else classify(files[0])[0]
        self.tool = tool; self.label = label
        self.validation = ''; self.warnings = []; self.child = None

    def info(self):
        nm = os.path.basename(self.files[0].rstrip('\\/')) or self.files[0]
        if self.merge and len(self.files) > 1: nm += f' 等 {len(self.files)} 個'
        progress = self.progress; speed = self.speed
        if self.child and self.state == 'running':
            progress = max(progress, getattr(self, '_child_base', progress) + getattr(self, '_child_span', 0) * self.child.progress)
            speed = self.child.speed or self.msg or speed
        return dict(id=self.id, name=nm, target=self.target, label=self.label or '', kind=self.tool or '', state=self.state, progress=round(min(1, progress), 3), speed=speed,
                    eta=self.eta, msg=self.msg, output=self.output, encoder=self.encoder, elapsed=round(self.elapsed, 2),
                    in_size=self.in_size, out_size=self.out_size, finished=self.finished, retry=self.tool not in ('rec',), validation=self.validation)

    def measure(self):
        p = self.output
        try:
            if p and os.path.isfile(p): self.out_size = os.path.getsize(p)
            elif p and os.path.isdir(p): self.out_size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
        except OSError: pass
        self.finished = time.time()


class Engine:
    def __init__(self, workers=2, light=None):
        self.jobs = {}; self.order = []; self.lock = threading.Lock()
        self.outcomes = {}
        self.execution_slots = threading.Semaphore(work_slots())
        self.quiet_slots = threading.Semaphore(1)
        # ffmpeg jobs are multi-threaded on their own -> few at a time; everything else runs in a wider pool
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.light = ThreadPoolExecutor(max_workers=light or light_workers())

    def out_path(self, job, src, ext):
        folder = job.opt.get('out_dir') or os.path.dirname(src)
        os.makedirs(folder, exist_ok=True)
        stem = os.path.splitext(os.path.basename(src))[0]
        if job.merge: stem += '_合併'
        stem += job.opt.get('_suffix', '')
        return unique_path(os.path.join(folder, f'{stem}.{ext}'), avoid=job.files)

    def submit(self, files, target, opt, merge=False):
        files = [os.path.abspath(f) for f in files]
        jobs = [Job(files, target, opt, True)] if merge else [Job([f], target, opt) for f in files]
        with self.lock:
            for j in jobs:
                self.jobs[j.id] = j; self.order.append(j.id)
                heavy = j.cat in ('video', 'audio') and not (j.cat == 'video' and target == 'srt')
                (self.pool if heavy else self.light).submit(self._run, j)
        return [j.id for j in jobs]

    def submit_tool(self, tool, files, opt, label, together=False, heavy=True):
        files = [f if E_isurl(f) else os.path.abspath(f) for f in files]
        jobs = [Job(files, tool, opt, True, tool=tool, label=label)] if together else [Job([f], tool, opt, tool=tool, label=label) for f in files]
        with self.lock:
            for j in jobs:
                self.jobs[j.id] = j; self.order.append(j.id)
                (self.pool if heavy else self.light).submit(self._run, j)
        return [j.id for j in jobs]

    def add_external(self, j):
        """Register a job driven from outside the pools (screen recording, downloads)."""
        with self.lock: self.jobs[j.id] = j; self.order.append(j.id)

    def busy(self):
        with self.lock: return any(self.jobs[i].state in ('queued', 'running') for i in self.order)

    def cancel(self, jid):
        j = self.jobs.get(jid)
        if not j: return
        if j.state not in ('queued', 'running'): return
        j.cancelled = True
        if j.child:
            j.child.cancelled = True
            if j.child.proc and j.child.proc.poll() is None:
                kill_process(j.child.proc)
        if j.state == 'queued': j.state = 'cancelled'; j.msg = '已取消'
        if j.proc and j.proc.poll() is None:
            kill_process(j.proc)

    def clear_done(self):
        with self.lock:
            self.order = [i for i in self.order if self.jobs[i].state in ('queued', 'running')]
            self.jobs = {i: self.jobs[i] for i in self.order}

    def shutdown(self):
        for j in self.status():
            if j['state'] in ('queued', 'running'): self.cancel(j['id'])
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.light.shutdown(wait=False, cancel_futures=True)

    def status(self):
        with self.lock:
            return [self.jobs[i].info() for i in self.order]

    def _run(self, j):
        if getattr(j, '_nested', False): return self._run_guarded(j)
        quiet = j.opt.get('resource_mode') == 'quiet'
        if quiet:
            while not self.quiet_slots.acquire(timeout=.1):
                if j.cancelled: return
                j.msg = '省資源模式：等待前一個工作'
        acquired = False
        try:
            while not self.execution_slots.acquire(timeout=.1):
                if j.cancelled: return
                j.msg = '等待可用處理資源'
            acquired = True
            return self._run_guarded(j)
        finally:
            if acquired: self.execution_slots.release()
            if quiet: self.quiet_slots.release()

    def _run_guarded(self, j):
        if j.cancelled: return
        j.state = 'running'; j.started = time.time()
        try:
            self._check_space(j)
            ext = classify(j.files[0])[1]
            if j.tool == 'hardware_test':
                import system_tools; system_tools.run_tests(self, j)
            elif j.tool == 'workflow':
                import workflows; workflows.run(self, j)
            elif j.cat == 'tool':
                import tools; tools.run(self, j)
            elif ext in UNSUPPORTED and not targets_for(j.cat, ext): raise RuntimeError(UNSUPPORTED[ext])
            elif j.cat == 'video' and j.target == 'srt':
                self._sub(j)
            elif j.cat in ('video', 'audio'):
                self._ffmpeg(j)
            elif j.cat == 'image':
                self._image(j)
            elif j.cat == 'pdf':
                self._pdf(j)
            elif j.cat in ('doc', 'sheet', 'office'):
                self._doc(j)
            elif j.cat == 'ebook':
                self._ebook(j)
            elif j.cat == 'archive':
                self._archive(j)
            elif j.cat == 'subtitle':
                self._sub(j)
            elif j.cat == 'model':
                self._model(j)
            else: raise RuntimeError('無法辨識來源檔案類型')
            if j.cancelled: raise InterruptedError
            if j.tool != 'workflow': self.validate(j)
            j.state = 'partial' if j.warnings else 'done'; j.progress = 1.0; j.msg = '部分完成：' + '；'.join(j.warnings)[:240] if j.warnings else '完成'; j.eta = 0
        except InterruptedError:
            j.state = 'cancelled'; j.msg = '已取消'
            if j.output and os.path.exists(j.output):
                try: os.remove(j.output)
                except Exception: pass
        except Exception as e:
            j.state = 'error'; j.msg = str(e)[:300]
            if j.output and os.path.isfile(j.output) and not getattr(j, 'keep_output', False):   # don't leave half-written files behind
                try: os.remove(j.output)
                except Exception: pass
        j.elapsed = time.time() - j.started
        j.measure()
        with self.lock:
            self.outcomes[j.id] = j.state
            if len(self.outcomes) > 1000: self.outcomes.pop(next(iter(self.outcomes)))
        if j.state == 'error': log_error(j)

    def _check_space(self, j):
        """Fail early with a clear message instead of a half-written file when the target drive is (almost) full."""
        folder = j.opt.get('out_dir') or (os.path.dirname(j.files[0]) if os.path.isfile(j.files[0]) else '')
        if not folder or not os.path.isdir(folder): return
        try: free = shutil.disk_usage(folder).free
        except OSError: return
        need = 200 * 2 ** 20 + (j.in_size if j.target in ('extract', 'wav', 'flac', 'avi', 'bmp', 'tiff') else 0)
        if free < need:
            raise RuntimeError(f'磁碟空間不足：{os.path.splitdrive(os.path.abspath(folder))[0] or folder} 只剩 {free / 2 ** 20:.0f} MB，'
                               f'請清出空間或在「儲存位置」改存到其他磁碟')

    def validate(self, j):
        import validation
        try:
            j.validation = validation.check(self, j)
        except Exception:
            j.keep_output = True
            j.validation = '未通過輸出檢查'
            raise

    def retry(self, jid):
        """Run a failed / cancelled job again with exactly the same settings."""
        old = self.jobs.get(jid)
        if not old or old.state not in ('error', 'cancelled', 'done', 'partial'): return None
        j = Job(old.files, old.target, old.opt, old.merge, tool=old.tool, label=old.label)
        if old.tool == 'dl': return 'dl'
        heavy = (j.cat in ('video', 'audio') and j.target != 'srt') if not j.tool else (j.tool in ('workflow', 'hardware_test') or j.tool in __import__('tools').HEAVY)
        with self.lock:
            self.jobs[j.id] = j; self.order.append(j.id)
            if old.state != 'done': self.order.remove(jid)
            (self.pool if heavy else self.light).submit(self._run, j)
        return j.id

    # ---------- ffmpeg ----------
    def _ffmpeg(self, j):
        if not FFMPEG: raise RuntimeError('找不到 ffmpeg（tools 資料夾）')
        o = j.opt; t = j.target
        out = self.out_path(j, j.files[0], t); j.output = out
        ss = float(o.get('trim_start') or 0); to = float(o.get('trim_end') or 0)
        tmb = float(o.get('target_mb') or 0)
        if (tmb and not j.merge and not ss and not to and not int(o.get('height') or 0) and not o.get('loudnorm') and not o.get('_vf') and not o.get('_logo') and o.get('codec', 'auto') == 'auto'
                and classify(j.files[0])[1] == t and os.path.getsize(j.files[0]) <= tmb * 1048576):
            shutil.copyfile(j.files[0], out); j.encoder = '原檔已小於目標大小，直接複製'; return
        cmd = [FFMPEG, '-hide_banner', '-nostdin', '-y', '-progress', 'pipe:1', '-nostats', '-v', 'error', '-filter_complex_threads', str(min(2, encoder_threads(o)))]
        if j.merge:
            durs = [probe_duration(f) for f in j.files]; dur = sum(durs)
            for f in j.files: cmd += ['-i', f]
            n = len(j.files)
            if t in AUDIO or j.cat == 'audio':
                fc = ''.join(f'[{i}:a:0]' for i in range(n)) + f'concat=n={n}:v=0:a=1[a]'
                cmd += ['-filter_complex', fc, '-map', '[a]']
            else:
                h = int(o.get('height') or 0) or 720
                first = probe_info(j.files[0])
                w = max(2, round(h * (first['width'] or 16) / (first['height'] or 9)) // 2 * 2)
                pre = ''
                for i, src in enumerate(j.files):
                    pre += f'[{i}:v:0]' + ''.join(x + ',' for x in hdr_filters(src))
                    pre += f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v{i}];'
                    if any(k == 'audio' for k, _ in probe_info(src)['streams']):
                        pre += f'[{i}:a:0]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}];'
                    else:
                        pre += f'anullsrc=r=48000:cl=stereo,atrim=duration={max(durs[i], 0.1)},asetpts=PTS-STARTPTS[a{i}];'
                fc = pre + ''.join(f'[v{i}][a{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=1[v][a]'
                cmd += ['-filter_complex', fc, '-map', '[v]', '-map', '[a]']
        else:
            dur = probe_duration(j.files[0])
            if ss: cmd += ['-ss', str(ss)]
            if to and to > ss: cmd += ['-to', str(to)]
            cmd += ['-i', j.files[0]]
            if to and to > ss: dur = to - ss
            elif ss: dur = max(0.1, dur - ss)
        vf = []
        h = int(o.get('height') or 0)
        info = probe_info(j.files[0])
        if h and not j.merge and info['height'] and h >= info['height'] and t != 'gif':
            h = 0                                    # never upscale: bigger file, no extra detail
        if not j.merge: vf += hdr_filters(j.files[0])
        if h and not j.merge and t != 'gif': vf.append(f'scale=-2:{h}')
        vf += list(o.get('_vf') or [])
        if t in AUDIO:
            if self._can_copy_audio(j, t, info):
                cmd += ['-vn', '-map', '0:a:0', '-c:a', 'copy'] + (['-f', 'adts'] if t == 'aac' else [])
                j.encoder = '直接取出音軌（不重新編碼）'
            else:
                aa = audio_args(t, o)
                cap = self._audio_cap(j, t, info)
                if cap: aa[aa.index('-b:a') + 1] = f'{cap}k'
                cmd += ['-vn'] + aa; j.encoder = aa[1]
        elif t == 'gif':
            gh = h or 480; fps = 12 if o.get('preset') == 'small' else 15
            cmd += ['-vf', ''.join(x + ',' for x in vf if not x.startswith('scale=')) + f'fps={fps},scale=-2:{gh}:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a', '-an']
            j.encoder = 'gif'
        elif self._can_copy(j, t):
            cmd += ['-map', '0', '-c', 'copy'] + (['-movflags', '+faststart'] if t in ('mp4', 'mov') else [])
            j.encoder = '直接封裝（不重新編碼）'
        else:
            va, enc = video_args(t, o, dur, detect_hw())
            if o.get('_logo') and not j.merge:
                cmd += ['-i', o['_logo'], '-filter_complex', '[0:v]' + (','.join(vf) if vf else 'null') + "[base];[1:v]scale=160:-1[logo];[base][logo]overlay=W-w-20:H-h-20[vout]", '-map', '[vout]', '-map', '0:a?']
            elif vf: cmd += ['-vf', ','.join(vf)]
            cmd += va; j.encoder = enc
        if o.get('loudnorm') and t != 'gif' and '-c' not in cmd and 'copy' not in cmd:
            cmd += ['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
        cmd.append(out)
        self._exec(j, cmd, dur)
        # hw failure fallback: swap only the encoder arguments, keep filters / loudnorm
        if j.state == 'running' and getattr(j, '_rc', 0) != 0 and j.encoder in ('h264_nvenc', 'h264_qsv', 'h264_amf') and not j.cancelled:
            o2 = dict(o); o2['hwaccel'] = False
            va_old, _ = video_args(t, o, dur, [j.encoder])
            va, enc = video_args(t, o2, dur, [])
            i = cmd.index('-c:v')
            cmd = cmd[:i] + va + cmd[i + len(va_old):]; j.encoder = enc + '（GPU 失敗改用 CPU）'
            self._exec(j, cmd, dur)
        if getattr(j, '_rc', 0) != 0 and not j.cancelled:
            import tools; raise RuntimeError(tools.ff_error(j._err))
        # target size is a promise: if the encoder overshot, redo once in strict bitrate mode, scaled down
        if tmb and t not in AUDIO and t != 'gif' and '-c:v' in cmd and os.path.getsize(out) > tmb * 1048576 and not j.cancelled:
            got = os.path.getsize(out) / 1048576
            o2 = dict(o, _vbr_scale=(float(o.get('_vbr_scale') or 1)) * tmb / got * 0.97)
            va_old, _ = video_args(t, o, dur, [j.encoder.split('（')[0]] if j.encoder.startswith('h264_') else [])
            va, enc = video_args(t, o2, dur, [j.encoder.split('（')[0]] if j.encoder.startswith('h264_') else [])
            i = cmd.index('-c:v'); cmd = cmd[:i] + va + cmd[i + len(va_old):]
            j.encoder = (enc or '') + f'（第一次 {got:.1f} MB 超過目標，已重壓）'
            self._exec(j, cmd, dur)
            if j._rc != 0 and not j.cancelled:
                import tools; raise RuntimeError(tools.ff_error(j._err))
        # re-encoded result bigger than the source and nothing was asked to change? keep the original streams instead
        if (not j.merge and not ss and not to and not h and not float(o.get('target_mb') or 0) and not o.get('loudnorm')
                and not o.get('_vf') and not o.get('_logo') and o.get('codec', 'auto') == 'auto'
                and t in ('mp4', 'mkv', 'mov') and '-c:v' in cmd and o.get('fastcopy', True)
                and os.path.getsize(out) > os.path.getsize(j.files[0]) and self._streams_copyable(j, t)):
            cmd2 = cmd[:cmd.index('-i') + 2] + ['-map', '0', '-c', 'copy'] + (['-movflags', '+faststart'] if t in ('mp4', 'mov') else []) + [out]
            cmd2[cmd2.index('-progress'):cmd2.index('-progress') + 2] = []
            if run(cmd2).returncode == 0: j.encoder = '保留原始編碼（重新編碼反而較大）'

    def _audio_cap(self, j, t, info):
        """Don't spend more bits than a lossy source has: 96k AAC -> 192k MP3 only makes the file bigger."""
        want = audio_kbps(t, j.opt)
        src = info['akbps']
        if j.merge or not want or not src or info['acodec'] in ('flac', 'alac', 'pcm_s16le', 'pcm_s24le', 'pcm_f32le', 'wavpack', 'ape', 'truehd'):
            return 0
        if info['acodec'].startswith('pcm'): return 0
        cap = max(64, -(-int(src * 1.15) // 16) * 16)
        return cap if cap < want else 0

    def _can_copy_audio(self, j, t, info):
        o = j.opt
        if j.merge or not o.get('fastcopy', True) or o.get('loudnorm') or t not in AUDIO_COPY: return False
        if info['acodec'] not in AUDIO_COPY[t]: return False
        if t == 'flac' or info['acodec'] == 'alac': return True
        want = audio_kbps(t, o)
        return bool(info['akbps']) and info['akbps'] <= want + 16

    def _can_copy(self, j, t):
        o = j.opt
        if j.merge or not o.get('fastcopy', True) or o.get('_vf') or o.get('_logo') or t not in ('mp4', 'mkv', 'mov') or int(o.get('height') or 0) or float(o.get('target_mb') or 0) or o.get('loudnorm'):
            return False
        codec = o.get('codec', 'auto')
        if codec != 'auto' and any(name != codec for typ, name in probe(j.files[0])[1] if typ == 'video'): return False
        return self._streams_copyable(j, t) and os.path.splitext(j.files[0])[1].lower() != '.' + t

    def _streams_copyable(self, j, t):
        _, streams = probe(j.files[0])
        ok_v = {'h264', 'hevc', 'av1'} if t != 'mkv' else {'h264', 'hevc', 'av1', 'vp9', 'vp8', 'mpeg4'}
        ok_a = {'aac', 'mp3', 'ac3', 'opus', 'flac'} if t != 'mov' else {'aac', 'mp3', 'ac3'}
        has_v = False
        for typ, name in streams:
            if typ == 'video' and name not in ('mjpeg', 'png'):
                if name not in ok_v: return False
                has_v = True
            elif typ == 'audio' and name not in ok_a: return False
            elif typ == 'subtitle' and t != 'mkv': return False
        return has_v

    def _exec(self, j, cmd, dur, cwd=None, base=0.0, span=1.0):
        if j.cancelled: raise InterruptedError
        j.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=LOWPRI, cwd=cwd)
        proc = j.proc
        err = []
        th = threading.Thread(target=lambda: err.extend(proc.stderr.readlines()), daemon=True); th.start()
        t0 = time.time()
        for line in j.proc.stdout:
            k, _, v = line.strip().partition('=')
            if k == 'out_time_us' and dur > 0:
                try:
                    cur = int(v) / 1e6; f = min(1.0, max(0, cur / dur)); j.progress = min(0.99, base + span * f)
                    el = time.time() - t0
                    if f > 0.01: j.eta = round(el / f - el)
                except ValueError: pass
            elif k == 'speed':
                j.speed = v.strip()
        j.proc.wait(); th.join(2)
        j._rc = j.proc.returncode; j._err = ''.join(err)
        proc.stdout.close()
        if not th.is_alive(): proc.stderr.close()
        if j.cancelled: raise InterruptedError

    # ---------- images ----------
    def _open_img(self, path):
        from PIL import Image
        ext = classify(path)[1]
        if ext in RAW:
            import rawpy
            with rawpy.imread(path) as r: return Image.fromarray(r.postprocess(use_camera_wb=True))
        if ext == 'psd':
            from psd_tools import PSDImage
            return PSDImage.open(path).composite()
        if ext == 'svg':
            import resvg_py, io
            data = resvg_py.svg_to_bytes(svg_path=path)
            return Image.open(io.BytesIO(bytes(data)))
        if ext in ('heic', 'heif'):
            return decode_with_ffmpeg(path)
        try:
            im = Image.open(path); im.load(); return im
        except Exception:
            if ext == 'avif': return decode_with_ffmpeg(path)      # Pillow without AVIF support
            raise

    def _image(self, j):
        from PIL import Image, ImageOps
        o = j.opt; t = j.target; preset = o.get('preset', 'balanced'); q = PRESET[preset]['q']
        h = int(o.get('height') or 0)
        if t == 'pdf':
            ims = []
            cap = {'high': 0, 'balanced': 3000, 'small': 2000}[preset]   # long side; 2000 px ≈ A4 at 240 dpi
            for i, f in enumerate(j.files):
                if j.cancelled: raise InterruptedError
                im = flatten(ImageOps.exif_transpose(self._open_img(f)))
                if h and im.height > h: im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
                if cap and max(im.size) > cap: im.thumbnail((cap, cap), Image.LANCZOS)
                ims.append(im); j.progress = (i + 1) / (len(j.files) + 1)
            out = self.out_path(j, j.files[0], 'pdf'); j.output = out
            # Pillow stores RGB pages as JPEG inside the PDF -> quality controls the size
            ims[0].save(out, save_all=True, append_images=ims[1:], resolution=150, quality=q, optimize=True)
            j.encoder = 'Pillow'; return
        im = ImageOps.exif_transpose(self._open_img(j.files[0]))
        if h and h < im.height: im = im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)   # never upscale
        out = self.out_path(j, j.files[0], t); j.output = out; j.encoder = 'Pillow'
        tsize = float(o.get('target_mb') or 0) * 1024 * 1024
        if t in ('jpg', 'bmp'): im = flatten(im)
        elif im.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P', '1') and t in ('png', 'webp', 'avif', 'ico'):
            im = im.convert('RGBA' if 'A' in im.mode or 'transparency' in im.info else 'RGB')
        if t in ('webp', 'avif') and im.mode == 'P': im = im.convert('RGBA' if 'transparency' in im.info else 'RGB')
        icc = im.info.get('icc_profile')

        def encode(qq):
            import io
            kw = {}
            if t == 'jpg': kw = dict(format='JPEG', quality=qq, optimize=True, progressive=True, subsampling=0 if preset == 'high' else 2)
            elif t == 'png': kw = dict(format='PNG', optimize=preset != 'high', compress_level=9 if preset == 'small' else 6)
            elif t == 'webp': kw = dict(format='WEBP', quality=qq, method=6 if preset == 'small' else 5)
            elif t == 'avif': kw = dict(format='AVIF', quality=qq)
            elif t == 'ico':
                im2 = im.copy(); im2.thumbnail((256, 256))
                kw = dict(format='ICO', sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256) if s <= max(im2.size)])
                b = io.BytesIO(); im2.save(b, **kw); return b.getvalue()
            elif t == 'bmp': kw = dict(format='BMP')
            elif t == 'tiff': kw = dict(format='TIFF', compression='tiff_adobe_deflate')
            if icc and t in ('jpg', 'png', 'webp', 'avif', 'tiff'): kw['icc_profile'] = icc   # keep colours right, drop the rest of EXIF
            b = io.BytesIO(); im.save(b, **kw); return b.getvalue()

        data = encode(q)
        if tsize and t in ('jpg', 'webp', 'avif') and len(data) > tsize:
            lo, hi, best = 10, q, None                  # binary search in memory, write once
            while hi - lo > 2:
                mid = (lo + hi) // 2; d = encode(mid)
                if len(d) > tsize: hi = mid
                else: lo = mid; best = d
            data = best or encode(lo)
        # same format, no resize, and we only made it bigger? keep the original bytes
        src = j.files[0]
        if not h and classify(src)[1] in ({t} | ({'jpeg', 'jfif'} if t == 'jpg' else set()) | ({'tif'} if t == 'tiff' else set())):
            try:
                if len(data) >= os.path.getsize(src):
                    shutil.copyfile(src, out); j.encoder = 'Pillow（原檔已是最小，直接複製）'; return
            except OSError: pass
        with open(out, 'wb') as fh: fh.write(data)

    # ---------- pdf ----------
    @pdfium_serial
    def _pdf(self, j):
        if j.target == 'txt': return self._pdf_text(j)
        if j.target in ('docx', 'epub'): return self._ebook(j)
        preset = j.opt.get('preset', 'balanced')
        if j.merge or j.target == 'pdf':
            from pypdf import PdfWriter
            w = PdfWriter()
            for f in j.files:
                if j.cancelled: raise InterruptedError
                w.append(f)
            j.progress = 0.3
            for i, page in enumerate(w.pages):
                if j.cancelled: raise InterruptedError
                if preset == 'small': self._shrink_pdf_images(page, PRESET['small']['q'], 1600)
                try: page.compress_content_streams(level=9)
                except Exception: pass
                j.progress = 0.3 + 0.6 * (i + 1) / max(1, len(w.pages))
            try: w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
            except Exception: pass
            out = self.out_path(j, j.files[0], 'pdf'); j.output = out
            with open(out, 'wb') as fh: w.write(fh)
            if not j.merge and os.path.getsize(out) >= os.path.getsize(j.files[0]):
                shutil.copyfile(j.files[0], out); j.encoder = 'pypdf（原檔已是最小，直接複製）'; return
            j.encoder = 'pypdf'; return
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(j.files[0]); n = len(pdf)
        dpi = {'high': 200, 'balanced': 150, 'small': 100}[preset]
        q = PRESET[preset]['q']
        folder = self.out_path(j, j.files[0], 'x')[:-2]
        folder = unique_path(folder); os.makedirs(folder); j.output = folder; j.encoder = 'PDFium'
        for i in range(n):
            if j.cancelled: raise InterruptedError
            img = pdf[i].render(scale=dpi / 72).to_pil()
            p = os.path.join(folder, f'{i+1:03d}.{j.target}')
            if j.target == 'jpg': img.convert('RGB').save(p, quality=q, optimize=True, progressive=True)
            else: img.save(p, optimize=preset == 'small')
            j.progress = (i + 1) / n
        pdf.close()

    @staticmethod
    def _shrink_pdf_images(page, quality, max_side):
        """Re-compress big photos inside a PDF page (lossy; only used by the 小檔案 preset)."""
        try: images = list(page.images)
        except Exception: return
        for img in images:
            try:
                obj = img.indirect_reference.get_object() if img.indirect_reference else None
                if obj is None or '/SMask' in obj or '/Mask' in obj: continue      # keep transparency intact
                if obj.get('/BitsPerComponent', 8) != 8: continue
                pil = img.image
                if pil.mode not in ('RGB', 'L') or max(pil.size) < 400: continue
                if max(pil.size) > max_side: pil.thumbnail((max_side, max_side))
                img.replace(pil, quality=quality)
            except Exception:
                continue

    @pdfium_serial
    def _pdf_text(self, j):
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(j.files[0])
        out = self.out_path(j, j.files[0], 'txt'); j.output = out
        with open(out, 'w', encoding='utf-8') as fh:
            for i in range(len(pdf)):
                if j.cancelled: raise InterruptedError
                fh.write(pdf[i].get_textpage().get_text_range() + '\n\f\n'); j.progress = (i + 1) / len(pdf)
        pdf.close()
        j.encoder = 'PDFium'

    def _proc(self, j, cmd, what, cwd=None):
        if j.cancelled: raise InterruptedError
        j.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=LOWPRI, cwd=cwd)
        o, e = j.proc.communicate(); j._err = e or o
        if j.cancelled: raise InterruptedError
        if j.proc.returncode != 0: raise RuntimeError(f'{what} 失敗：' + ((e or o).strip().splitlines() or [''])[-1][:200])

    def _doc(self, j):
        ext = classify(j.files[0])[1]; t = j.target
        if PANDOC and ext in PANDOC_IN and t in ('docx', 'odt', 'html', 'md', 'txt', 'epub', 'rtf'):
            out = self.out_path(j, j.files[0], t); j.output = out
            fmt = {'md': 'gfm', 'txt': 'plain', 'html': 'html'}.get(t, t)
            fin = {'md': 'markdown', 'markdown': 'markdown', 'txt': 'markdown', 'htm': 'html', 'tex': 'latex'}.get(ext, ext)
            cmd = [PANDOC, j.files[0], '-f', fin, '-t', fmt, '-o', out, '--resource-path', os.path.dirname(j.files[0])]
            if t in ('html', 'epub'): cmd.append('--standalone')
            self._proc(j, cmd, 'Pandoc'); j.encoder = 'Pandoc'; return
        self._office(j)

    def _ebook(self, j):
        if CALIBRE:
            out = self.out_path(j, j.files[0], j.target); j.output = out
            with OFFICE_SLOTS:
                if j.cancelled: raise InterruptedError
                self._proc(j, [CALIBRE, j.files[0], out], 'Calibre')
            j.encoder = 'Calibre'; return
        return self._doc(j)

    def _archive(self, j):
        if not SEVENZIP: raise RuntimeError('缺少 7-Zip 元件')
        src = j.files[0]
        if j.target == 'extract':
            stem = os.path.basename(src)
            for suf in ('.tar.gz', '.tar.xz', '.tar.bz2', '.tgz'):
                if stem.lower().endswith(suf): stem = stem[:-len(suf)]; break
            else: stem = os.path.splitext(stem)[0]
            folder = unique_path(os.path.join(j.opt.get('out_dir') or os.path.dirname(src), stem)); j.output = folder
            self._proc(j, [SEVENZIP, 'x', '-y', '-bso0', '-bsp0', f'-o{folder}', src], '解壓縮')
            inner = os.listdir(folder)
            if len(inner) == 1 and inner[0].lower().endswith('.tar'):
                tar = os.path.join(folder, inner[0]); self._proc(j, [SEVENZIP, 'x', '-y', '-bso0', f'-o{folder}', tar], '解壓縮'); os.remove(tar)
        else:
            out = self.out_path(j, src, j.target); j.output = out
            lvl = {'high': '9', 'balanced': '5', 'small': '9'}[j.opt.get('preset', 'balanced')]
            tmp = tempfile.mkdtemp(prefix='zdgc_repack_')
            try:
                self._proc(j, [SEVENZIP, 'x', '-y', '-bso0', '-bsp0', f'-o{tmp}', src], '解開來源壓縮檔')
                inner = os.listdir(tmp)
                if len(inner) == 1 and inner[0].lower().endswith('.tar'):
                    tar = os.path.join(tmp, inner[0]); self._proc(j, [SEVENZIP, 'x', '-y', '-bso0', f'-o{tmp}', tar], '解開 TAR'); os.remove(tar)
                if not os.listdir(tmp): raise RuntimeError('來源壓縮檔沒有內容')
                self._proc(j, [SEVENZIP, 'a', '-bso0', '-bsp0', f'-mx={lvl}', '-mmt=on', out, '.\\*'], '重新壓縮', cwd=tmp)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        j.encoder = '7-Zip'

    def _sub(self, j):
        out = self.out_path(j, j.files[0], j.target); j.output = out
        src = j.files[0]; tmp = None
        if j.cat == 'subtitle':
            # Big5 / GBK / UTF-16 subtitles are common; ffmpeg only reads UTF-8, so normalise first
            import tools
            tmp = tempfile.mkdtemp(prefix='zdgc_s_'); src = os.path.join(tmp, 'in' + os.path.splitext(j.files[0])[1].lower())
            with open(src, 'w', encoding='utf-8') as fh: fh.write(tools.read_text_any(j.files[0]))
        try: self._sub_run(j, src, out)
        finally:
            if tmp: shutil.rmtree(tmp, ignore_errors=True)

    def _sub_run(self, j, src, out):
        cmd = [FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-y', '-i', src]
        if j.cat == 'video': cmd += ['-map', '0:s:0']
        self._proc(j, cmd + [out], '字幕轉換（影片需內含字幕軌）'); j.encoder = 'FFmpeg'

    def _model(self, j):
        import trimesh
        m = trimesh.load(j.files[0], force=None)
        out = self.out_path(j, j.files[0], j.target); j.output = out
        if j.target in ('stl', 'ply', 'obj') and isinstance(m, trimesh.Scene): m = m.dump(concatenate=True)
        m.export(out); j.encoder = 'trimesh'

    _lo_slots = threading.local(); _lo_next = [0]; _lo_lock = threading.Lock()
    def _lo_profile(self):
        """One LibreOffice profile per worker thread, kept between jobs and launches.
        A fresh profile costs several seconds of first-run setup on every conversion."""
        sl = getattr(self._lo_slots, 'n', None)
        if sl is None:
            with self._lo_lock: sl = self._lo_next[0]; self._lo_next[0] += 1
            self._lo_slots.n = sl
        d = os.path.join(tempfile.gettempdir(), 'zdgc_lo', f'p{sl}')
        os.makedirs(d, exist_ok=True)
        from pathlib import Path
        return Path(d).as_uri()

    def _office(self, j):
        if not SOFFICE: raise RuntimeError('需要 LibreOffice 才能轉這個格式')
        with OFFICE_SLOTS:
            if j.cancelled: raise InterruptedError
            return self._office_run(j)

    def _office_run(self, j):
        out = self.out_path(j, j.files[0], j.target); j.output = out
        tmp = tempfile.mkdtemp(prefix='zdgc_')
        ext = classify(j.files[0])[1]; t = j.target
        conv = t
        if t == 'pdf':
            p = PRESET[j.opt.get('preset', 'balanced')]
            filt = 'calc_pdf_Export' if ext in ('xls', 'xlsx', 'ods', 'csv') else 'impress_pdf_Export' if ext in ('ppt', 'pptx', 'odp') else 'writer_pdf_Export'
            conv = 'pdf:%s:%s' % (filt, json.dumps({
                'Quality': {'type': 'long', 'value': str(p['pdfq'])},
                'ReduceImageResolution': {'type': 'boolean', 'value': 'true'},
                'MaxImageResolution': {'type': 'long', 'value': str(p['pdfdpi'])},
                'UseLosslessCompression': {'type': 'boolean', 'value': 'false'}}, separators=(',', ':')))
        try:
            for attempt in (conv, t) if conv != t else (t,):
                j.proc = subprocess.Popen([SOFFICE, f'-env:UserInstallation={self._lo_profile()}', '--headless', '--norestore', '--nolockcheck',
                                           '--convert-to', attempt, '--outdir', tmp, j.files[0]],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=LOWPRI)
                j.proc.communicate()
                if j.cancelled: raise InterruptedError
                res = [f for f in os.listdir(tmp) if f.lower().endswith('.' + t)]
                if res: break
            if not res: raise RuntimeError('LibreOffice 轉換失敗')
            shutil.move(os.path.join(tmp, res[0]), out); j.encoder = 'LibreOffice'
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


CAT_ZH = {'video': '影片', 'audio': '音訊', 'image': '圖片', 'pdf': 'PDF', 'doc': '文件', 'sheet': '試算表／簡報', 'ebook': '電子書',
          'archive': '壓縮檔', 'subtitle': '字幕', 'model': '3D 模型'}
def format_table():
    rows = []
    for cat in CAT_ZH:
        exts = sorted(e for e, c in EXT_CAT.items() if c == cat)
        outs = sorted({t for e in exts for t in targets_for(cat, e)})
        engine = {'video': 'FFmpeg', 'audio': 'FFmpeg', 'image': 'Pillow／LibRaw／resvg', 'pdf': 'PDFium／pypdf', 'doc': 'Pandoc／LibreOffice',
                  'sheet': 'LibreOffice', 'ebook': 'Calibre／Pandoc', 'archive': '7-Zip', 'subtitle': 'FFmpeg', 'model': 'trimesh'}[cat]
        note = []
        if cat in ('sheet',) and not SOFFICE: note.append('需安裝 LibreOffice')
        if cat == 'doc' and not SOFFICE: note.append('轉 PDF 與 .doc 需 LibreOffice')
        if cat == 'ebook' and not CALIBRE: note.append('MOBI／AZW3 需 Calibre；EPUB 可用')
        for e in exts:
            if e in UNSUPPORTED: note.append(f'{e.upper()}：{UNSUPPORTED[e]}')
        rows.append(dict(cat=CAT_ZH[cat], key=cat, inputs=exts, outputs=outs, engine=engine, note='；'.join(note)))
    return rows
