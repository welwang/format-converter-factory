import os, sys, json, threading, base64, subprocess
import webview
import engine as E
import tools as T
import capture as C

SETTINGS = os.path.join(E.data_dir(), 'settings.json')
VERSION = '2.0.0'
EDITION = '試用版'                 # free, no time limit, no locked features - just labelled like WinRAR / 7-Zip style freeware
TITLE = f'轉檔工廠（{EDITION}）'
DEFAULTS = dict(theme='auto', preset='balanced', out_mode='source', out_dir='', hwaccel=True, fastcopy=True, loudnorm=False, workers=0,
                finish='sound', watch=[], tool_opts={}, rec={}, dl={}, tab='convert')

def res(p):
    b = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(b, p)

class Api:
    def __init__(self):
        self._s = dict(DEFAULTS)
        try: self._s.update(json.load(open(SETTINGS, encoding='utf-8-sig')))
        except Exception: pass
        self._eng = E.Engine(int(self._s.get('workers') or 0) or E.auto_workers())
        self._win = None
        self.pending_shutdown = False
        threading.Thread(target=E.detect_hw, daemon=True).start()
        self._rec = C.Recorder(self._eng); self._dl = C.Downloader(self._eng)
        self._watch = C.Watcher(self); self._watch.set_rules(self._s.get('watch'))
        self._fin = C.Finisher(self)
        threading.Thread(target=C.hotkey_loop, args=(self._hotkey,), daemon=True).start()

    def base_opt(self):
        s = self._s
        return dict(preset=s.get('preset', 'balanced'), hwaccel=s.get('hwaccel', True), fastcopy=s.get('fastcopy', True),
                    out_dir=s.get('out_dir') if s.get('out_mode') == 'custom' else '')

    # ---------- tools
    def tools_schema(self): return T.schema()

    def tool_files(self, paths, tool):
        acc = T.TOOL[tool]['accept']
        return [d for d in self.describe(paths) if d['cat'] in acc]

    def run_tool(self, tool, paths, params):
        t = T.TOOL[tool]
        opt = dict(self.base_opt(), **(params or {}))
        self._s.setdefault('tool_opts', {})[tool] = {k: v for k, v in (params or {}).items() if k not in ('rect',)}
        self.save_settings({})
        return self._eng.submit_tool(tool, paths, opt, t['name'], together=bool(t.get('together')), heavy=tool in T.HEAVY)

    def pick_file(self, filt=''):
        ft = (filt,) if filt else ()
        try: r = self._win.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=ft + ('所有檔案 (*.*)',))
        except Exception: r = self._win.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
        return r[0] if r else ''

    def preview(self, path, t=None):
        """A frame (video) or the picture itself, as a data URL plus its real pixel size, for the rectangle picker."""
        cat, ext = E.classify(path)
        if cat == 'image':
            from PIL import Image
            im = T.open_img(path); W, H = im.size; im = E.flatten(im); im.thumbnail((1280, 1280))
            import io; b = io.BytesIO(); im.save(b, 'JPEG', quality=85)
            return dict(src='data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode(), w=W, h=H, dur=0)
        i = E.probe_info(path); d = i['dur']; t = d * 0.3 if t is None else float(t)
        r = subprocess.run([E.FFMPEG, '-hide_banner', '-v', 'error', '-ss', f'{max(0, min(t, d - 0.1)):.2f}', '-i', path, '-frames:v', '1',
                            '-vf', ','.join(E.hdr_filters(path) + ['scale=1280:-2']), '-f', 'image2pipe', '-c:v', 'mjpeg', '-q:v', '4', '-'], capture_output=True, creationflags=E.NOWIN)
        return dict(src='data:image/jpeg;base64,' + base64.b64encode(r.stdout).decode(), w=i['width'], h=i['height'], dur=d)

    def drives(self): return T.list_drives()

    # ---------- recorder / downloader / watcher
    def rec_info(self): return dict(audio=C.audio_devices(), monitors=monitors_safe(), opts=self._s.get('rec') or {})
    def rec_start(self, o):
        self._s['rec'] = o; self.save_settings({})
        jid = self._rec.start(dict(self.base_opt(), **o))
        if o.get('minimize', True):
            try: self._win.minimize()
            except Exception: pass
        return jid
    def rec_stop(self):
        jid = self._rec.stop()
        try: self._win.restore()
        except Exception: pass
        return jid
    def rec_state(self): return self._rec.state()
    def _hotkey(self):
        if self._rec.state().get('rec'): self.rec_stop()

    def dl_start(self, urls, o):
        self._s['dl'] = o; self.save_settings({})
        return self._dl.start(urls, dict(self.base_opt(), **o))
    def dl_update(self): return self._dl.update()
    def dl_ready(self): return bool(C.ytdlp())

    def watch_get(self): return self._s.get('watch') or []
    def watch_set(self, rules):
        self._s['watch'] = rules; self.save_settings({}); self._watch.set_rules(rules); return True

    def cancel_shutdown(self):
        subprocess.Popen(['shutdown', '/a'], creationflags=E.NOWIN); self.pending_shutdown = False; return True

    def hwinfo(self):
        names = {'h264_nvenc': 'NVIDIA NVENC', 'h264_qsv': 'Intel QSV', 'h264_amf': 'AMD AMF'}
        return None if E._HW is None or E._HW_BUSY else [names[h] for h in E._HW]

    def init(self):
        hw = E._HW if (E._HW is not None and not E._HW_BUSY) else []
        names = {'h264_nvenc': 'NVIDIA NVENC', 'h264_qsv': 'Intel QSV', 'h264_amf': 'AMD AMF'}
        pc = dict(cores=os.cpu_count() or 0, ram=round(E.mem_gb(), 1), low=E.low_end())
        return dict(version=VERSION, edition=EDITION, pc=pc, settings=self._s, hw=[names[h] for h in hw], ffmpeg=bool(E.FFMPEG), office=bool(E.SOFFICE), tools=T.schema(), ytdlp=bool(C.ytdlp()))

    def save_settings(self, s):
        self._s.update({k: v for k, v in (s or {}).items() if k != 'watch'})   # watch rules are owned by watch_set
        try:                                   # write-then-rename: a crash or power cut never leaves a half-written settings file
            tmp = SETTINGS + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as fh: json.dump(self._s, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, SETTINGS)
        except Exception: pass
        return True

    # ---------- job actions
    def retry(self, jid):
        r = self._eng.retry(jid)
        if r == 'dl':
            old = self._eng.jobs[jid]; ids = self._dl.start(old.files[0], old.opt)
            with self._eng.lock:
                if jid in self._eng.order: self._eng.order.remove(jid)
            return ids[0]
        return r
    def open_file(self, path):
        if path and os.path.exists(path):
            try: os.startfile(path)
            except Exception: self.reveal(path)
        return True
    def open_doc(self, name):
        p = os.path.join(E.base_dir(), {'license': '授權說明.md', 'guide': '使用說明.md', 'eula': '使用授權條款.md'}.get(name, ''))
        if os.path.isfile(p):
            try: os.startfile(p)
            except Exception: self.reveal(p)
        return True
    def open_log(self):
        d = E.log_dir()
        try: os.startfile(d)
        except Exception: pass
        return d
    def media_info(self, paths):
        """Duration / resolution / HDR for the file lists (video and audio only)."""
        out = {}
        for p in (paths or [])[:300]:
            if E.classify(p)[0] in ('video', 'audio'):
                i = E.probe_info(p); out[p] = dict(dur=i['dur'], w=i['width'], h=i['height'], hdr=i.get('hdr', ''), a=i['acodec'])
        return out

    def describe(self, paths):
        out = []
        for p in E.expand(paths):
            cat, ext = E.classify(p)
            try: size = os.path.getsize(p)
            except Exception: size = 0
            out.append(dict(path=p, name=os.path.basename(p), cat=cat, ext=ext, size=size,
                            targets=E.targets_for(cat, ext), suggest=E.suggest(cat, ext), note=E.UNSUPPORTED.get(ext, '')))
        return out

    def pick_files(self):
        r = self._win.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        return self.describe(list(r or []))

    def pick_folder(self, purpose='add'):
        r = self._win.create_file_dialog(webview.FOLDER_DIALOG)
        if not r: return None
        if purpose == 'out': return r[0]
        return self.describe([r[0]])

    def start(self, items, opt, merge=False):
        ids = []
        if merge:
            groups = {}
            for it in items: groups.setdefault(it['target'], []).append(it['path'])
            for t, fs in groups.items(): ids += self._eng.submit(fs, t, opt, merge=True)
        else:
            for it in items: ids += self._eng.submit([it['path']], it['target'], opt)
        return ids

    def formats(self): return E.format_table()
    def startup_files(self):
        return self.describe([a for a in sys.argv[1:] if os.path.exists(a)])
    def status(self): return dict(jobs=self._eng.status(), rec=self._rec.state(), shutdown=self.pending_shutdown)
    def cancel(self, jid): self._eng.cancel(jid); return True
    def cancel_all(self):
        for j in self._eng.status():
            if j['state'] in ('queued', 'running'): self._eng.cancel(j['id'])
        return True
    def clear_done(self): self._eng.clear_done(); return True
    def reveal(self, path):
        if path and os.path.exists(path):
            import subprocess
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
        return True

def monitors_safe():
    try: return C.monitors()
    except Exception: return [dict(idx=0, label='螢幕 1')]

def on_drop(e):
    files = e.get('dataTransfer', {}).get('files', [])
    paths = [f.get('pywebviewFullPath') for f in files if f.get('pywebviewFullPath')]
    if paths:
        api._win.evaluate_js(f'window.onDropped({json.dumps(api.describe(paths), ensure_ascii=False)}, {json.dumps(paths, ensure_ascii=False)})')

def bind(win):
    from webview.dom import DOMEventHandler
    win.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True)
    win.dom.document.events.drop += DOMEventHandler(on_drop, True, True)

