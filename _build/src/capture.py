"""四維八德: screen recorder, web video downloader, watched folders, finish actions."""
import os, re, sys, json, time, shutil, subprocess, threading, zipfile, urllib.request
import engine as E
import file_actions as FA

NOWIN = E.NOWIN

def downloads_dir():
    d = os.path.join(os.path.expanduser('~'), 'Downloads')
    return d if os.path.isdir(d) else os.path.expanduser('~')

def videos_dir():
    d = os.path.join(os.path.expanduser('~'), 'Videos')
    return d if os.path.isdir(d) else os.path.expanduser('~')

# ====================================================================== screen recorder
def audio_devices():
    """DirectShow audio capture devices (microphones, 'Stereo Mix' if enabled)."""
    if not E.FFMPEG or os.name != 'nt': return []
    r = E.run([E.FFMPEG, '-hide_banner', '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy'])
    out = []
    for line in r.stderr.splitlines():
        m = re.search(r'"([^"]+)" \(audio\)', line)
        if m: out.append(m.group(1))
    return out

def monitors():
    if os.name != 'nt': return [dict(idx=0, label='螢幕 1')]
    import ctypes
    n = max(1, ctypes.windll.user32.GetSystemMetrics(80))
    return [dict(idx=i, label=f'螢幕 {i + 1}' + ('（主螢幕）' if i == 0 else '')) for i in range(n)]

