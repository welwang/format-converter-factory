import os, sys, json, threading, base64, subprocess
import webview
import engine as E
import tools as T
import capture as C

SETTINGS = os.path.join(E.base_dir(), 'settings.json')
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
                            '-vf', 'scale=1280:-2', '-f', 'image2pipe', '-c:v', 'mjpeg', '-q:v', '4', '-'], capture_output=True, creationflags=E.NOWIN)
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
        return dict(settings=self._s, hw=[names[h] for h in hw], ffmpeg=bool(E.FFMPEG), office=bool(E.SOFFICE), tools=T.schema(), ytdlp=bool(C.ytdlp()))

    def save_settings(self, s):
        self._s.update({k: v for k, v in (s or {}).items() if k != 'watch'})   # watch rules are owned by watch_set
        try: json.dump(self._s, open(SETTINGS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        except Exception: pass
        return True

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

api = Api()
def selftest(d):
    import time
    log = open(os.path.join(d, 'selftest.log'), 'w', encoding='utf-8')
    log.write(f'ffmpeg={E.FFMPEG}\nsoffice={E.SOFFICE}\ncalibre={E.CALIBRE}\npandoc={E.PANDOC}\n7z={E.SEVENZIP}\nhw={E.detect_hw()}\n')
    J = lambda f: os.path.join(d, f)
    cases = [(['v.mp4'], 'mkv', dict(hwaccel=True)), (['v.mp4'], 'mp4', dict(hwaccel=False, height=720)),
             (['v.mp4'], 'mp4', dict(hwaccel=True, height=720)), (['v.mp4'], 'webm', {}), (['v.mp4'], 'gif', dict(trim_start=0, trim_end=3)),
             (['v.mp4'], 'mp3', {}), (['v.mp4'], 'mp4', dict(target_mb=2)),
             (['a.wav'], 'flac', {}), (['a.wav'], 'opus', {}), (['a.wav'], 'm4a', {}),
             (['i.png'], 'webp', {}), (['i.png'], 'avif', {}), (['i.png'], 'ico', {}), (['i.png'], 'jpg', dict(target_mb=0.1)), (['i.heic'], 'jpg', {}),
             (['i.png', 'i2.png'], 'pdf', {}), (['p.pdf'], 'png', {}), (['t.txt'], 'pdf', {}),
             (['p.pdf'], 'txt', {}), (['d.md'], 'docx', {}), (['d.md'], 'html', {}), (['d.md'], 'epub', {}), (['d.docx'], 'pdf', {}), (['d.docx'], 'md', {}),
             (['b.epub'], 'docx', {}), (['s.csv'], 'xlsx', {}), (['s.csv'], 'pdf', {}), (['x.zip'], 'extract', {}), (['x.tar.gz'], 'extract', {}),
             (['x.zip'], '7z', {}), (['v.mkv'], 'mp4', dict(fastcopy=True)), (['a.wav'], 'mp3', dict(loudnorm=True)), (['b.epub'], 'mobi', {}), (['b.epub'], 'azw3', {}), (['x.docx'], 'pdf', {}), (['x.doc'], 'pdf', {}), (['x.xls'], 'xlsx', {}), (['x.ppt'], 'pdf', {}), (['c.srt'], 'vtt', {}), (['c.srt'], 'ass', {}), (['m.stl'], 'glb', {}), (['m.stl'], 'obj', {}),
             (['g.svg'], 'png', {}), (['k.psd'], 'jpg', {}), (['r.dng'], 'jpg', {}), (['z.kfx'], 'epub', {})]
    eng = E.Engine(1, 1)
    for fs, t, o in cases:
        fs = [J(f) for f in fs]
        if not all(os.path.exists(f) for f in fs): log.write(f'SKIP {fs}\n'); continue
        ids = eng.submit(fs, t, o, merge=len(fs) > 1)
        while any(eng.jobs[i].state in ('queued', 'running') for i in ids): time.sleep(0.1)
        for i in ids:
            j = eng.jobs[i]; sz = os.path.getsize(j.output) if j.output and os.path.isfile(j.output) else 0
            log.write(f'{j.state}\t{os.path.basename(fs[0])}->{t}\t{o}\t{j.elapsed:.2f}s\t{j.encoder}\t{sz}\t{j.msg}\n'); log.flush()
    ids = eng.submit([J('v.mp4'), J('v.mp4')], 'mp4', dict(height=480), merge=True)
    while any(eng.jobs[i].state in ('queued', 'running') for i in ids): time.sleep(0.1)
    j = eng.jobs[ids[0]]; log.write(f'{j.state}\tmerge 2x\t{j.elapsed:.2f}s\t{j.msg}\n')
    ids = eng.submit([J('v.mp4')], 'mkv', dict(hwaccel=False, preset='high', height=1080, fastcopy=False))
    time.sleep(1.5); eng.cancel(ids[0]); time.sleep(1); log.write(f'cancel test: {eng.jobs[ids[0]].state}\n'); log.close()

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--selftest':
        selftest(sys.argv[2]); sys.exit(0)
    api._win = webview.create_window('轉檔工廠', url=res('ui/index.html'), js_api=api, width=1240, height=820,
                                    min_size=(980, 640), background_color='#F4F6FA')
    webview.start(bind, api._win, gui='edgechromium', private_mode=True, debug=False)