api = None   # created in __main__ after the single-instance check
PIPE = r'\\.\pipe\ZhuanDangGongChang-' + (os.environ.get('USERNAME') or 'user')

def forward_to_running():
    """If 轉檔工廠 is already open, hand our files to it (and bring it to the front) instead of opening a 2nd window."""
    if os.name != 'nt': return False
    try:
        from multiprocessing.connection import Client
        c = Client(PIPE, family='AF_PIPE', authkey=b'zdgc'); c.send([os.path.abspath(a) for a in sys.argv[1:] if os.path.exists(a)]); c.close()
        return True
    except Exception:
        return False

def serve_instances():
    if os.name != 'nt': return
    from multiprocessing.connection import Listener
    try: lst = Listener(PIPE, family='AF_PIPE', authkey=b'zdgc')
    except Exception: return
    while True:
        try:
            c = lst.accept(); paths = c.recv(); c.close()
        except Exception:
            continue
        w = api._win
        try:
            w.restore(); w.show()
            if os.name == 'nt': ctypes_foreground()
        except Exception: pass
        if paths:
            try: w.evaluate_js(f'window.onDropped({json.dumps(api.describe(paths), ensure_ascii=False)}, {json.dumps(paths, ensure_ascii=False)})')
            except Exception: pass

def ctypes_foreground():
    import ctypes
    u = ctypes.windll.user32
    h = u.FindWindowW(None, api._win.title) if api._win else 0
    if h: u.ShowWindow(h, 9); u.SetForegroundWindow(h)