class Recorder:
    def __init__(self, eng):
        self.eng = eng; self.job = None; self.proc = None; self.t0 = 0; self.lock = threading.Lock()

    def state(self):
        j = self.job
        if not j or j.state != 'running': return dict(rec=False)
        return dict(rec=True, sec=int(time.time() - self.t0), size=os.path.getsize(self.tmp) if os.path.exists(self.tmp) else 0, id=j.id)

    def _cmd(self, o, out, mode, hw):
        fps = int(o.get('fps') or 30)
        c = [E.FFMPEG, '-hide_banner', '-y', '-v', 'error']
        region = o.get('region') or ''
        if mode == 'dda':
            args = f"ddagrab=output_idx={int(o.get('monitor') or 0)}:framerate={fps}:draw_mouse={1 if o.get('mouse', True) else 0}"
            if region:
                x, y, w, h = [int(v) for v in region.split(',')]; args += f':offset_x={x}:offset_y={y}:video_size={w // 2 * 2}x{h // 2 * 2}'
            c += ['-f', 'lavfi', '-i', args]
            vf = 'hwdownload,format=bgra,format=yuv420p'
        else:
            c += ['-f', 'gdigrab', '-framerate', str(fps), '-draw_mouse', '1' if o.get('mouse', True) else '0']
            if region:
                x, y, w, h = [int(v) for v in region.split(',')]; c += ['-offset_x', str(x), '-offset_y', str(y), '-video_size', f'{w // 2 * 2}x{h // 2 * 2}']
            c += ['-i', 'desktop']; vf = 'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p'
        mics = [m for m in (o.get('audio') or []) if m]
        for m in mics: c += ['-rtbufsize', '256M', '-f', 'dshow', '-audio_buffer_size', '50', '-i', f'audio={m}']
        fc = f'[0:v]{vf}[v]'
        if len(mics) > 1: fc += ';' + ''.join(f'[{i + 1}:a]' for i in range(len(mics))) + f'amix=inputs={len(mics)}:normalize=0[a]'
        c += ['-filter_complex', fc, '-map', '[v]'] + (['-map', '1:a'] if len(mics) == 1 else ['-map', '[a]'] if mics else [])
        q = {'high': 20, 'balanced': 24, 'small': 28}[o.get('preset', 'balanced')]
        enc = hw[0] if hw else 'libx264'
        if enc == 'h264_nvenc': c += ['-c:v', enc, '-preset', 'p4', '-rc', 'vbr', '-cq', str(q), '-b:v', '0']
        elif enc == 'h264_qsv': c += ['-c:v', enc, '-preset', 'faster', '-global_quality', str(q)]
        elif enc == 'h264_amf': c += ['-c:v', enc, '-quality', 'speed', '-rc', 'cqp', '-qp_i', str(q), '-qp_p', str(q)]
        else: c += ['-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency', '-crf', str(q)]
        c += ['-g', str(fps * 2), '-c:a', 'aac', '-b:a', '160k', out]
        return c, enc

    def start(self, o):
        with self.lock:
            if self.job and self.job.state == 'running': raise RuntimeError('已經在錄影中')
            if not E.FFMPEG: raise RuntimeError('找不到 ffmpeg')
            folder = o.get('out_dir') or videos_dir(); os.makedirs(folder, exist_ok=True)
            name = time.strftime('螢幕錄影_%Y%m%d_%H%M%S')
            self.tmp = os.path.join(folder, name + '.mkv')          # MKV survives crashes / power loss
            self.final = E.unique_path(os.path.join(folder, name + '.mp4'))
            j = E.Job([self.final], 'mp4', o, tool='rec', label='螢幕錄影'); j.state = 'running'; j.started = time.time(); j.output = self.final
            hw = E.detect_hw() if o.get('hwaccel', True) else []
            last_err = ''
            for mode in (['dda', 'gdi'] if os.name == 'nt' else ['gdi']):
                for h in ([hw[:1], []] if hw else [[]]):
                    cmd, enc = self._cmd(o, self.tmp, mode, h)
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=NOWIN)
                    time.sleep(1.2)
                    if p.poll() is None:
                        self.proc = p; j.encoder = ('桌面複製 ' if mode == 'dda' else 'GDI ') + enc
                        self.job = j; self.t0 = time.time(); j.proc = p
                        self.eng.add_external(j)
                        threading.Thread(target=self._watch, daemon=True).start()
                        return j.id
                    last_err = p.stderr.read().decode('utf-8', 'replace')
                    p.stdin.close(); p.stderr.close()
            import tools
            raise RuntimeError('無法開始錄影：' + tools.ff_error(last_err))

    def _watch(self):
        j = self.job
        while self.proc and self.proc.poll() is None:
            el = int(time.time() - self.t0); j.speed = f'錄影中 {el // 60:02d}:{el % 60:02d}'
            try: j.msg = f'{os.path.getsize(self.tmp) / 1048576:.1f} MB'
            except OSError: pass
            time.sleep(0.5)
        if j.state == 'running': self.stop()      # cancelled from the queue, or ffmpeg ended on its own (disk full...)

    def stop(self):
        with self.lock:
            p, j = self.proc, self.job
            if not p or not j: return None
            try: p.stdin.write(b'q'); p.stdin.flush()
            except Exception: pass
            try: p.wait(15)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
            p.stdin.close(); p.stderr.close()
            self.proc = None
            j.elapsed = time.time() - j.started; j.speed = ''
            if j.cancelled:
                j.state = 'cancelled'; j.msg = '已取消'
                try: os.remove(self.tmp)
                except OSError: pass
                return j.id
            # remux MKV -> MP4 (instant, no re-encode); keep the MKV if anything goes wrong
            r = E.run([E.FFMPEG, '-hide_banner', '-y', '-v', 'error', '-i', self.tmp, '-map', '0', '-c', 'copy', '-movflags', '+faststart', self.final])
            if r.returncode == 0 and os.path.getsize(self.final) > 0:
                os.remove(self.tmp); j.output = self.final
            else:
                j.output = self.tmp
            j.state = 'done'; j.progress = 1.0; j.msg = '完成'; j.eta = 0; j.measure()
            return j.id

def hotkey_loop(callback, vk=0x78, mods=0x0002 | 0x0004):
    """Ctrl+Shift+F9 global hotkey (Windows). Calls callback() on press."""
    if os.name != 'nt': return
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    if not u.RegisterHotKey(None, 0x5A47, mods | 0x4000, vk): return    # MOD_NOREPEAT
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == 0x0312:
            try: callback()
            except Exception: pass

# ====================================================================== downloader (yt-dlp)
def ytdlp():
    return E.find_tool('yt-dlp')

def deno():
    p = E.bundled('deno.exe')
    return p if os.path.isfile(p) else None

def ensure_deno(j):
    """YouTube needs a JavaScript runtime; Deno ships in tools\\ (nothing is downloaded at run time)."""
    return deno()

