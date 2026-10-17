"""四維八德 AI 智慧工具（全部離線）：智慧剪輯、精華剪輯、自動章節、智慧封面、智慧挑照片、自動去黑邊、
平台響度校正、智慧命名、畫質目標壓縮；另提供一般轉檔的「智慧建議」與工具搜尋的白話指令解析。

只使用隨附的 FFmpeg／whisper／Qwen3（tools 資料夾）與 Pillow／numpy，不呼叫任何雲端服務。
每個工具都是 tools.TOOLS 的一筆描述＋RUN 的一個函式，所以介面表單、工作佇列、取消、重試與輸出檢查
跟其他工具完全相同；C++ 的 run_tool 不認得這些 id，會整包轉交 Python。
"""
import os, re, json, math, time, shutil, subprocess, threading, csv
from concurrent.futures import ThreadPoolExecutor
import engine as E

class _Tools:
    """tools.py loads this module at its end; import it lazily so either module can be imported first."""
    def __getattr__(self, name):
        import tools
        return getattr(tools, name)
T = _Tools()

def F(k, label, type='number', default=None, **kw):
    d = dict(k=k, label=label, type=type, default=default); d.update(kw); return d

LANGS = [['auto', '自動偵測'], ['zh', '中文'], ['en', '英文'], ['ja', '日文'], ['ko', '韓文'], ['yue', '粵語'], ['th', '泰文'], ['vi', '越南文'], ['id', '印尼文'], ['fr', '法文'], ['de', '德文'], ['es', '西班牙文']]
AUDIO_OUT = [['same', '跟原檔相同'], ['mp3', 'MP3'], ['m4a', 'M4A'], ['flac', 'FLAC'], ['wav', 'WAV'], ['opus', 'Opus']]
GROUP = ['smart', 'AI 智慧工具']

PLATFORMS = [['youtube', 'YouTube／Spotify／一般影片（-14 LUFS）'], ['apple', 'Apple Podcasts／Apple Music（-16 LUFS）'],
             ['podcast', 'Podcast／有聲書（-18 LUFS）'], ['broadcast', '電視廣播 EBU R128（-23 LUFS）'], ['film', '影院／串流對白（-27 LUFS）']]
LOUD = {'youtube': (-14, -1.0), 'apple': (-16, -1.0), 'podcast': (-18, -1.5), 'broadcast': (-23, -1.0), 'film': (-27, -2.0)}
QUALITY = [['0.985', '幾乎看不出差異（SSIM 0.985）'], ['0.975', '高畫質（SSIM 0.975，建議）'], ['0.96', '省空間（SSIM 0.96）']]

TOOLS = [
    dict(id='s_jumpcut', group='smart', icon='scissors', name='智慧剪輯：去除停頓', desc='自動判斷音量門檻，剪掉說話之間的空白與停頓（影片、錄音都可用）', accept=['video', 'audio'], fields=[
        F('auto', '自動判斷靜音門檻（依這段錄音的音量）', 'check', True), F('db', '靜音門檻（dB）', 'number', -40, min=-80, max=-10, show={'auto': False}),
        F('min', '停頓超過幾秒才剪', 'number', 0.6, min=0.2, max=10, step=0.1), F('pad', '每段前後保留（秒）', 'number', 0.15, min=0, max=2, step=0.05),
        F('fmt', '音訊輸出格式', 'select', 'same', options=AUDIO_OUT)]),
    dict(id='s_highlight', group='smart', icon='sparkles', name='AI 精華剪輯', desc='依聲音起伏與畫面變化挑出精華片段，自動剪成短片（可直接出直式）', accept=['video'], fields=[
        F('length', '精華總長度（秒）', 'number', 30, min=5, max=600), F('clip', '每段長度（秒）', 'number', 4, min=1, max=30, step=0.5),
        F('ratio', '畫面', 'select', 'same', options=[['same', '跟原影片相同'], ['9:16', '9:16 直式短影音（模糊背景）'], ['1:1', '1:1 方形（模糊背景）']])]),
    dict(id='s_chapters', group='smart', icon='list', name='AI 自動章節', desc='離線聽打後依話題轉換切章節、寫章節標題，輸出 YouTube 章節並內嵌到影片', accept=['video', 'audio'], fields=[
        F('lang', '語言', 'select', 'zh', options=LANGS), F('model', '辨識模型', 'select', 'base', options=[['base', '離線快速（已內建）']]),
        F('trad', '轉成繁體中文', 'check', True), F('count', '章節數（0＝自動）', 'number', 0, min=0, max=30),
        F('mode', '章節標題', 'select', 'ai', options=[['ai', '離線 AI 撰寫（較慢）'], ['extract', '快速摘錄關鍵句']]),
        F('embed', '把章節內嵌到影片（不重新編碼）', 'check', True)]),
    dict(id='s_bestframe', group='smart', icon='frames', name='智慧封面', desc='掃描整支影片，挑出最清晰、曝光最好、不重複的畫面當封面', accept=['video'], fields=[
        F('count', '要幾張候選', 'number', 5, min=1, max=20), F('fmt', '格式', 'select', 'jpg', options=[['jpg', 'JPG'], ['png', 'PNG']]),
        F('faces', '偏好畫面中央有主體', 'check', True)]),
    dict(id='s_photocull', group='smart', icon='image', name='智慧挑照片', desc='找出模糊、過暗過亮與連拍重複的照片，每組留最好的一張（只複製，不動原檔）', accept=['image'], together=True, min_files=2, fields=[
        F('sim', '相似照片判定', 'select', 'normal', options=[['strict', '嚴格（幾乎一樣才算）'], ['normal', '一般（連拍、同一場景）'], ['loose', '寬鬆（構圖相近就算）']]),
        F('blur', '模糊判定', 'select', 'normal', options=[['strict', '嚴格'], ['normal', '一般'], ['loose', '寬鬆']]),
        F('copy_all', '其餘照片也分類複製（模糊／曝光不佳／相似）', 'check', True)]),
    dict(id='s_autocrop', group='smart', icon='crop', name='自動去黑邊', desc='偵測並裁掉影片上下左右的黑邊（電影、翻錄、直式轉橫式常見）', accept=['video'], fields=[
        F('limit', '黑色判定（越大越積極）', 'number', 24, min=4, max=80)]),
    dict(id='s_loudness', group='smart', icon='volume', name='平台響度校正', desc='先量測再校正（兩段式 EBU R128），讓音量符合 YouTube、Podcast、廣播規範', accept=['audio', 'video'], fields=[
        F('target', '目標平台', 'select', 'youtube', options=PLATFORMS), F('fmt', '輸出格式', 'select', 'same', options=AUDIO_OUT)]),
    dict(id='s_smartname', group='smart', icon='tag', name='智慧命名', desc='依拍攝時間、相機、PDF 標題、歌曲資訊批次命名副本，附對照表', accept=['image', 'video', 'audio', 'pdf'], together=True, min_files=1, fields=[
        F('style', '命名方式', 'select', 'date_info', options=[['date_info', '日期_時間_相機或標題'], ['date', '日期_時間'], ['info', '標題或歌手 - 歌名'], ['prefix_seq', '自訂前綴＋日期排序編號']]),
        F('prefix', '前綴', 'text', '', show={'style': 'prefix_seq'}), F('month', '依月份分資料夾', 'check', False)]),
    dict(id='s_quality', group='smart', icon='sliders', name='畫質目標壓縮', desc='先試壓樣本、量測畫質（SSIM），自動找出畫質達標的最小檔案', accept=['video'], fields=[
        F('target', '畫質目標', 'select', '0.975', options=QUALITY), F('codec', '編碼', 'select', 'h264', options=[['h264', 'H.264（相容性最好）'], ['hevc', 'H.265／HEVC（更小，較慢）']]),
        F('height', '畫面高度', 'select', '0', options=[['0', '原始'], ['2160', '2160'], ['1440', '1440'], ['1080', '1080'], ['720', '720']])]),
]
HEAVY = {'s_jumpcut', 's_highlight', 's_chapters', 's_bestframe', 's_autocrop', 's_quality'}
SPEECH = {'s_chapters'}

# ---------------------------------------------------------------- shared helpers
def analyze_cmd(src, *a):
    """ffmpeg for measuring passes: info log level (the detect filters print there), progress on stdout."""
    return [E.FFMPEG, '-hide_banner', '-nostdin', '-progress', 'pipe:1', '-nostats', '-i', src] + list(a)

def an_error(err):
    """Analysis passes run at info log level: keep only the lines that report a problem."""
    lines = [l for l in (err or '').splitlines() if re.search(r'error|invalid|could not|cannot|unable|no such|denied|not found|failed', l, re.I)]
    return T.ff_error('\n'.join(lines) if lines else (err or '').strip().splitlines()[-1:][0] if (err or '').strip() else '')

def merge_ranges(ranges, gap=0.0):
    out = []
    for a, b in sorted(ranges):
        if b <= a: continue
        if out and a <= out[-1][1] + gap: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out