def monitor():
    """Window title shows overall progress; the PC does not go to sleep mid-conversion; the taskbar button flashes when done."""
    import time
    was = False; sleep_blocked = False
    while True:
        time.sleep(1)
        try:
            jobs = api._eng.status(); act = [j for j in jobs if j['state'] in ('queued', 'running')]
            busy = bool(act)
            if busy:
                p = sum(j['progress'] for j in act) / len(act)
                title = f'{p * 100:.0f}% · {len(act)} 個工作 — {TITLE}'
            else: title = TITLE
            if api._win and api._win.title != title:
                try: api._win.set_title(title)
                except Exception: pass
            if os.name == 'nt':
                import ctypes
                if busy and not sleep_blocked: ctypes.windll.kernel32.SetThreadExecutionState(0x80000001); sleep_blocked = True
                elif not busy and sleep_blocked: ctypes.windll.kernel32.SetThreadExecutionState(0x80000000); sleep_blocked = False
                if was and not busy:
                    u = ctypes.windll.user32; h = u.FindWindowW(None, TITLE)
                    if h and u.GetForegroundWindow() != h:
                        class FW(ctypes.Structure): _fields_ = [('cbSize', ctypes.c_uint), ('hwnd', ctypes.c_void_p), ('dwFlags', ctypes.c_uint), ('uCount', ctypes.c_uint), ('dwTimeout', ctypes.c_uint)]
                        fw = FW(ctypes.sizeof(FW), h, 0x3 | 0xC, 0, 0); u.FlashWindowEx(ctypes.byref(fw))   # FLASHW_ALL | FLASHW_TIMERNOFG
            was = busy
        except Exception:
            pass