QUALITY = {
    'best_compat': ['-f', 'bv*[vcodec^=avc1][height<=2160]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b', '--merge-output-format', 'mp4'],
    'best': ['-f', 'bv*+ba/b', '--merge-output-format', 'mp4/mkv'],
    '1080': ['-f', 'bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]', '--merge-output-format', 'mp4'],
    '720': ['-f', 'bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]', '--merge-output-format', 'mp4'],
    'mp3': ['-f', 'ba/b', '-x', '--audio-format', 'mp3', '--audio-quality', '0'],
    'm4a': ['-f', 'ba[ext=m4a]/ba/b', '-x', '--audio-format', 'm4a'],
}

class Downloader:
    def __init__(self, eng):
        self.eng = eng

    def start(self, urls, o):
        exe = ytdlp()
        if not exe: raise RuntimeError('缺少下載元件 yt-dlp（tools 資料夾）')
        urls = [u.strip() for u in re.split(r'[\s]+', urls or '') if re.match(r'https?://', u.strip())]
        if not urls: raise RuntimeError('請貼上影片網址（http 開頭）')
        ids = []
        for u in urls:
            j = E.Job([u], 'download', o, tool='dl', label='下載'); j.state = 'queued'
            self.eng.add_external(j); ids.append(j.id)
            threading.Thread(target=self._run, args=(j, u, o, exe), daemon=True).start()
        return ids

    _slots = threading.Semaphore(3)

    def _run(self, j, url, o, exe):
        with self._slots:
            if j.cancelled: j.state = 'cancelled'; j.msg = '已取消'; return
            j.state = 'running'; j.started = time.time()
            try: self._dl(j, url, o, exe)
            except InterruptedError: j.state = 'cancelled'; j.msg = '已取消'
            except Exception as e: j.state = 'error'; j.msg = str(e)[:300]; E.log_error(j)
            j.elapsed = time.time() - j.started
            if j.state != 'done': j.measure()

    def _dl(self, j, url, o, exe):
        folder = o.get('out_dir') or downloads_dir(); os.makedirs(folder, exist_ok=True)
        q = o.get('quality', 'best_compat')
        cmd = [exe, '--newline', '--no-colors', '--encoding', 'utf-8', '--ignore-config', '--no-mtime', '--ffmpeg-location', os.path.dirname(E.FFMPEG) if E.FFMPEG else '',
               '-P', folder, '-o', '%(title).120B [%(id)s].%(ext)s', '--windows-filenames', '--progress-template',
               'download:ZDGC %(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s|%(info.title)s',
               '--print', 'after_move:ZDGCFILE %(filepath)j', '--no-simulate', '--retries', '5', '--fragment-retries', '5', '-N', '4']
        cmd += QUALITY.get(q, QUALITY['best_compat'])
        if not o.get('playlist'): cmd += ['--no-playlist']
        if o.get('subs'): cmd += ['--write-subs', '--sub-langs', 'zh-Hant,zh-TW,zh.*,en.*', '--convert-subs', 'srt']
        if o.get('thumb') and q in ('mp3', 'm4a'): cmd += ['--embed-thumbnail', '--embed-metadata']
        if re.search(r'youtu\.?be', url):
            d = ensure_deno(j)
            if d: cmd += ['--js-runtimes', f'deno:{d}']
        cmd.append(url)
        files = []; err = []
        child_env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
        j.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', env=child_env, creationflags=E.LOWPRI)
        th = threading.Thread(target=lambda: err.extend(j.proc.stderr.readlines()), daemon=True); th.start()
        part = 0
        for line in j.proc.stdout:
            line = line.rstrip()
            if line.startswith('ZDGC '):
                pct, sp, eta, title = (line[5:].split('|') + ['', '', '', ''])[:4]
                try:
                    p = float(pct.strip().rstrip('%')) / 100
                    if p < j.progress - 0.5: part += 1           # next stream (video -> audio) started
                    j.progress = min(0.99, p)
                except ValueError: pass
                j.speed = sp.strip() if sp.strip() not in ('NA', 'Unknown') else ''
                m = re.match(r'(\d+):(\d+)(?::(\d+))?', eta.strip())
                if m: j.eta = int(m.group(1)) * 60 + int(m.group(2)) if not m.group(3) else int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                if title and title != 'NA': j.label = '下載：' + title[:40]
            elif line.startswith('ZDGCFILE '):
                completed=FA.completed_path(line,folder)
                if completed and completed not in files:files.append(completed);j.output=completed
            elif '[Merger]' in line or '[ExtractAudio]' in line:
                j.speed = '合併影音中…' if 'Merger' in line else '轉成音訊中…'
        j.proc.wait(); th.join(2)
        if j.cancelled: raise InterruptedError
        if j.proc.returncode != 0 and not files:
            msg = next((l.strip() for l in err if 'ERROR' in l), (err[-1].strip() if err else '下載失敗'))
            msg = re.sub(r'^ERROR:\s*', '', msg)
            hint = ''
            if 'Sign in' in msg or 'login' in msg.lower() or 'private' in msg.lower(): hint = '（需要登入或是私人影片）'
            elif 'Unsupported URL' in msg: hint = '（不支援這個網站）'
            elif 'HTTP Error 403' in msg or 'nsig' in msg or 'Requested format is not available' in msg: hint = '（網站改版，請按「更新下載元件」後再試）'
            raise RuntimeError(msg[:220] + hint)
        if not files: raise RuntimeError('下載元件沒有回報可開啟的完成檔案，請檢查儲存資料夾；已保留下載內容')
        j.encoder = 'yt-dlp' + (f'（{len(files)} 個檔案）' if len(files) > 1 else '')
        if len(files) > 1: j.output = os.path.dirname(files[0])
        if j.proc.returncode != 0:
            j.state = 'partial'; j.msg = '部分完成：部分影片下載失敗，已保留成功檔案'; j._err = ''.join(err); E.log_error(j)
        else:
            j.state = 'done'; j.msg = '完成'
        j.progress = 1.0; j.eta = 0; j.speed = ''; j.measure()

    def update(self):
        exe = ytdlp()
        if not exe: raise RuntimeError('缺少 yt-dlp')
        r = E.run([exe, '-U'], timeout=180)
        txt = (r.stdout + r.stderr).strip().splitlines()
        return txt[-1] if txt else ('完成' if r.returncode == 0 else '更新失敗')