def select_expr(ranges):
    return '+'.join(f'between(t,{a:.3f},{b:.3f})' for a, b in ranges)

def cut_filters(ranges):
    e = select_expr(ranges)
    return f"select='{e}',setpts=N/FRAME_RATE/TB", f"aselect='{e}',asetpts=N/SR/TB"

def limit_ranges(ranges, most=300):
    """Very long recordings: merge the closest pieces so the select expression stays fast."""
    ranges = [list(r) for r in ranges]
    while len(ranges) > most:
        k = min(range(len(ranges) - 1), key=lambda i: ranges[i + 1][0] - ranges[i][1])
        ranges[k][1] = ranges[k + 1][1]; del ranges[k + 1]
    return ranges

def fmt_time(t):
    t = int(round(t)); h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'

def need_media(src, video=False):
    T.need_ff()
    i = T.info(src)
    if i['dur'] <= 0: raise RuntimeError('無法讀取影音長度，檔案可能損毀')
    if video and not T.has_video(src): raise RuntimeError('這個檔案沒有影像')
    return i

# ---------------------------------------------------------------- 1 智慧剪輯：去除停頓
def mean_volume(eng, j, src, base=0.0, span=0.1):
    eng._exec(j, analyze_cmd(src, '-vn', '-af', 'volumedetect', '-f', 'null', '-'), T.info(src)['dur'], base=base, span=span)
    m = re.search(r'mean_volume:\s*(-?[\d.]+) dB', j._err or '')
    return float(m.group(1)) if m else None

def auto_threshold(mean_db):
    """Speech sits ~15–20 dB above the pauses between words; clamp so silence in quiet files is still found."""
    if mean_db is None: return -40.0
    return max(-60.0, min(-25.0, mean_db - 17.0))

def silences(eng, j, src, db, mind, base=0.1, span=0.25):
    eng._exec(j, analyze_cmd(src, '-vn', '-af', f'silencedetect=n={db}dB:d={mind}', '-f', 'null', '-'), T.info(src)['dur'], base=base, span=span)
    if j._rc != 0: raise RuntimeError('分析聲音失敗：' + an_error(j._err))
    st = [float(x) for x in re.findall(r'silence_start:\s*(-?[\d.]+)', j._err)]
    en = [float(x) for x in re.findall(r'silence_end:\s*([\d.]+)', j._err)]
    return st, en

def keep_ranges(dur, starts, ends, pad):
    sil = []
    for k, s in enumerate(starts):
        e = ends[k] if k < len(ends) else dur
        s, e = max(0.0, s + pad), min(dur, e - pad)
        if e - s > 0.05: sil.append((s, e))
    keep, cur = [], 0.0
    for s, e in sil:
        if s > cur: keep.append([cur, s])
        cur = max(cur, e)
    if cur < dur: keep.append([cur, dur])
    return merge_ranges([r for r in keep if r[1] - r[0] >= 0.08], 0.02)

def t_jumpcut(eng, j, o):
    src = j.files[0]; i = need_media(src)
    if not T.has_audio(src): raise RuntimeError('檔案裡沒有聲音，無法判斷停頓')
    dur = i['dur']; mind = max(0.2, T.num(o, 'min', 0.6)); pad = max(0.0, T.num(o, 'pad', 0.15))
    if o.get('auto', True):
        j.msg = '分析音量'; db = auto_threshold(mean_volume(eng, j, src))
    else: db = T.num(o, 'db', -40)
    j.msg = '尋找停頓'; st, en = silences(eng, j, src, db, mind)
    keep = limit_ranges(keep_ranges(dur, st, en, pad))
    kept = sum(b - a for a, b in keep)
    if not keep or kept <= 0.3: raise RuntimeError('整段幾乎都是靜音，請改用手動門檻（調低 dB）')
    if dur - kept < 0.5: raise RuntimeError(f'沒有找到超過 {mind:g} 秒的停頓（門檻 {db:.0f} dB），不需要剪輯')
    vf, af = cut_filters(keep)
    if T.has_video(src) and o.get('fmt', 'same') == 'same':
        T.video_tool(eng, j, src, '_去停頓', vf=[vf], af=[af], dur=kept, base=0.35, span=0.65)
    else:
        T.audio_tool(eng, j, src, '_去停頓', [af], ext=T.aext(src, o) if T.has_video(src) else None, dur=kept)
    cuts = len(keep) - 1 + (keep[0][0] > 0.05) + (keep[-1][1] < dur - 0.05)
    j.notes = [f'剪掉 {cuts} 處停頓，共 {dur - kept:.1f} 秒（{(dur - kept) / dur * 100:.0f}%）；{fmt_time(dur)} → {fmt_time(kept)}',
               f'靜音門檻 {db:.0f} dB{"（自動判斷）" if o.get("auto", True) else ""}，停頓超過 {mind:g} 秒才剪，每段前後保留 {pad:g} 秒']
    j.encoder = (j.encoder or 'FFmpeg') + f' · 剪掉 {dur - kept:.0f} 秒'

# ---------------------------------------------------------------- 2 AI 精華剪輯
def media_curves(eng, j, src, dur, base=0.0, span=0.5):
    """Per-second loudness (RMS dB) and scene-change times in one decoding pass."""
    tmp = T.tmpdir()
    try:
        audio = T.has_audio(src); parts = ["[0:v:0]scale=256:-2,select='gt(scene\\,0.28)',metadata=print:file=scene.txt[v]"]
        maps = ['-map', '[v]', '-f', 'null', '-']
        if audio:
            parts.append('[0:a:0]aresample=8000,asetnsamples=n=4000:p=0,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=rms.txt[a]')
            maps += ['-map', '[a]', '-f', 'null', '-']
        eng._exec(j, analyze_cmd(src, '-filter_complex', ';'.join(parts), *maps), dur, cwd=tmp, base=base, span=span)
        if j._rc != 0: raise RuntimeError('分析影片失敗：' + an_error(j._err))
        def read(name):
            p = os.path.join(tmp, name)
            return open(p, encoding='utf-8', errors='replace').read() if os.path.isfile(p) else ''
        scenes = [float(x) for x in re.findall(r'pts_time:([\d.]+)', read('scene.txt'))]
        rms = {}; txt = read('rms.txt'); t = None
        for line in txt.splitlines():
            m = re.search(r'pts_time:([\d.]+)', line)
            if m: t = float(m.group(1)); continue
            m = re.search(r'RMS_level=(-?[\d.]+|-inf)', line)
            if m and t is not None:
                v = -90.0 if 'inf' in m.group(1) else float(m.group(1)); rms[int(t * 2)] = max(-90.0, v)
        return rms, scenes
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def pick_highlights(dur, rms, scenes, length, clip):
    """Score every window, pick the best non-overlapping ones, return them in time order."""
    clip = max(1.0, min(clip, dur)); want = max(1, int(math.ceil(min(length, dur) / clip)))
    if dur <= length: return [[0.0, dur]]
    vals = sorted(rms.values())
    lo = vals[len(vals) // 10] if vals else -60.0; hi = vals[-1] if vals else -10.0
    norm = lambda v: 0.0 if hi - lo < 1 else max(0.0, min(1.0, (v - lo) / (hi - lo)))
    step = clip / 2; cands = []
    t = min(dur * 0.02, 2.0)                      # skip the very first frames (logos, black)
    while t + clip <= dur - min(dur * 0.02, 1.0) + 1e-6:
        half = [rms[k] for k in range(int(t * 2), int((t + clip) * 2)) if k in rms]
        loud = sum(norm(v) for v in half) / len(half) if half else 0.0
        peak = max((norm(v) for v in half), default=0.0)
        cuts = sum(1 for s in scenes if t <= s < t + clip)
        motion = min(1.0, cuts / 2.0)
        score = 0.55 * loud + 0.25 * peak + 0.2 * motion
        cands.append((score, t)); t += step
    if not cands: return [[0.0, min(dur, length)]]
    chosen = []
    for score, t in sorted(cands, reverse=True):
        if all(abs(t - c) >= clip for c in chosen): chosen.append(t)
        if len(chosen) >= want: break
    return [[t, min(dur, t + clip)] for t in sorted(chosen)]

def t_highlight(eng, j, o):
    src = j.files[0]; i = need_media(src, video=True); dur = i['dur']
    length = max(5.0, T.num(o, 'length', 30)); clip = max(1.0, T.num(o, 'clip', 4))
    if dur <= length + 1: raise RuntimeError(f'影片只有 {dur:.0f} 秒，比精華長度還短')
    j.msg = '分析聲音與畫面'; rms, scenes = media_curves(eng, j, src, dur)
    keep = pick_highlights(dur, rms, scenes, length, clip); total = sum(b - a for a, b in keep)
    vsel, asel = cut_filters(keep); audio = T.has_audio(src); ratio = o.get('ratio', 'same')
    if ratio in ('9:16', '1:1'):
        H = 1920 if ratio == '9:16' else 1080; W = T.even(H * T.ratio_of(ratio))
        fc, _ = T.fill_graph(W, H, 20, False)
        fc = fc.replace('[0:v]', f'[0:v:0]{vsel},', 1)
        maps = ['[v]']
        if audio: fc += f';[0:a:0]{asel}[aout]'; maps.append('[aout]')
        T.video_tool(eng, j, src, '_精華' + ('_直式' if ratio == '9:16' else '_方形'), fc=fc, maps=maps, dur=total, base=0.5, span=0.5)
    else:
        T.video_tool(eng, j, src, '_精華', vf=[vsel], af=[asel], dur=total, base=0.5, span=0.5)
    j.notes = ['精華片段：' + '、'.join(f'{fmt_time(a)}–{fmt_time(b)}' for a, b in keep),
               '依聲音大小、聲音高峰與畫面切換挑選；運動、演講、活動紀錄效果最好，請自行確認內容。']
    j.encoder = (j.encoder or 'FFmpeg') + f' · {len(keep)} 段 {total:.0f} 秒'

# ---------------------------------------------------------------- 3 AI 自動章節
WORD = re.compile(r'[A-Za-z]{3,}|[一-鿿]{2}')

def _bag(text):
    from collections import Counter
    return Counter(w.lower() for w in WORD.findall(text))

def _cos(a, b):
    if not a or not b: return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values())); nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0

