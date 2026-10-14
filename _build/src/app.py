import os, sys, json, threading, base64, subprocess, copy, uuid
# The window belongs to the C program (四維八德.exe); this module is the engine's API behind it.
OPEN_DIALOG, FOLDER_DIALOG, SAVE_DIALOG = 'open', 'folder', 'save'
import engine as E
import tools as T
import capture as C
import workflows as W
import system_tools as ST
import disk_tools as DT
import file_actions as FA

SETTINGS = os.path.join(E.data_dir(), 'settings.json')
VERSION = '2.3.0'
EDITION = '開源版'
TITLE = f'四維八德（{EDITION}）'
DEFAULTS = dict(theme='auto', preset='balanced', out_mode='source', out_dir='', hwaccel=True, fastcopy=True, loudnorm=False, workers=0,
                finish='sound', watch=[], tool_opts={}, rec={}, dl={}, tab='workflow', flow_profiles=[], codec='auto', verify_full=False, resource_mode='auto')

def res(p):
    b = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(b, p)

class Api:
    def __init__(self):
        self._s = copy.deepcopy(DEFAULTS); self._settings_lock = threading.RLock()
        try: self._s.update(json.load(open(SETTINGS, encoding='utf-8-sig')))
        except Exception: pass
        self._s = W.clean_settings(self._s)
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
                    out_dir=s.get('out_dir') if s.get('out_mode') == 'custom' else '', codec=s.get('codec', 'auto'), verify_full=s.get('verify_full', False), resource_mode=s.get('resource_mode', 'auto'))

    def workflow_schema(self): return dict(recipes=W.RECIPES, profiles=self._s.get('flow_profiles') or [])

    def system_info(self): return dict(hardware=ST.hardware_info(), cleanup=ST.CLEANUP)

    def disk_info(self): return DT.inventory()

    def disk_preview(self, mode, source, destination, group, recovery_mode):
        if self._eng.busy(): raise ValueError('請先完成目前工作，避免同時存取要檢查或修復的磁碟')
        self._disk_plan = DT.plan(mode, source, destination, group, recovery_mode)
        return {k:v for k,v in self._disk_plan.items() if k!='command'}

    def disk_launch(self, token, confirmed):
        if self._eng.busy(): raise ValueError('請先完成目前工作')
        if not getattr(self, '_disk_plan', None): raise ValueError('請先預覽磁碟操作')
        result=DT.launch(self._disk_plan, token, confirmed);self._disk_plan=None
        return result

    def disk_help(self, kind):
        import webbrowser
        webbrowser.open(DT.HELP.get(kind,DT.HELP['check']));return True

    def system_test(self):
        return self._eng.submit_tool('hardware_test', ['電腦硬體'], dict(resource_mode='quiet', out_dir=os.path.join(E.data_dir(), 'hardware-tests')), '電腦硬體短測', heavy=True)

    def cleanup_scan(self, categories):
        if self._eng.busy(): raise ValueError('請先完成或停止進行中的工作，再掃描清理')
        self._cleanup_plan = ST.scan_cleanup(categories)
        return ST.cleanup_preview(self._cleanup_plan)

    def cleanup_execute(self, token):
        if self._eng.busy(): raise ValueError('有工作正在執行，請稍後重新掃描')
        if not getattr(self, '_cleanup_plan', None): raise ValueError('請先掃描清理項目')
        result = ST.execute_cleanup(self._cleanup_plan, token); self._cleanup_plan = None
        return result

    def workflow_run(self, recipe, paths, params):
        paths = list(dict.fromkeys(E.expand(paths)))
        if not paths: raise ValueError('請先加入可以處理的素材')
        params = params or {}
        W.valid_profile(dict(name='交付', recipe=recipe, options=params))
        opt = dict(self.base_opt(), **params); opt['recipe'] = recipe
        opt['out_dir'] = params.get('out_dir') or self.base_opt().get('out_dir') or ''
        return self._eng.submit_tool('workflow', paths, opt, next(r['name'] for r in W.RECIPES if r['id'] == recipe), together=True, heavy=True)

    def workflow_save(self, profile):
        value = W.valid_profile(profile)
        value['id'] = profile.get('id') or uuid.uuid4().hex
        profiles = [p for p in self._s.get('flow_profiles', []) if p.get('id') != value['id']]
        if len(profiles) >= 100: raise ValueError('最多保存 100 個配方')
        profiles.append(value); self._s['flow_profiles'] = profiles; self.save_settings({})
        return self.workflow_schema()

    def workflow_delete(self, pid):
        self._s['flow_profiles'] = [p for p in self._s.get('flow_profiles', []) if p.get('id') != pid]; self.save_settings({})
        return self.workflow_schema()

    def workflow_export(self, pid):
        profile = next((p for p in self._s.get('flow_profiles', []) if p.get('id') == pid), None)
        if not profile: raise ValueError('請先保存配方')
        paths = self._win.create_file_dialog(SAVE_DIALOG, save_filename='交付配方.zdgc.json', file_types=('交付配方 (*.json)',))
        if not paths: return ''
        path = paths[0] if isinstance(paths, (list, tuple)) else paths
        with open(path, 'w', encoding='utf-8') as fh: json.dump(dict(format='zdgc-workflow', version=1, profile=W.valid_profile(profile)), fh, ensure_ascii=False, indent=2)
        return path

    def workflow_import(self):
        path = self.pick_file('交付配方 (*.json)')
        if not path: return self.workflow_schema()
        if os.path.getsize(path) > 1024 * 1024: raise ValueError('配方檔案過大')
        with open(path, encoding='utf-8-sig') as fh: data = json.load(fh)
        if data.get('format') != 'zdgc-workflow' or data.get('version') != 1: raise ValueError('不支援的配方檔案')
        return self.workflow_save(W.valid_profile(data.get('profile')))

    # ---------- tools
    def tools_schema(self): return T.schema()

    def pdf_preview(self,path,page=1,pw=''):
        import pdf_tools
        return pdf_tools.preview(path,page,pw)

    def pdf_scan(self):
        if os.name!='nt':raise ValueError('掃描器擷取僅支援 Windows')
        destination=os.path.join(E.data_dir(),'掃描原圖');os.makedirs(destination,exist_ok=True)
        path=os.path.join(destination,'掃描_'+uuid.uuid4().hex[:12]+'.jpg')
        powershell=os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'System32','WindowsPowerShell','v1.0','powershell.exe')
        r=subprocess.run([powershell,'-NoProfile','-ExecutionPolicy','Bypass','-File',res('ui/scan.ps1'),'-Destination',path],capture_output=True,creationflags=E.NOWIN)
        if r.returncode or not os.path.isfile(path):raise ValueError('未取得掃描圖片，請確認掃描器與驅動程式，或改用匯入圖片')
        return self.describe([path])

    def pdf_html(self,text):
        if not isinstance(text,str) or len(text)>2*1024*1024:raise ValueError('HTML 內容過大')
        if not text.strip():raise ValueError('請貼上 HTML 內容')
        root=os.path.join(E.data_dir(),'HTML原稿');os.makedirs(root,exist_ok=True)
        path=os.path.join(root,'文件_'+uuid.uuid4().hex[:12]+'.html')
        with open(path,'w',encoding='utf-8') as f:f.write(text)
        return self.describe([path])

    def tool_files(self, paths, tool):
        acc = T.TOOL[tool]['accept']
        return [d for d in self.describe(paths) if d['cat'] in acc]

    def run_tool(self, tool, paths, params):
        t = T.TOOL[tool]
        if len(paths)<t.get('min_files',2 if t.get('together') else 1):raise ValueError('加入的檔案數不足')
        if t.get('max_files') and len(paths)!=t['max_files']:raise ValueError(f'請加入 {t["max_files"]} 個檔案')
        if tool in ('p_edit','p_sign','p_redact','p_forms'):
            import pdf_tools
            params=dict(params or {});params['actions']=pdf_tools.safe_actions(params.get('actions'))
        opt = dict(self.base_opt(), **(params or {}))
        self._s.setdefault('tool_opts', {})[tool] = W.clean_settings({k: v for k, v in (params or {}).items() if k not in ('rect','actions','pfx')})
        self.save_settings({})
        return self._eng.submit_tool(tool, paths, opt, t['name'], together=bool(t.get('together')), heavy=tool in T.HEAVY)

    def pick_file(self, filt=''):
        ft = (filt,) if filt else ()
        try: r = self._win.create_file_dialog(OPEN_DIALOG, allow_multiple=False, file_types=ft + ('所有檔案 (*.*)',))
        except Exception: r = self._win.create_file_dialog(OPEN_DIALOG, allow_multiple=False)
        return r[0] if r else ''

    def preview(self, path, t=None):
        """A frame (video) or the picture itself, as a data URL plus its real pixel size, for the rectangle picker."""
        cat, ext = E.classify(path)
        if cat == 'image':
            from PIL import Image
            real = []
            def want(w, h): real[:] = [w, h]; return 1280 / max(w, h)     # decode big JPEGs pre-shrunk, report the true size
            im = T.open_img(path, want); W, H = real or im.size; im = E.flatten(im); im.thumbnail((1280, 1280))
            import io; b = io.BytesIO(); im.save(b, 'JPEG', quality=85)
            return dict(src='data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode(), w=W, h=H, dur=0)
        i = E.probe_info(path); d = i['dur']; t = d * 0.3 if t is None else float(t)
        r = subprocess.run([E.FFMPEG, '-hide_banner', '-v', 'error', '-ss', f'{max(0, min(t, d - 0.1)):.2f}', '-i', path, '-frames:v', '1',
                            '-vf', ','.join(E.hdr_filters(path) + ['scale=1280:-2']), '-f', 'image2pipe', '-c:v', 'mjpeg', '-q:v', '4', '-'], capture_output=True, creationflags=E.NOWIN)
        return dict(src='data:image/jpeg;base64,' + base64.b64encode(r.stdout).decode(), w=i['width'], h=i['height'], dur=d)

    def drives(self): return T.list_drives()

    def compare_job(self, jid):
        job = self._eng.jobs.get(jid)
        if not job or job.state not in ('done', 'partial'): raise ValueError('請先完成轉檔')
        if not os.path.isfile(job.output): raise ValueError('多檔案成品請開啟交付資料夾')
        if any(E.classify(p)[0] not in ('image', 'video') for p in (job.files[0], job.output)):
            raise ValueError('目前可預覽圖片及影片畫面')
        return dict(before=self.preview(job.files[0]), after=self.preview(job.output), name=os.path.basename(job.output), validation=job.validation)

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
        pc = dict(E.platform_info(), low=E.low_end())
        return dict(version=VERSION, edition=EDITION, pc=pc, settings=self._s, hw=[names[h] for h in hw], ffmpeg=bool(E.FFMPEG), office=bool(E.SOFFICE), tools=T.schema(), ytdlp=bool(C.ytdlp()), workflows=self.workflow_schema(), missing=E.missing_components())

    def save_settings(self, s):
        with self._settings_lock:
            self._s.update({k: v for k, v in (s or {}).items() if k not in ('watch', 'flow_profiles')})
            self._s = W.clean_settings(self._s)
            tmp = SETTINGS + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as fh: json.dump(self._s, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, SETTINGS)
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
        return FA.open_file(path)
    def open_doc(self, name):
        document = {'license': '授權說明.md', 'guide': '使用說明.md', 'eula': '使用授權條款.md', 'tests': '測試報告.html'}.get(name)
        if not document: raise ValueError('不支援的說明文件')
        return FA.open_file(os.path.join(E.base_dir(), document))
    def open_log(self):
        d = E.log_dir()
        try: os.startfile(d)
        except Exception: pass
        return d
    def media_info(self, paths):
        """Duration / resolution / HDR for the file lists (video and audio only)."""
        # each probe is a separate ffmpeg process that mostly waits on the disk: run several at once
        paths = [p for p in (paths or []) if E.classify(p)[0] in ('video', 'audio')]
        if not paths: return {}
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max(1, min(6, len(paths), os.cpu_count() or 2))) as ex:
            infos = list(ex.map(E.probe_info, paths))
        return {p: dict(dur=i['dur'], w=i['width'], h=i['height'], hdr=i.get('hdr', ''), a=i['acodec']) for p, i in zip(paths, infos)}

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
        r = self._win.create_file_dialog(OPEN_DIALOG, allow_multiple=True)
        return self.describe(list(r or []))

    def pick_folder(self, purpose='add'):
        r = self._win.create_file_dialog(FOLDER_DIALOG)
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
    def monitor_state(self):
        """What the C program needs every second for the title bar, sleep prevention and finish actions."""
        with self._eng.lock:
            act = [dict(id=j.id, progress=j.info()['progress']) for j in (self._eng.jobs[i] for i in self._eng.order) if j.state in ('queued', 'running')]
            recent = [dict(id=j.id,state=j.state,created=j.created,output=j.output or '') for j in (self._eng.jobs[i] for i in self._eng.order[-150:])]
        return dict(active=act,recent=recent,finish=self._s.get('finish', 'sound'),shutdown=self.pending_shutdown,rec=bool(self._rec.state().get('rec')))

    def job_states(self, ids):
        return {i: (self._eng.jobs[i].state if i in self._eng.jobs else self._eng.outcomes.get(i, '')) for i in ids or []}

    def status(self):
        active = self._eng.counts()
        return dict(jobs=self._eng.status(tail=150), active=active, busy=active > 0, rec=self._rec.state(), shutdown=self.pending_shutdown, finish=self._s.get('finish', 'sound'))
    def cancel(self, jid):
        if self._rec.job and self._rec.job.id == jid: self.rec_stop()
        else: self._eng.cancel(jid)
        return True
    def cancel_all(self):
        for j in self._eng.status():
            if j['state'] in ('queued', 'running'): self._eng.cancel(j['id'])
        return True
    def clear_done(self): self._eng.clear_done(); return True

    def close(self):
        self._watch.stop_event.set(); self._fin.stop_event.set()
        if self._rec.state().get('rec'): self._rec.stop()
        self._eng.shutdown(); self.save_settings({})
    def reveal(self, path):
        return FA.reveal(path)

def monitors_safe():
    try: return C.monitors()
    except Exception: return [dict(idx=0, label='螢幕 1')]

api = None   # set by core.py

def monitor():
    """Window title shows overall progress; the PC does not go to sleep mid-conversion; the taskbar button flashes when done."""
    import time
    was = False; sleep_blocked = False; shown = TITLE
    while True:
        time.sleep(1)
        try:
            jobs = api._eng.status(); act = [j for j in jobs if j['state'] in ('queued', 'running')]
            busy = bool(act)
            title = f'{sum(j["progress"] for j in act) / len(act) * 100:.0f}% · {len(act)} 個工作 — {TITLE}' if busy else TITLE
            if api._win and title != shown:
                api._win.set_title(title); shown = title
            if os.name == 'nt':
                import ctypes
                if busy and not sleep_blocked: ctypes.windll.kernel32.SetThreadExecutionState(0x80000001); sleep_blocked = True
                elif not busy and sleep_blocked: ctypes.windll.kernel32.SetThreadExecutionState(0x80000000); sleep_blocked = False
            if was and not busy and api._win: api._win.flash()
            was = busy
        except Exception:
            pass

if __name__ == '__main__':
    import core
    sys.exit(core.main())