# ====================================================================== watched folders
class Watcher:
    """Polls rule folders; converts new files once they stop growing. Never touches the originals."""
    def __init__(self, api):
        self.api = api; self.rules = []; self.seen = {}; self.sizes = {}; self.lock = threading.RLock(); self.stop_event = threading.Event()
        self.state_file = os.path.join(E.data_dir(), 'watch_state.json')
        try: self.seen = json.load(open(self.state_file, encoding='utf-8'))
        except Exception: self.seen = {}
        threading.Thread(target=self._loop, daemon=True).start()

    def set_rules(self, rules):
        with self.lock: self.rules = [r for r in rules or [] if r.get('folder') and r.get('on', True)]
        # first sight of a rule: existing files count as "already there" unless the rule asks to include them
        for r in self.rules:
            key = r['folder']
            if key not in self.seen:
                stats = {}; files = self._list(r, stats)
                self.seen[key] = {} if r.get('existing') else {p: dict(sig=list(stats[p]), state='done') for p in files}
        self._save()

    def _list(self, r, stats=None):
        """Files to consider, via os.scandir: on Windows size and date come with the directory listing, so a
        folder of thousands of files is checked every 4 s without one extra disk query per file."""
        out = []; folder = r['folder']; skip = os.path.normcase(os.path.abspath(self._out(r)))
        if stats is None: stats = {}
        if not os.path.isdir(folder): return out
        todo = [folder]
        while todo:
            root = todo.pop()
            if self._inside(root, skip): continue
            try: entries = list(os.scandir(root))
            except OSError: continue
            for e in sorted(entries, key=lambda e: e.name):
                try:
                    if e.is_dir(follow_symlinks=False):
                        if r.get('recursive'): todo.append(e.path)
                        continue
                    f = e.name
                    if not e.is_file() or not E.classify(f)[0] or f.startswith(('~$', '.')) or f.endswith(('.part', '.tmp', '.crdownload')): continue
                    st = e.stat(); stats[e.path] = (st.st_size, st.st_mtime); out.append(e.path)
                except OSError: continue
        return out

    @staticmethod
    def _inside(path, parent):
        try: return os.path.commonpath([os.path.normcase(os.path.abspath(path)), parent]) == parent
        except ValueError: return False

    def _out(self, r): return r.get('out_dir') or os.path.join(r['folder'], '已轉檔')

    def _save(self):
        try:
            with self.lock:
                with open(self.state_file + '.tmp', 'w', encoding='utf-8') as fh: json.dump(self.seen, fh, ensure_ascii=False)
                os.replace(self.state_file + '.tmp', self.state_file)
        except Exception: pass

    def _loop(self):
        while not self.stop_event.wait(4):
            try: self._tick()
            except Exception: pass

    def _tick(self):
        with self.lock: rules = list(self.rules)
        changed = False
        for r in rules:
            seen = self.seen.setdefault(r['folder'], {}); stats = {}
            for p in self._list(r, stats):
                sz = stats[p]
                entry = seen.get(p)
                if entry == 1: seen[p] = dict(sig=list(sz), state='done'); changed = True; continue
                if entry and entry.get('state') == 'pending':
                    job = self.api._eng.jobs.get(entry.get('job'))
                    if job and job.state in ('queued', 'running'): continue
                    finished = job.state if job else self.api._eng.outcomes.get(entry.get('job'))
                    entry['state'] = 'done' if finished == 'done' else 'error'
                    entry['retry_at'] = time.time() + 60; changed = True
                if entry and entry.get('sig') == list(sz):
                    if entry.get('state') == 'done': continue
                    if time.time() < entry.get('retry_at', 0) or entry.get('attempts', 0) >= 3: continue
                if self.sizes.get(p) != sz: self.sizes[p] = sz; continue      # still being written / copied
                cat, ext = E.classify(p)
                t = r.get('target') or 'auto'
                if t == 'auto': t = E.suggest(cat, ext)
                if not t or t not in E.targets_for(cat, ext): seen[p] = dict(sig=list(sz), state='done'); changed = True; continue
                opt = dict(self.api.base_opt(), out_dir=self._out(r))
                if r.get('preset'): opt['preset'] = r['preset']
                ids = self.api._eng.submit([p], t, opt)
                attempts = entry.get('attempts', 0) if entry and entry.get('sig') == list(sz) else 0
                seen[p] = dict(sig=list(sz), state='pending', job=ids[0], attempts=attempts + 1); changed = True
        if changed: self._save()