def chapter_starts(cues, dur, count=0):
    """TextTiling-style: boundaries where the speech pauses AND the words before/after differ most."""
    if not cues: return [0.0]
    n = int(count) if count else max(3 if dur >= 180 else 2, min(15, int(round(dur / 180.0))))
    if dur < 90 or len(cues) < 6: n = min(n, 2 if dur >= 40 else 1)
    if n <= 1: return [0.0]
    min_len = max(20.0, dur / (n * 2.5))
    window = 60.0
    cands = []
    for k in range(1, len(cues)):
        t = cues[k][0]
        if t < min_len or dur - t < min_len * 0.6: continue
        gap = max(0.0, cues[k][0] - cues[k - 1][1])
        before = ' '.join(c[2] for c in cues if t - window <= c[0] < t)
        after = ' '.join(c[2] for c in cues if t <= c[0] < t + window)
        shift = 1.0 - _cos(_bag(before), _bag(after))
        cands.append((0.6 * shift + 0.4 * min(1.0, gap / 2.0), t))
    starts = [0.0]
    for score, t in sorted(cands, reverse=True):
        if all(abs(t - s) >= min_len for s in starts): starts.append(t)
        if len(starts) >= n: break
    return sorted(starts)

def extract_title(text, limit=16, whole=''):
    """The sentence near the start of the chapter whose words are most specific to this chapter."""
    from collections import Counter
    sentences = [s.strip(' ，,、') for s in re.split(r'(?<=[。！？.!?])\s*|\n', text) if len(s.strip()) >= 4]
    if not sentences: return text.strip()[:limit] or '段落'
    local = Counter(w.lower() for w in WORD.findall(text)); total = Counter(w.lower() for w in WORD.findall(whole or text))
    def score(k, s):
        ws = WORD.findall(s.lower())
        spec = sum(local[w] / (total[w] or 1) for w in ws) / (len(ws) + 2)
        return spec * (1.0 - min(0.5, k / 40.0))          # topic sentences tend to come first
    best = max(enumerate(sentences[:40]), key=lambda x: score(*x))[1]
    best = re.sub(r'^(那|那麼|然後|所以|就是|接下來|最後|首先|今天|嗯|呃|好|OK|ok)[，, ]*', '', best)
    best = re.split(r'[，,、；;：:]', best)[0] if len(best) > limit else best
    return (best[:limit] + ('…' if len(best) > limit else '')) or '段落'

def clean_title(s, limit=24):
    s = re.sub(r'<think>.*?</think>', '', s or '', flags=re.S)
    s = s.strip().splitlines()[0] if s.strip() else ''
    s = re.sub(r'^(章節標題|標題|title)\s*[:：]\s*', '', s, flags=re.I).strip(' "「」『』*#-•　')
    return s[:limit]

def ffmeta_escape(s):
    return re.sub(r'([=;#\\\n])', r'\\\1', s)

def chapter_metadata(chapters, dur):
    lines = [';FFMETADATA1']
    for k, (t, title) in enumerate(chapters):
        end = chapters[k + 1][0] if k + 1 < len(chapters) else dur
        lines += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={int(t * 1000)}', f'END={int(end * 1000)}', 'title=' + ffmeta_escape(title)]
    return '\n'.join(lines) + '\n'

def t_chapters(eng, j, o):
    src = j.files[0]; i = need_media(src); dur = i['dur']
    mode = o.get('mode', 'ai')
    if mode == 'ai' and not T.ai_ok(): mode = 'extract'; T_warn = True
    else: T_warn = False
    text = T.whisper_srt(eng, j, src, o, 0.0, 0.6 if mode == 'ai' else 0.85)
    cues = T.srt_cues(text)
    if not cues: raise RuntimeError('沒有辨識到任何語音')
    starts = chapter_starts(cues, dur, int(T.num(o, 'count', 0)))
    chapters = []; whole = ' '.join(c[2] for c in cues)
    import pdf_local_engines as L
    for k, s in enumerate(starts):
        if j.cancelled: raise InterruptedError
        e = starts[k + 1] if k + 1 < len(starts) else dur + 1
        body = ' '.join(c[2] for c in cues if s <= c[0] < e)
        title = ''
        if mode == 'ai' and body.strip():
            j.encoder = f'AI 撰寫章節標題 {k + 1}/{len(starts)}'
            try: title = clean_title(L.generate(j, '以下是影片其中一段的逐字稿（語音辨識，可能有錯字）。請用繁體中文寫一個 4 到 14 個字的章節標題，概括這段在講什麼。只輸出標題本身。', body[:900], 40))
            except InterruptedError: raise
            except Exception as ex: E.log(f'chapter title AI failed: {ex}')
        chapters.append((s, title or extract_title(body, whole=whole) or f'第 {k + 1} 段'))
        j.progress = 0.6 + 0.3 * (k + 1) / len(starts)
    folder = T.out_dir_for(j, src, '_章節'); j.output = folder
    stem = os.path.splitext(os.path.basename(src))[0]
    yt = '\n'.join(f'{fmt_time(t)} {title}' for t, title in chapters)
    with open(os.path.join(folder, '章節（YouTube 說明欄）.txt'), 'w', encoding='utf-8') as fh: fh.write(yt + '\n')
    with open(os.path.join(folder, '逐字稿.srt'), 'w', encoding='utf-8-sig') as fh: fh.write(text)
    with open(os.path.join(folder, '章節.md'), 'w', encoding='utf-8') as fh:
        fh.write(f'# {stem} 章節\n\n' + '\n\n'.join(f'## {fmt_time(t)} {title}\n\n' + ' '.join(c[2] for c in cues if t <= c[0] < (chapters[k + 1][0] if k + 1 < len(chapters) else dur + 1))
                                                  for k, (t, title) in enumerate(chapters)) + '\n')
    ext = os.path.splitext(src)[1].lower().lstrip('.')
    if o.get('embed', True) and ext in ('mp4', 'mkv', 'mov', 'm4a', 'm4v', 'webm', 'mka', 'mp3', 'flac', 'opus', 'ogg'):
        meta = os.path.join(folder, 'chapters.ffmeta')
        with open(meta, 'w', encoding='utf-8') as fh: fh.write(chapter_metadata(chapters, dur))
        out = os.path.join(folder, f'{stem}_含章節.{ext}')
        c = [E.FFMPEG, '-hide_banner', '-nostdin', '-y', '-v', 'error', '-i', src, '-f', 'ffmetadata', '-i', meta,
             '-map', '0', '-map_metadata', '0', '-map_chapters', '1', '-c', 'copy']
        if ext in ('mp4', 'mov', 'm4a', 'm4v'): c += ['-movflags', '+faststart']
        try: eng._proc(j, c + [out], '內嵌章節')
        except InterruptedError: raise
        except Exception as ex:
            j.warnings.append('章節無法內嵌到這個格式，已另存章節文字檔'); E.log(f'chapter embed failed: {ex}')
            if os.path.isfile(out): os.remove(out)
        finally:
            try: os.remove(meta)
            except OSError: pass
    j.encoder = f'{len(chapters)} 個章節（' + ('whisper + llama.cpp 離線' if mode == 'ai' else 'whisper + 關鍵句摘錄') + '）'
    j.notes = ['YouTube 章節：把「章節（YouTube 說明欄）.txt」貼到影片說明欄即可（第一行必須是 00:00，至少 3 個章節、每章 10 秒以上）。',
               '語音辨識與章節標題可能有錯字，發布前請檢查。'] + (['沒有離線文字模型，改用快速摘錄關鍵句。'] if T_warn else [])