def win_geometry():
    """Fit the window to the usable screen area (taskbar excluded), in logical pixels, so it also works on
    1366x768 laptops at 125 % scaling. Saved size/position is reused only if it still fits."""
    g = api._s.get('win') or {}
    W, H, ox, oy = 1366, 728, 0, 0
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT(); ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)   # SPI_GETWORKAREA
        try: k = ctypes.windll.user32.GetDpiForSystem() / 96
        except Exception: k = 1.0
        W, H, ox, oy = (r.right - r.left) / k, (r.bottom - r.top) / k, r.left / k, r.top / k
    except Exception:
        pass
    dw, dh = min(1240, int(W * 0.94)), min(820, int(H * 0.94))
    w = int(g.get('w') or dw); h = int(g.get('h') or dh)
    w = max(min(w, int(W)), min(900, int(W))); h = max(min(h, int(H)), min(560, int(H)))
    x, y = g.get('x'), g.get('y')
    if x is None or y is None or not (ox - 20 <= x <= ox + W - 200 and oy - 10 <= y <= oy + H - 100):
        x, y = int(ox + (W - w) / 2), int(oy + (H - h) / 2)
    return w, h, x, y

def remember(**kw):
    g = dict(api._s.get('win') or {}); g.update(kw); api._s['win'] = g

WV2_ID = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
def webview2_ok():
    """Edge WebView2 runtime (the window engine). Built into Windows 11 and updated Windows 10."""
    if os.name != 'nt': return True
    import winreg
    for root, sub in ((winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\' + WV2_ID),
                      (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\' + WV2_ID),
                      (winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\EdgeUpdate\\Clients\\' + WV2_ID)):
        try:
            with winreg.OpenKey(root, sub) as k:
                v = winreg.QueryValueEx(k, 'pv')[0]
                if v and v != '0.0.0.0': return True
        except OSError: continue
    return False

def ensure_webview2():
    """Never depend on what the PC happens to have: use the installed runtime, else a private copy in
    tools\\webview2 (Fixed Version runtime), else offer the bundled installer."""
    if webview2_ok(): return True
    fixed = E.bundled('webview2')
    if os.path.isfile(os.path.join(fixed, 'msedgewebview2.exe')):
        os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER'] = fixed; return True
    import ctypes
    setup = E.bundled('MicrosoftEdgeWebview2Setup.exe')
    msg = ('轉檔工廠的視窗需要 Microsoft Edge WebView2 執行環境（Windows 11 已內建），這台電腦目前沒有。\n\n'
           + ('按「確定」立即安裝（約 1 分鐘，需要網路），完成後會自動開啟轉檔工廠。' if os.path.isfile(setup) else '請到 https://go.microsoft.com/fwlink/p/?LinkId=2124703 下載安裝後再開啟。'))
    r = ctypes.windll.user32.MessageBoxW(None, msg, TITLE, 0x41 if os.path.isfile(setup) else 0x30)
    if r == 1 and os.path.isfile(setup):
        subprocess.run([setup, '/silent', '/install'])
        return webview2_ok()
    return False

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--selftest':
        import selftest
        selftest.main(sys.argv[2] if len(sys.argv) > 2 else None); sys.exit(0)
    if forward_to_running(): sys.exit(0)
    if not ensure_webview2(): sys.exit(1)
    api = Api()
    import threading as _t
    _t.Thread(target=serve_instances, daemon=True).start()
    _t.Thread(target=monitor, daemon=True).start()
    w, h, x, y = win_geometry()
    api._win = webview.create_window(TITLE, url=res('ui/index.html'), js_api=api, width=w, height=h, x=x, y=y,
                                    min_size=(900, 560), background_color='#F5F5F7')
    try:
        api._win.events.resized += lambda width, height: remember(w=width, h=height)
        api._win.events.moved += lambda x, y: remember(x=x, y=y)
        api._win.events.closing += lambda: api.save_settings({})
    except Exception: pass
    webview.start(bind, api._win, gui='edgechromium', private_mode=True, debug=False)
    api.save_settings({})