# ====================================================================== finish actions
class Finisher:
    def __init__(self, api): self.api = api; self.was_busy = False; self.batch = set(); self.stop_event = threading.Event(); threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self.stop_event.wait(2):
            busy = self.api._eng.busy()
            if busy: self.batch.update(j['id'] for j in self.api._eng.status() if j['state'] in ('queued', 'running'))
            if self.was_busy and not busy: self._fire()
            self.was_busy = busy

    def _fire(self):
        act = self.api._s.get('finish', 'sound')
        batch = [self.api._eng.jobs[i] for i in self.batch if i in self.api._eng.jobs]
        self.batch.clear()
        if act in ('shutdown', 'sleep') and (not batch or any(j.state != 'done' for j in batch)):
            self.api._s['finish'] = 'sound'
            return
        if act in ('sound', 'shutdown', 'sleep') and os.name == 'nt':
            try:
                import winsound; winsound.MessageBeep(0x40)
            except Exception: pass
        if act == 'shutdown' and os.name == 'nt':
            subprocess.Popen(['shutdown', '/s', '/t', '120', '/c', '四維八德：工作完成，2 分鐘後關機。要取消請在四維八德按「取消關機」。'], creationflags=NOWIN)
            self.api._s['finish'] = 'sound'; self.api.pending_shutdown = True
        elif act == 'sleep' and os.name == 'nt':
            self.api._s['finish'] = 'sound'
            subprocess.Popen(['rundll32.exe', 'powrprof.dll,SetSuspendState', '0,1,0'], creationflags=NOWIN)
        elif act == 'open':
            jobs = [j for j in self.api._eng.status() if j['state'] == 'done' and j['output']]
            if jobs: self.api.reveal(jobs[-1]['output'])