# ---------------------------------------------------------------- image scoring (shared by 智慧封面 / 智慧挑照片)
def gray_array(im, side=512):
    import numpy as np
    im = im.convert('L'); im.thumbnail((side, side))
    return np.asarray(im, dtype=np.float32)

def sharpness(g):
    """Edge crispness: the strongest Laplacian responses (99.5th percentile) relative to the picture's tonal range.
    Sharp photos score ~40–80, visibly blurry ones under ~15; a mostly flat but sharp picture still scores high."""
    import numpy as np
    if g.shape[0] < 3 or g.shape[1] < 3: return 0.0
    lap = np.abs(-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    rng = float(np.percentile(g, 99) - np.percentile(g, 1))
    return float(np.percentile(lap, 99.5)) / (rng + 10.0) * 100.0

def exposure(g):
    """(mean 0–255, share of clipped black, share of clipped white)"""
    import numpy as np
    n = g.size or 1
    return float(g.mean()), float((g < 8).sum()) / n, float((g > 247).sum()) / n

def colorfulness(im):
    import numpy as np
    a = np.asarray(im.convert('RGB').resize((96, 96)), dtype=np.float32)
    rg = a[..., 0] - a[..., 1]; yb = 0.5 * (a[..., 0] + a[..., 1]) - a[..., 2]
    return float(math.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * math.sqrt(rg.mean() ** 2 + yb.mean() ** 2))

def dhash(im, size=8):
    import numpy as np
    g = np.asarray(im.convert('L').resize((size + 1, size)), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    v = 0
    for b in bits: v = (v << 1) | int(b)
    return v

def hamming(a, b): return bin(a ^ b).count('1')

def center_weight(g):
    """How much of the detail sits in the middle third (subject in frame rather than an empty wall)."""
    import numpy as np
    h, w = g.shape
    if h < 9 or w < 9: return 0.5
    gy = np.abs(np.diff(g, axis=0))[:, :-1]; gx = np.abs(np.diff(g, axis=1))[:-1, :]; e = gx + gy
    tot = float(e.sum()) or 1.0
    mid = float(e[h // 3: 2 * h // 3, w // 3: 2 * w // 3].sum())
    return mid / tot

def frame_score(im, prefer_center=True):
    g = gray_array(im, 384); sh = sharpness(g); mean, black, white = exposure(g)
    expo = 1.0 - min(1.0, abs(mean - 120) / 120.0) - 1.5 * max(0, black - 0.25) - 1.5 * max(0, white - 0.15)
    contrast = min(1.0, float(g.std()) / 60.0)
    color = min(1.0, colorfulness(im) / 80.0)
    sh_n = min(1.0, sh / 60.0)
    score = 0.4 * sh_n + 0.25 * max(0.0, expo) + 0.15 * contrast + 0.1 * color + (0.1 * min(1.0, center_weight(g) * 2.5) if prefer_center else 0.1)
    if mean < 18 or mean > 245 or g.std() < 6: score *= 0.2      # black / white / flat frames
    return score, dict(sharp=round(sh, 1), mean=round(mean), contrast=round(float(g.std()), 1))

# ---------------------------------------------------------------- 4 智慧封面
def grab_frame(src, t, width=480, hdr=()):
    from PIL import Image
    import io
    vf = list(hdr) + ([f'scale={width}:-2'] if width else [])
    r = subprocess.run([E.FFMPEG, '-hide_banner', '-v', 'error', '-ss', f'{max(0.0, t):.3f}', '-i', src, '-frames:v', '1', '-an', '-sn',
                        *(['-vf', ','.join(vf)] if vf else []), '-f', 'image2pipe', '-c:v', 'png', '-'], capture_output=True, creationflags=E.NOWIN)
    if r.returncode or not r.stdout: return None
    im = Image.open(io.BytesIO(r.stdout)); im.load(); return im

def t_bestframe(eng, j, o):
    src = j.files[0]; i = need_media(src, video=True); dur = i['dur']
    want = max(1, min(20, int(T.num(o, 'count', 5)))); fmt = o.get('fmt', 'jpg')
    n = int(max(24, min(120, dur / 2 + want * 6)))
    lo, hi = dur * 0.03, dur * 0.97
    times = [lo + (hi - lo) * (k + 0.5) / n for k in range(n)]
    hdr = E.hdr_filters(src); results = []; done = [0]; lock = threading.Lock()
    def one(t):
        if j.cancelled: return None
        im = grab_frame(src, t, 480, hdr)
        with lock:
            done[0] += 1; j.progress = 0.8 * done[0] / n; j.msg = f'評分畫面 {done[0]}/{n}'
        if im is None: return None
        s, d = frame_score(im, o.get('faces', True))
        return (s, t, dhash(im), d)
    with ThreadPoolExecutor(max_workers=max(1, min(4, (os.cpu_count() or 2) // 2))) as ex:
        results = [r for r in ex.map(one, times) if r]
    if j.cancelled: raise InterruptedError
    if not results: raise RuntimeError('無法讀取影片畫面')
    chosen = []
    for s, t, h, d in sorted(results, reverse=True):
        if all(hamming(h, c[2]) > 10 and abs(t - c[1]) > dur / (want * 4) for c in chosen): chosen.append((s, t, h, d))
        if len(chosen) >= want: break
    for r in sorted(results, reverse=True):                     # similar-looking footage: fill up by time spacing only
        if len(chosen) >= want: break
        if all(abs(r[1] - c[1]) > dur / (want * 3) for c in chosen): chosen.append(r)
    chosen.sort(key=lambda c: -c[0])
    folder = T.out_dir_for(j, src, '_封面候選'); j.output = folder; lines = []
    for k, (s, t, h, d) in enumerate(chosen, 1):
        if j.cancelled: raise InterruptedError
        im = grab_frame(src, t, 0, hdr)
        if im is None: continue
        name = f'封面{k}_{int(t // 60):02d}分{int(t % 60):02d}秒.{fmt}'
        p = os.path.join(folder, name)
        if fmt == 'jpg': E.flatten(im).save(p, 'JPEG', quality=93, optimize=True)
        else: im.save(p, 'PNG', optimize=True)
        lines.append(f'{k}. {fmt_time(t)}　分數 {s:.2f}　清晰度 {d["sharp"]}　亮度 {d["mean"]}　對比 {d["contrast"]}　{name}')
        j.progress = 0.8 + 0.2 * k / len(chosen)
    with open(os.path.join(folder, '評分說明.txt'), 'w', encoding='utf-8') as fh:
        fh.write(f'來源：{os.path.basename(src)}（{fmt_time(dur)}）\n掃描 {len(results)} 個畫面，依清晰度、曝光、對比、色彩與主體位置評分，並排除相似畫面。\n\n' + '\n'.join(lines) + '\n')
    j.encoder = f'從 {len(results)} 個畫面挑出 {len(lines)} 張'

# ---------------------------------------------------------------- 5 智慧挑照片
SIM = {'strict': 4, 'normal': 9, 'loose': 14}
BLUR = {'strict': 0.55, 'normal': 0.4, 'loose': 0.25}

def photo_stats(path):
    im = T.open_img(path, lambda w, h: min(1.0, 900 / max(w, h)))
    im = E.flatten(im) if im.mode in ('RGBA', 'LA', 'P') else im.convert('RGB')
    g = gray_array(im, 512); sh = sharpness(g); mean, black, white = exposure(g)
    s, _ = frame_score(im, False)
    return dict(path=path, sharp=sh, mean=mean, black=black, white=white, score=s, hash=dhash(im), w=im.width, h=im.height)

def group_similar(stats, limit):
    parent = list(range(len(stats)))
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a in range(len(stats)):
        for b in range(a + 1, len(stats)):
            if hamming(stats[a]['hash'], stats[b]['hash']) <= limit:
                parent[find(a)] = find(b)
    groups = {}
    for k in range(len(stats)): groups.setdefault(find(k), []).append(k)
    return list(groups.values())

def classify_photos(stats, sim='normal', blur='normal'):
    sharp = sorted(s['sharp'] for s in stats); med = sharp[len(sharp) // 2] if sharp else 0
    cut = max(12.0, min(35.0, med * BLUR.get(blur, 0.4)))
    for s in stats:
        s['blurry'] = s['sharp'] < cut
        s['badexp'] = s['mean'] < 40 or s['mean'] > 225 or s['black'] > 0.55 or s['white'] > 0.45
        s['cat'] = None
    for g in group_similar(stats, SIM.get(sim, 9)):
        ranked = sorted(g, key=lambda k: (stats[k]['blurry'], stats[k]['badexp'], -stats[k]['score']))
        for n, k in enumerate(ranked):
            s = stats[k]; s['group'] = g[0]; s['group_size'] = len(g)
            if n > 0: s['cat'] = '相似重複'
            elif s['blurry']: s['cat'] = '可能模糊'
            elif s['badexp']: s['cat'] = '曝光不佳'
            else: s['cat'] = '精選'
    return stats

def t_photocull(eng, j, o):
    paths = j.files; stats = []; done = [0]; lock = threading.Lock(); errors = []
    def one(p):
        if j.cancelled: return None
        try: r = photo_stats(p)
        except Exception as ex: errors.append(f'{os.path.basename(p)}：{str(ex)[:80]}'); r = None
        with lock: done[0] += 1; j.progress = 0.7 * done[0] / len(paths); j.msg = f'分析照片 {done[0]}/{len(paths)}'
        return r
    with ThreadPoolExecutor(max_workers=max(1, min(6, E.light_workers() * 2))) as ex:
        stats = [r for r in ex.map(one, paths) if r]
    if j.cancelled: raise InterruptedError
    if not stats: raise RuntimeError('沒有可以讀取的照片')
    classify_photos(stats, o.get('sim', 'normal'), o.get('blur', 'normal'))
    root = T.out_dir_for(j, paths[0], '_智慧挑選'); j.output = root
    for k, s in enumerate(stats):
        if j.cancelled: raise InterruptedError
        if s['cat'] != '精選' and not o.get('copy_all', True): continue
        d = os.path.join(root, s['cat']); os.makedirs(d, exist_ok=True)
        s['out'] = E.unique_path(os.path.join(d, os.path.basename(s['path'])))
        shutil.copy2(s['path'], s['out']); j.progress = 0.7 + 0.28 * (k + 1) / len(stats)
    with open(os.path.join(root, '挑選報告.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh); w.writerow(['檔名', '分類', '綜合分數', '清晰度', '平均亮度', '相似組大小', '原始路徑'])
        for s in sorted(stats, key=lambda s: (s['cat'] != '精選', -s['score'])):
            w.writerow([os.path.basename(s['path']), s['cat'], f"{s['score']:.3f}", f"{s['sharp']:.1f}", f"{s['mean']:.0f}", s.get('group_size', 1), s['path']])
    count = {c: sum(1 for s in stats if s['cat'] == c) for c in ('精選', '可能模糊', '曝光不佳', '相似重複')}
    j.encoder = '　'.join(f'{k} {v}' for k, v in count.items() if v)
    j.notes = [f'共 {len(stats)} 張：' + '、'.join(f'{k} {v} 張' for k, v in count.items()), '原始照片沒有移動或刪除；分類結果與分數在「挑選報告.csv」。']
    if errors: j.warnings.append(f'{len(errors)} 張無法讀取：' + '；'.join(errors[:3]))

# ---------------------------------------------------------------- 6 自動去黑邊
def detect_crop(eng, j, src, limit, dur):
    # long videos: keyframes only (fast); short clips have too few keyframes, so look at every frame
    cmd = [E.FFMPEG, '-hide_banner', '-nostdin', '-progress', 'pipe:1', '-nostats'] + (['-skip_frame', 'nokey'] if dur > 60 else []) + ['-i', src,
           '-an', '-sn', '-vf', f'cropdetect=limit={int(limit)}:round=2:reset=0:skip=0', '-f', 'null', '-']
    eng._exec(j, cmd, dur, base=0.0, span=0.3)
    found = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', j._err or '')
    if j._rc != 0: raise RuntimeError('偵測黑邊失敗：' + an_error(j._err))
    if not found: raise RuntimeError('偵測黑邊失敗：沒有讀到可以分析的畫面')
    from collections import Counter
    tail = found[len(found) // 3:] or found                  # reset=0 grows; the later values are settled
    return tuple(int(x) for x in Counter(tail).most_common(1)[0][0])

def t_autocrop(eng, j, o):
    src = j.files[0]; i = need_media(src, video=True); W, H = i['width'], i['height']
    w, h, x, y = detect_crop(eng, j, src, T.num(o, 'limit', 24), i['dur'])
    w, h = T.even(w), T.even(h)
    if W and H and (W - w) <= 8 and (H - h) <= 8: raise RuntimeError('沒有偵測到黑邊，不需要裁切')
    if w < 64 or h < 64: raise RuntimeError('畫面大多是黑色，無法判斷黑邊（請調低「黑色判定」）')
    T.video_tool(eng, j, src, '_去黑邊', vf=[f'crop={w}:{h}:{x}:{y}'], base=0.3, span=0.7)
    j.notes = [f'原始 {W}×{H} → 裁成 {w}×{h}（左 {x}、上 {y}）']

# ---------------------------------------------------------------- 7 平台響度校正
def measure_loudness(eng, j, src, I, TP, dur):
    eng._exec(j, analyze_cmd(src, '-vn', '-af', f'loudnorm=I={I}:TP={TP}:LRA=11:print_format=json', '-f', 'null', '-'), dur, base=0.0, span=0.4)
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', j._err or '', re.S)
    if j._rc != 0 or not m: raise RuntimeError('量測響度失敗：' + an_error(j._err))
    d = json.loads(m.group(0))
    if d.get('input_i') in ('-inf', None) or float(d['input_i']) < -70: raise RuntimeError('聲音太小或幾乎無聲，無法校正響度')
    return d

def t_loudness(eng, j, o):
    src = j.files[0]; i = need_media(src)
    if not T.has_audio(src): raise RuntimeError('檔案裡沒有聲音')
    I, TP = LOUD.get(o.get('target', 'youtube'), LOUD['youtube'])
    j.msg = '量測響度'; d = measure_loudness(eng, j, src, I, TP, i['dur'])
    af = (f"loudnorm=I={I}:TP={TP}:LRA=11:measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}"
          f":measured_thresh={d['input_thresh']}:offset={d['target_offset']}:linear=true,aresample=48000")
    j.progress = 0.4
    T.audio_tool(eng, j, src, f'_{I}LUFS', [af])
    j.notes = [f'原始響度 {float(d["input_i"]):.1f} LUFS、峰值 {float(d["input_tp"]):.1f} dBTP → 目標 {I} LUFS、峰值上限 {TP} dBTP（兩段式量測校正）']
    j.encoder = (j.encoder or 'FFmpeg') + f' · {float(d["input_i"]):.1f} → {I} LUFS'

# ---------------------------------------------------------------- 8 智慧命名
BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')

def safe_name(s, limit=60):
    s = BAD.sub(' ', str(s or '')).strip(' .'); s = re.sub(r'\s+', ' ', s)
    return s[:limit].strip(' .')

def _exif(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            ex = im.getexif(); sub = ex.get_ifd(0x8769) if hasattr(ex, 'get_ifd') else {}
            date = sub.get(0x9003) or sub.get(0x9004) or ex.get(0x0132)
            model = (ex.get(0x0110) or '').strip('\x00 ')
            make = (ex.get(0x010F) or '').strip('\x00 ')
            if make and model and not model.lower().startswith(make.lower().split()[0]): model = f'{make} {model}'
            return date, model or make
    except Exception: return None, ''

def _parse_date(s):
    if not s: return None
    m = re.search(r'(\d{4})[:\-/](\d{2})[:\-/](\d{2})[ T]?(\d{2})?:?(\d{2})?:?(\d{2})?', str(s))
    if not m: return None
    y, mo, d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    if not (1980 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31): return None
    return (y, mo, d, h, mi, se)

def media_tags(path):
    r = E.run([E.FFMPEG, '-hide_banner', '-i', path]) if E.FFMPEG else None
    txt = r.stderr if r else ''
    def tag(k):
        m = re.search(rf'^\s*{k}\s*:\s*(.+)$', txt, re.M | re.I)
        return m.group(1).strip() if m else ''
    return dict(date=tag('creation_time') or tag('date'), title=tag('title'), artist=tag('artist'), model=tag('com.apple.quicktime.model') or tag('model'))

def pdf_title(path):
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        if r.is_encrypted:
            try: r.decrypt('')
            except Exception: return '', None
        meta = r.metadata or {}
        t = (meta.get('/Title') or '').strip()
        date = meta.get('/CreationDate') or ''
        if not t or re.fullmatch(r'(untitled|microsoft word.*|document\d*|無標題)', t, re.I):
            text = (r.pages[0].extract_text() or '') if r.pages else ''
            t = next((l.strip() for l in text.splitlines() if len(l.strip()) >= 3), '')
        return t, _parse_date(str(date)[2:] if str(date).startswith('D:') else date)
    except Exception: return '', None

def describe_for_name(path):
    cat, ext = E.classify(path); date = None; info = ''
    if cat == 'image':
        d, model = _exif(path); date = _parse_date(d); info = model
    elif cat in ('video', 'audio'):
        t = media_tags(path); date = _parse_date(t['date'])
        if cat == 'audio' and (t['artist'] or t['title']): info = ' - '.join(x for x in (t['artist'], t['title']) if x)
        else: info = t['title'] or t['model']
    elif cat == 'pdf':
        info, date = pdf_title(path)
    source = '中繼資料' if date else '檔案修改時間'
    if not date:
        lt = time.localtime(os.path.getmtime(path)); date = lt[:6]
    return dict(date=date, info=safe_name(info, 40), source=source, ext=ext)

def build_name(d, style, prefix='', seq=0, width=3):
    y, mo, da, h, mi, se = d['date']; ds = f'{y:04d}-{mo:02d}-{da:02d}'; ts = f'{h:02d}{mi:02d}{se:02d}'
    if style == 'date': base = f'{ds}_{ts}'
    elif style == 'info': base = d['info'] or f'{ds}_{ts}'
    elif style == 'prefix_seq': base = f'{safe_name(prefix, 30) or "檔案"}_{seq:0{width}d}_{ds}'
    else: base = f'{ds}_{ts}' + (f'_{d["info"]}' if d['info'] else '')
    return safe_name(base, 90) or 'file'

def t_smartname(eng, j, o):
    paths = j.files; style = o.get('style', 'date_info'); infos = []
    for k, p in enumerate(paths):
        if j.cancelled: raise InterruptedError
        try: infos.append((p, describe_for_name(p)))
        except Exception as ex: j.warnings.append(f'{os.path.basename(p)} 讀取失敗：{str(ex)[:60]}')
        j.progress = 0.6 * (k + 1) / len(paths); j.msg = f'讀取資訊 {k + 1}/{len(paths)}'
    if not infos: raise RuntimeError('沒有可以命名的檔案')
    infos.sort(key=lambda x: (x[1]['date'], os.path.basename(x[0]).lower()))
    folder = j.opt.get('out_dir') or os.path.dirname(paths[0])
    root = E.unique_path(os.path.join(folder, time.strftime('智慧命名_%Y%m%d_%H%M%S'))); os.makedirs(root); j.output = root
    width = max(3, len(str(len(infos)))); rows = []
    for k, (p, d) in enumerate(infos, 1):
        if j.cancelled: raise InterruptedError
        sub = root if not o.get('month') else os.path.join(root, f'{d["date"][0]:04d}-{d["date"][1]:02d}')
        os.makedirs(sub, exist_ok=True)
        ext = os.path.splitext(p)[1]
        dst = E.unique_path(os.path.join(sub, build_name(d, style, o.get('prefix', ''), k, width) + ext.lower()))
        shutil.copy2(p, dst); rows.append([os.path.basename(p), os.path.relpath(dst, root), d['source'], p])
        j.progress = 0.6 + 0.38 * k / len(infos)
    with open(os.path.join(root, '命名對照表.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh); w.writerow(['原檔名', '新檔名', '日期來源', '原始路徑']); w.writerows(rows)
    by_meta = sum(1 for r in rows if r[2] == '中繼資料')
    j.encoder = f'{len(rows)} 個檔案（{by_meta} 個用拍攝／建立時間）'
    j.notes = ['原始檔案沒有改名或移動；新名稱的副本與「命名對照表.csv」在輸出資料夾。'] + ([f'{len(rows) - by_meta} 個檔案沒有拍攝時間，改用檔案修改時間。'] if by_meta < len(rows) else [])

# ---------------------------------------------------------------- 9 畫質目標壓縮
CRF_RANGE = {'h264': (16, 34), 'hevc': (18, 36)}

def parse_ssim(err):
    m = re.findall(r'All:([\d.]+)', err or '')
    return float(m[-1]) if m else None

def sample_points(dur, n=3, length=4.0):
    if dur <= length * n + 2: return [(0.0, dur)]
    return [(max(0.0, dur * f - length / 2), length) for f in (0.2, 0.5, 0.8)[:n]]

def quality_vf(src, height):
    vf = list(E.hdr_filters(src))
    if height: vf.append(f'scale=-2:{height}:flags=lanczos')
    return vf

def enc_args(codec, crf, threads):
    if codec == 'hevc':
        return ['-c:v', 'libx265', '-preset', 'fast', '-crf', str(crf), '-x265-params', f'log-level=error:pools={threads}', '-tag:v', 'hvc1', '-pix_fmt', 'yuv420p']
    return ['-c:v', 'libx264', '-preset', 'fast', '-crf', str(crf), '-threads', str(threads), '-pix_fmt', 'yuv420p']

def sample_ssim(eng, j, src, codec, crf, samples, vf, tmp):
    threads = E.encoder_threads(j.opt); vals = []; sizes = 0.0; secs = 0.0
    for k, (ss, ln) in enumerate(samples):
        if j.cancelled: raise InterruptedError
        enc = os.path.join(tmp, f's{k}_{crf}.mkv')
        c = [E.FFMPEG, '-hide_banner', '-nostdin', '-y', '-v', 'error', '-ss', f'{ss:.3f}', '-t', f'{ln:.3f}', '-i', src, '-an', '-sn']
        if vf: c += ['-vf', ','.join(vf)]
        eng._proc(j, c + enc_args(codec, crf, threads) + [enc], '試壓樣本')
        ref_vf = (','.join(vf) + ',' if vf else '') + 'format=yuv420p'
        c = [E.FFMPEG, '-hide_banner', '-nostdin', '-i', enc, '-ss', f'{ss:.3f}', '-t', f'{ln:.3f}', '-i', src,
             '-lavfi', f'[1:v:0]{ref_vf}[ref];[0:v:0]format=yuv420p[dist];[dist][ref]ssim', '-f', 'null', '-']
        r = subprocess.run(c, capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=E.LOWPRI)
        v = parse_ssim(r.stderr)
        if v is None: raise RuntimeError('畫質量測失敗：' + T.ff_error(r.stderr))
        vals.append(v); sizes += os.path.getsize(enc); secs += ln
        try: os.remove(enc)
        except OSError: pass
    return min(vals), sizes / max(0.1, secs)

def search_crf(probe, lo, hi, target, steps=5):
    """Largest CRF (smallest file) whose worst sample still reaches the SSIM target."""
    best = None; tried = {}
    a, b = lo, hi
    for _ in range(steps):
        if a > b: break
        mid = (a + b) // 2
        tried[mid] = probe(mid)
        if tried[mid][0] >= target: best = mid; a = mid + 1
        else: b = mid - 1
    if best is None:
        best = lo
        if lo not in tried: tried[lo] = probe(lo)
    return best, tried

def t_quality(eng, j, o):
    src = j.files[0]; i = need_media(src, video=True); dur = i['dur']
    codec = o.get('codec', 'h264') if o.get('codec') in ('h264', 'hevc') else 'h264'
    target = float(o.get('target') or 0.975); height = int(o.get('height') or 0)
    if height and i['height'] and height >= i['height']: height = 0          # never upscale
    vf = quality_vf(src, height); samples = sample_points(dur)
    tmp = T.tmpdir(); lo, hi = CRF_RANGE[codec]; n = [0]
    try:
        def probe(crf):
            n[0] += 1; j.msg = f'試壓樣本（第 {n[0]} 次，CRF {crf}）'; j.progress = min(0.3, 0.06 * n[0])
            return sample_ssim(eng, j, src, codec, crf, samples, vf, tmp)
        crf, tried = search_crf(probe, lo, hi, target)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ssim, rate = tried[crf]
    out = T.out_for(j, src, 'mp4' if os.path.splitext(src)[1].lower() != '.mkv' else 'mkv', f'_畫質{target:g}'); j.output = out
    threads = E.encoder_threads(j.opt); audio = T.has_audio(src)
    def build(hw):
        c = T.base_cmd() + ['-i', src, '-map', '0:v:0'] + (['-map', '0:a:0'] if audio else [])
        if vf: c += ['-vf', ','.join(vf)]
        c += enc_args(codec, crf, threads)
        if audio: c += ['-c:a', 'copy'] if i['acodec'] == 'aac' else ['-c:a', 'aac', '-b:a', '160k']
        if out.endswith('.mp4'): c += ['-movflags', '+faststart']
        return c + ['-map_metadata', '0', out]
    T.ff_run(eng, j, build, dur, base=0.32, span=0.68, gpu=False)
    j.encoder = f'{"H.265" if codec == "hevc" else "H.264"} CRF {crf} · 樣本 SSIM {ssim:.4f}'
    insz = os.path.getsize(src); outsz = os.path.getsize(out) if os.path.isfile(out) else 0
    j.notes = [f'試了 {len(tried)} 種壓縮強度：' + '、'.join(f'CRF {k}→{v[0]:.4f}' for k, v in sorted(tried.items())),
               f'選用 CRF {crf}（樣本最差 SSIM {ssim:.4f}，目標 {target:g}）；{insz / 1048576:.1f} MB → {outsz / 1048576:.1f} MB']
    if outsz > insz: j.notes.append('成品比原檔大：原檔已經壓得很省，建議保留原檔，或改選「省空間」。')

RUN = dict(s_jumpcut=t_jumpcut, s_highlight=t_highlight, s_chapters=t_chapters, s_bestframe=t_bestframe, s_photocull=t_photocull,
           s_autocrop=t_autocrop, s_loudness=t_loudness, s_smartname=t_smartname, s_quality=t_quality)

# ================================================================ 智慧建議（一般轉檔）
def suggest_one(path):
    cat, ext = E.classify(path); targets = E.targets_for(cat, ext); base = E.suggest(cat, ext)
    r = dict(target=base, why='', tip='')
    if not targets: return r
    pick = lambda t, why, tip='': dict(target=t if t in targets else base, why=why, tip=tip)
    try: size = os.path.getsize(path)
    except OSError: size = 0
    if cat == 'video':
        i = E.probe_info(path); v = next((c for k, c in i['streams'] if k == 'video'), '')
        if i.get('hdr'): return pick('mp4', 'HDR 影片：轉成一般色彩的 MP4，在一般螢幕與通訊軟體上顏色才不會發灰')
        if v in ('hevc', 'h265', 'av1', 'vp9', 'prores', 'dnxhd') or ext in ('mov', 'avi', 'wmv', 'flv', 'mts', 'm2ts', 'ts', '3gp', 'mpg', 'mpeg', 'vob'):
            name = {'hevc': 'HEVC', 'h265': 'HEVC', 'av1': 'AV1', 'vp9': 'VP9', 'prores': 'ProRes', 'dnxhd': 'DNxHD'}.get(v, ext.upper())
            return pick('mp4', f'{name}：轉成 MP4（H.264）相容性最好，Windows、手機、LINE 都能直接播放')
        if ext == 'mp4' and v == 'h264' and size > 1 << 30 and i['dur'] > 0 and size * 8 / i['dur'] > 12e6:
            return pick('mp4', f'位元率偏高（約 {size * 8 / i["dur"] / 1e6:.0f} Mbps）：可用「小檔案」品質或 HEVC 重新壓縮', 'small')
        if ext == 'gif': return pick('mp4', 'GIF 動畫轉 MP4 通常小 5～10 倍，畫質更好')
        if ext == 'webm': return pick('mp4', 'WebM 在部分 Windows 與 iPhone 軟體打不開；轉 MP4 相容性最好')
    elif cat == 'audio':
        if ext in ('wav', 'aif', 'aiff') and size > 10 << 20: return pick('flac', '無壓縮音訊：FLAC 是無損壓縮，音質完全相同、大小約一半')
        if ext == 'flac': return pick('m4a', '要放手機或分享可轉 M4A；要保存請保留 FLAC 原檔')
        if ext in ('wma', 'amr', 'ape', 'ac3', 'dts'): return pick('mp3', f'{ext.upper()} 很多裝置不支援；MP3 到處都能播')
        i = E.probe_info(path)
        if i.get('akbps') and i['akbps'] <= 128 and ext in ('mp3', 'm4a', 'aac', 'ogg', 'opus'):
            return dict(target=base, why=f'原檔只有 {i["akbps"]} kbps：轉成更高位元率不會變好聽', tip='')
    elif cat == 'image':
        if ext in ('heic', 'heif', 'avif'): return pick('jpg', f'{ext.upper()} 在舊版 Windows 與很多網站無法開啟；JPG 到處都能用')
        if ext in E.RAW: return pick('jpg', '相機 RAW：轉成 JPG 方便分享；要後製請保留 RAW 原檔')
        if ext in ('psd', 'tiff', 'tif', 'bmp') and size > 5 << 20: return pick('png' if ext == 'psd' else 'jpg', '檔案很大：轉成一般圖片方便分享')
        if ext == 'png' and size > 1 << 20:
            try:
                from PIL import Image
                with Image.open(path) as im:
                    alpha = im.mode in ('RGBA', 'LA') or 'transparency' in im.info
                    colors = len(im.convert('RGB').resize((64, 64)).getcolors(4096) or [0] * 4097)
                if alpha: return pick('webp', '有透明背景：WebP 能保留透明，大小通常只有 PNG 的 1/3')
                if colors > 2000: return pick('jpg', '這是照片類 PNG：轉 JPG 通常小 5 倍以上，看不出差異')
            except Exception: pass
    elif cat == 'pdf':
        try:
            from pypdf import PdfReader
            rd = PdfReader(path)
            if not rd.is_encrypted:
                pages = [rd.pages[k] for k in range(min(3, len(rd.pages)))]
                text = ''.join((p.extract_text() or '') for p in pages)
                has_img = any('/XObject' in (p.get('/Resources') or {}) for p in pages)
                if len(text.strip()) < 20 and has_img: return dict(target=base, why='這是掃描 PDF（沒有文字）：到「PDF 工作台 → OCR」可變成可搜尋、可複製的文件', tip='ocr')
        except Exception: pass
    elif cat in ('doc', 'sheet', 'office') and 'pdf' in targets:
        return pick('pdf', '交付、列印與送審用 PDF 版面最穩定，對方不需要 Office')
    elif cat == 'ebook' and ext in ('mobi', 'azw', 'azw3') and 'epub' in targets:
        return pick('epub', 'EPUB 是通用電子書格式，大部分閱讀器都支援')
    return r

def smart_suggest(paths):
    paths = [p for p in (paths or []) if isinstance(p, str) and os.path.isfile(p)][:400]
    if not paths: return {}
    with ThreadPoolExecutor(max_workers=max(1, min(6, len(paths), os.cpu_count() or 2))) as ex:
        res = list(ex.map(lambda p: _safe(suggest_one, p), paths))
    return {p: r for p, r in zip(paths, res) if r}

def _safe(fn, *a):
    try: return fn(*a)
    except Exception as ex: E.log(f'smart_suggest {a}: {ex}'); return None

# ================================================================ 白話指令 → 工具（工具搜尋）
CN_NUM = {'一': 1, '兩': 2, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '半': 0.5}

def _num_before(text, units):
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:' + units + ')', text, re.I)
    if m: return float(m.group(1))
    m = re.search(r'([一兩二三四五六七八九十半])\s*(?:' + units + ')', text)
    return float(CN_NUM[m.group(1)]) if m else None

# (pattern, tool, params-builder, reason)
def _rules():
    def mb(t):
        v = _num_before(t, 'mb|mB|MB|m(?![a-z])|M(?![a-z])|百萬|兆')
        return v
    R = [
        (r'停頓|空白|贅詞|沒聲音的地方|口誤|jump ?cut|剪掉.*(安靜|靜音)', 's_jumpcut', lambda t: {}, '自動剪掉說話之間的停頓'),
        (r'精華|重點片段|highlight|集錦|預告', 's_highlight', lambda t: dict(ratio='9:16' if re.search(r'直式|短影音|shorts|reels|抖音|tiktok', t, re.I) else 'same',
                                                                    **({'length': _num_before(t, '秒|s')} if _num_before(t, '秒|s') else {})), '依聲音與畫面挑精華'),
        (r'章節|chapter|分段標題|時間軸目錄', 's_chapters', lambda t: {}, '逐字稿分章節並寫標題'),
        (r'封面|縮圖|thumbnail|最好看的畫面|截.*最清楚', 's_bestframe', lambda t: {}, '挑最清晰的畫面'),
        (r'挑照片|選照片|模糊.*照片|照片.*模糊|重複.*照片|照片.*重複|連拍|篩選照片', 's_photocull', lambda t: {}, '分出精選、模糊、重複的照片'),
        (r'黑邊|黑框|letterbox', 's_autocrop', lambda t: {}, '偵測並裁掉黑邊'),
        (r'響度|lufs|音量.*(一致|平均|標準)|podcast|廣播規範', 's_loudness', lambda t: dict(target='podcast' if re.search('podcast|有聲書', t, re.I) else 'broadcast' if re.search('廣播|電視|ebu', t, re.I) else 'apple' if re.search('apple', t, re.I) else 'youtube'), '兩段式響度校正'),
        (r'命名|改名|檔名|rename', 's_smartname', lambda t: dict(month=bool(re.search('月份|按月|每月', t))), '依拍攝時間與資訊命名副本'),
        (r'畫質.*(不變|不要變|保持)|無損壓縮影片|最小.*畫質|ssim|vmaf', 's_quality', lambda t: dict(codec='hevc' if re.search('hevc|h\\.?265', t, re.I) else 'h264'), '量測畫質，找出最小檔案'),
        (r'(自動|ai|辨識|聽打|產生).{0,4}字幕|字幕.{0,4}(自動|ai|辨識)', 'v_autosub', lambda t: dict(out='burn' if re.search('燒|內嵌到畫面|硬字幕', t) else 'soft' if re.search('內嵌|軟字幕|可開關', t) else 'srt'), '離線語音辨識產生字幕'),
        (r'加字幕|燒.*字幕|字幕檔', 'v_subs', lambda t: {}, '把字幕檔加進影片'),
        (r'會議|開會|紀錄|總結|摘要.*錄音', 'a_meeting', lambda t: {}, '逐字稿＋摘要、決議、待辦'),
        (r'逐字稿|聽打|轉文字|語音轉|轉成文字', 'a_transcribe', lambda t: {}, '錄音轉成逐字稿'),
        (r'去人聲|伴奏|卡拉|消音', 'a_vocal', lambda t: {}, '消去人聲做伴奏'),
        (r'降噪|雜音|底噪|風切|冷氣聲', 'a_denoise', lambda t: {}, '去除背景雜音'),
        (r'升.{0,3}key|降.{0,3}key|變調|升調|降調|半音', 'a_pitch', lambda t: dict(semi=(-1 if re.search('降', t) else 1) * (_num_before(t, 'key|個?半音|度') or 1)), '升降 Key'),
        (r'鈴聲|ringtone', 'a_ringtone', lambda t: dict(fmt='mp3' if re.search('android|安卓', t, re.I) else 'm4r'), '做手機鈴聲'),
        (r'(加|配).{0,3}(音樂|配樂|bgm)|換音軌', 'v_audio', lambda t: {}, '加背景音樂'),
        (r'去.{0,2}(聲音|音訊)|靜音|只要畫面', 'v_mute', lambda t: {}, '去除聲音'),
        (r'慢動作|快轉|倍速|加速|變速', 'v_speed', lambda t: dict(speed=(_num_before(t, '倍|x|X') or (0.5 if re.search('慢', t) else 2))), '影片變速'),
        (r'防手震|晃|穩定', 'v_stab', lambda t: {}, '穩定晃動畫面'),
        (r'(去|移除|消除).{0,3}(浮水印|台標|logo)', 'v_delogo', lambda t: {}, '框選後補掉浮水印'),
        (r'直式|短影音|shorts|reels|抖音|tiktok|9 ?[:：比] ?16', 'v_fill', lambda t: dict(ratio='9:16'), '改成直式（模糊背景）'),
        (r'方形|1 ?[:：比] ?1|ig.*貼文', 'v_fill', lambda t: dict(ratio='1:1', height='1080'), '改成方形'),
        (r'(影片|video).{0,6}浮水印|浮水印.{0,6}影片', 'v_wm_text', lambda t: {}, '影片加文字浮水印'),
        (r'(照片|圖片|圖).{0,6}浮水印|浮水印.{0,6}(照片|圖)', 'i_watermark', lambda t: dict(pos='tile') if re.search('平鋪|防盜', t) else {}, '圖片加浮水印'),
        (r'浮水印', 'v_wm_text', lambda t: {}, '加浮水印'),
        (r'長圖|拼圖|九宮格|拼接', 'i_collage', lambda t: dict(layout='grid' if '九宮格' in t else 'h' if re.search('橫', t) else 'v'), '多張圖片拼在一起'),
        (r'照片.{0,4}(影片|幻燈片|mv)|幻燈片|相簿影片', 'i_slideshow', lambda t: {}, '照片做成影片'),
        (r'gif', 'i_gif', lambda t: {}, '做成 GIF 動畫'),
        (r'(照片|圖片).{0,4}(縮小|縮放|尺寸)|縮圖片|批次縮放', 'i_resize', lambda t: {}, '批次縮放圖片'),
        (r'(gps|位置|定位|隱私|個資|exif)', 'x_privacy', lambda t: {}, '移除位置與拍攝資訊'),
        (r'合併.{0,3}pdf|pdf.{0,3}合併', 'p_merge', lambda t: {}, '合併多個 PDF'),
        (r'(壓縮|縮小).{0,3}pdf|pdf.{0,4}(太大|壓縮|縮小)', 'p_compress', lambda t: {}, '壓縮 PDF'),
        (r'ocr|掃描.{0,4}(文字|搜尋)|可搜尋', 'p_ocr', lambda t: {}, '辨識掃描 PDF 的文字'),
        (r'pdf.{0,3}(轉|變成).{0,3}word|pdf.{0,3}編輯', 'p_pdf_word', lambda t: {}, 'PDF 轉 Word'),
        (r'pdf.{0,3}(加密|密碼)|(加密|密碼).{0,3}pdf', 'p_encrypt', lambda t: {}, '幫 PDF 加密碼'),
        (r'(解除|移除|拿掉).{0,3}密碼', 'p_decrypt', lambda t: {}, '解除 PDF 密碼'),
        (r'簽名|簽章|蓋章', 'p_sign', lambda t: {}, 'PDF 簽名'),
        (r'(拆|分割).{0,3}pdf|pdf.{0,3}(拆|分割)', 'p_split', lambda t: {}, '分割 PDF'),
        (r'pdf.{0,4}翻譯|翻譯.{0,4}(pdf|文件)', 'p_translate', lambda t: {}, '離線翻譯 PDF'),
        (r'pdf.{0,4}摘要|摘要.{0,4}(pdf|文件)', 'p_summary', lambda t: {}, '離線摘要 PDF'),
        (r'(分割|切).{0,4}(影片|段)|每.{0,4}秒.{0,2}切', 'v_split', lambda t: {}, '分割影片'),
        (r'旋轉|轉正|翻轉|橫的變直', 'v_rotate', lambda t: {}, '旋轉影片'),
        (r'裁切|裁剪|crop', 'v_crop', lambda t: {}, '裁切畫面'),
        (r'淡入|淡出', 'v_fade', lambda t: {}, '淡入淡出'),
        (r'倒轉|倒放|倒著播', 'v_reverse', lambda t: {}, '倒轉播放'),
        (r'截圖|擷取畫面|縮圖總覽', 'v_frames', lambda t: {}, '擷取畫面'),
        (r'並排|分割畫面|左右|上下.{0,2}並', 'v_grid', lambda t: {}, '多支影片並排'),
        (r'dvd', 'd_dvd', lambda t: {}, 'DVD 轉影片'), (r'藍光|blu-?ray', 'd_bluray', lambda t: {}, '藍光轉影片'),
        (r'音樂 ?cd|cd.{0,3}(轉|音軌)', 'd_cd', lambda t: {}, '音樂 CD 轉檔'), (r'iso', 'd_iso', lambda t: {}, '光碟轉 ISO'),
        (r'(歌名|歌手|專輯|封面).{0,4}(改|加|資訊)|id3', 'a_tags', lambda t: {}, '修改歌曲資訊'),
        (r'混音|疊.{0,3}音軌', 'a_mix', lambda t: {}, '多個音軌混在一起'),
    ]
    return R

def size_intent(text):
    v = _num_before(text, r'mb|MB|Mb|m(?![a-z])|M(?![a-z])|百萬|兆|mega')
    if v and re.search(r'壓|縮|以內|以下|小於|不超過|限制|上限|傳|寄|附件|line|discord|email|mail', text, re.I):
        return v
    return None

def intent(text, tools=None):
    """Plain-language request → ranked [{tool, params, why, score}] plus an optional convert-page suggestion."""
    text = (text or '').strip()[:300]
    if not text: return dict(tools=[], convert=None)
    known = {t['id']: t for t in (tools or T.TOOLS)}
    low = text.lower(); out = []; seen = set()
    for k, (pat, tid, build, why) in enumerate(_rules()):
        if tid in seen or tid not in known: continue
        if re.search(pat, low, re.I):
            try: params = {a: b for a, b in build(text).items() if b is not None}
            except Exception: params = {}
            fields = {f['k'] for f in known[tid]['fields']}
            params = {a: (int(b) if isinstance(b, float) and b.is_integer() and a not in ('speed',) else b) for a, b in params.items() if a in fields}
            out.append(dict(tool=tid, params=params, why=why, score=round(1.0 - k * 0.004, 3))); seen.add(tid)
    # fuzzy: overlap of 2-character pieces with the tool name / description
    grams = lambda s: {s[i:i + 2] for i in range(len(s) - 1)} | set(re.findall(r'[a-z0-9]{2,}', s))
    q = grams(re.sub(r'\s+', '', low))
    if q:
        for t in known.values():
            if t['id'] in seen: continue
            g = grams((t['name'] + t['desc']).lower()); hit = len(q & g)
            if hit >= (3 if seen else 2) or (hit and len(q) <= 3 and not seen):
                out.append(dict(tool=t['id'], params={}, why='名稱或說明相符', score=round(min(0.6, 0.15 * hit), 3)))
    out.sort(key=lambda r: -r['score'])
    convert = None; mbv = size_intent(text)
    if mbv:
        convert = dict(target_mb=mbv, why=f'一般轉檔：把「目標大小」設為 {mbv:g} MB')
        if re.search(r'影片|video|mp4|片', low): convert['target'] = 'mp4'
    elif re.search(r'轉成?\s*(mp4|mp3|mkv|webm|gif|jpg|png|webp|pdf|docx|flac|m4a|wav|epub|srt)', low):
        fmt = re.search(r'轉成?\s*(mp4|mp3|mkv|webm|gif|jpg|png|webp|pdf|docx|flac|m4a|wav|epub|srt)', low).group(1)
        convert = dict(target=fmt, why=f'一般轉檔：全部轉成 {fmt.upper()}')
    return dict(tools=out[:8], convert=convert)
