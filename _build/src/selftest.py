"""四維八德 self test.

    四維八德.exe --selftest            -> builds its own sample files and tests every converter / tool
    四維八德.exe --selftest --ai       -> also tests AI subtitles (downloads the small 150 MB model once)
    四維八德.exe --selftest --rec      -> also records the screen for 3 seconds

Results: selftest\\selftest.log next to the program (the folder is opened when done).
"""
import os, sys, time, json, shutil, platform, subprocess, traceback
import engine as E

def main(arg=None):
    flags = set(a for a in sys.argv[2:] if a.startswith('--'))
    root = arg if arg and not arg.startswith('--') else os.path.join(E.base_dir(), 'selftest')
    smp = os.path.join(root, 'samples'); out = E.unique_path(os.path.join(root, 'out'))
    os.makedirs(smp, exist_ok=True); os.makedirs(out, exist_ok=True)
    logf = open(os.path.join(root, 'selftest.log'), 'w', encoding='utf-8')
    def log(s):
        logf.write(s + '\n'); logf.flush()
        if sys.stdout:
            try: print(s)
            except UnicodeEncodeError: print(s.encode(sys.stdout.encoding or 'utf-8', 'replace').decode(sys.stdout.encoding or 'utf-8'))
    import tools as T, capture as C
    log(f'四維八德 自我檢測  {time.strftime("%Y-%m-%d %H:%M:%S")}')
    log(f'Windows {platform.version()}  {platform.machine()}  CPU {os.cpu_count()}  Python {platform.python_version()}')
    ffv = E.run([E.FFMPEG, '-version']).stdout.splitlines()[0] if E.FFMPEG else '（沒有）'
    log(f'ffmpeg   {ffv}')
    log(f'GPU      {E.detect_hw() or "（無，使用 CPU）"}')
    log(f'whisper  {T.whisper_ok()}   字型 {T.find_font()}')
    log(f'office   {E.SOFFICE}\ncalibre  {E.CALIBRE}\npandoc   {E.PANDOC}\n7z       {E.SEVENZIP}')
    yv = E.run([C.ytdlp(), '--version']).stdout.strip() if C.ytdlp() else '（沒有）'
    log(f'yt-dlp   {yv}   deno {C.deno() or "（尚未下載）"}')
    log(f'音訊裝置 {C.audio_devices()}   螢幕 {C.monitors()}')
    log('')

    S = lambda f: os.path.join(smp, f)
    # ---------- build samples ----------
    ff = lambda *a: E.run([E.FFMPEG, '-hide_banner', '-v', 'error', '-y'] + list(a))
    if not os.path.isfile(S('v.mp4')):
        ff('-f', 'lavfi', '-i', 'testsrc2=s=1280x720:r=30:d=8', '-f', 'lavfi', '-i', 'sine=f=440:d=8', '-f', 'lavfi', '-i', 'sine=f=660:d=8',
           '-filter_complex', '[1][2]join=inputs=2:channel_layout=stereo[a]', '-map', '0', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-g', '250', '-c:a', 'aac', S('v.mp4'))
        ff('-i', S('v.mp4'), '-c', 'copy', S('v.mkv'))
        ff('-f', 'lavfi', '-i', 'testsrc=s=720x1280:r=30:d=5', '-f', 'lavfi', '-i', 'sine=f=300:d=5', '-c:v', 'libx264', '-preset', 'veryfast', '-c:a', 'aac', S('vert.mp4'))
        ff('-f', 'lavfi', '-i', 'testsrc2=s=1920x1080:r=30:d=4', '-vf', 'format=yuv420p10le', '-c:v', 'libx265', '-preset', 'ultrafast',
           '-x265-params', 'colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc', '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc', '-tag:v', 'hvc1', S('hdr.mov'))
        ff('-f', 'lavfi', '-i', 'sine=f=300:d=12', '-ac', '2', S('a.wav'))
        ff('-f', 'lavfi', '-i', 'sine=f=500:d=6', '-f', 'lavfi', '-i', 'anoisesrc=d=6:a=0.05', '-filter_complex', '[0][1]amix=inputs=2,aformat=channel_layouts=stereo', '-c:a', 'libmp3lame', '-b:a', '192k', S('song.mp3'))
        ff('-i', S('a.wav'), '-c:a', 'aac', '-b:a', '96k', S('a96.m4a'))
        from PIL import Image, ImageDraw
        for i, c in enumerate([(200, 50, 50), (50, 150, 200), (60, 180, 90), (220, 200, 40)]):
            im = Image.new('RGB', (1600 + i * 200, 1200), c); ImageDraw.Draw(im).ellipse((300, 200, 900, 800), fill=(255, 255, 255))
            ex = Image.Exif(); ex[0x010F] = 'TestCam'; im.save(S(f'img{i}.jpg'), quality=90, exif=ex.tobytes())
        im = Image.new('RGBA', (800, 600), (40, 90, 200, 255)); ImageDraw.Draw(im).ellipse((100, 100, 500, 500), fill=(255, 0, 0, 0)); im.save(S('alpha.png'))
        lg = Image.new('RGBA', (300, 120), (0, 0, 0, 0)); ImageDraw.Draw(lg).rounded_rectangle((0, 0, 299, 119), 20, fill=(255, 120, 0, 220)); lg.save(S('logo.png'))
        Image.open(S('img1.jpg')).save(S('multi.pdf'), save_all=True, append_images=[Image.open(S('img2.jpg')), Image.open(S('img3.jpg'))])
        from pypdf import PdfWriter
        w = PdfWriter()
        for _ in range(6): w.add_blank_page(595, 842)
        w.add_metadata({'/Author': 'Someone'}); w.write(S('doc6.pdf'))
        open(S('sub.srt'), 'wb').write('1\n00:00:00,500 --> 00:00:03,000\n測試字幕：你好世界\n\n2\n00:00:03,500 --> 00:00:06,000\n第二行\n'.encode('cp950'))
        open(S('d.md'), 'w', encoding='utf-8').write('# 標題\n\n這是**測試**文件。\n\n- 一\n- 二\n')
        open(S('s.csv'), 'w', encoding='utf-8-sig').write('品名,數量\n蘋果,3\n香蕉,5\n')
        open(S('t.txt'), 'w', encoding='utf-8').write('純文字測試\n第二行\n')
        if E.PANDOC:
            E.run([E.PANDOC, S('d.md'), '-o', S('d.docx')]); E.run([E.PANDOC, S('d.md'), '-o', S('b.epub'), '--metadata', 'title=測試'])
        if E.SEVENZIP: E.run([E.SEVENZIP, 'a', '-bso0', S('x.zip'), S('t.txt'), S('d.md')])
        for cand in (os.path.join(E.base_dir(), '_build', 'samples', 'i.heic'), os.path.join(os.path.dirname(E.base_dir()), 'samples', 'i.heic')):
            if os.path.isfile(cand): shutil.copy(cand, S('i.heic')); break
        open(S('m.stl'), 'w').write('solid t\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid t\n')

    eng = E.Engine(1, 1); results = []
    def wait(ids, limit=600):
        t0 = time.time()
        while any(eng.jobs[i].state in ('queued', 'running') for i in ids) and time.time() - t0 < limit: time.sleep(0.1)
    def report(name, ids):
        for i in ids:
            j = eng.jobs[i]; p = j.output or ''
            ok = bool(j.state == 'done' and (os.path.isfile(p) and os.path.getsize(p) > 0 or os.path.isdir(p) and os.listdir(p)))
            results.append(ok)
            log(f"{'OK  ' if ok else 'FAIL'} {name:34} {j.elapsed:6.2f}s  {(j.out_size or 0) // 1024:>7} KB  {j.encoder[:50]}  {'' if ok else j.msg}")

    log('── 轉檔 ──')
    conv = [(['v.mp4'], 'mkv', {}), (['v.mp4'], 'mp4', dict(height=480)), (['v.mp4'], 'webm', {}), (['v.mp4'], 'gif', dict(trim_end=3)),
            (['v.mp4'], 'mp3', {}), (['v.mp4'], 'mp4', dict(target_mb=1)), (['v.mkv'], 'mp4', {}), (['hdr.mov'], 'mp4', dict(fastcopy=False)),
            (['a.wav'], 'flac', {}), (['a.wav'], 'opus', {}), (['a.wav'], 'mp3', dict(loudnorm=True)), (['a96.m4a'], 'mp3', {}),
            (['i.heic'], 'jpg', {}), (['alpha.png'], 'jpg', {}), (['alpha.png'], 'webp', {}), (['alpha.png'], 'avif', {}), (['alpha.png'], 'ico', {}), (['img0.jpg'], 'jpg', dict(target_mb=0.05)),
            (['img0.jpg', 'img1.jpg'], 'pdf', {}), (['multi.pdf'], 'png', {}), (['multi.pdf'], 'pdf', dict(preset='small')), (['multi.pdf'], 'txt', {}),
            (['d.md'], 'docx', {}), (['d.md'], 'html', {}), (['d.md'], 'pdf', {}), (['t.txt'], 'pdf', {}), (['d.docx'], 'pdf', {}), (['s.csv'], 'xlsx', {}),
            (['b.epub'], 'mobi', {}), (['b.epub'], 'docx', {}), (['x.zip'], 'extract', {}), (['x.zip'], '7z', {}), (['sub.srt'], 'vtt', {}), (['m.stl'], 'glb', {})]
    for fs, t, o in conv:
        fs = [S(f) for f in fs]
        if not all(os.path.exists(f) for f in fs): log(f'SKIP {os.path.basename(fs[0])}->{t}（缺少範例檔）'); continue
        ids = eng.submit(fs, t, dict(o, out_dir=out), merge=len(fs) > 1); wait(ids); report(f'{os.path.basename(fs[0])} → {t} {o or ""}', ids)

    log('\n── 工具箱 ──')
    tl = [('v_social', ['v.mp4'], dict(mode='vertical')), ('v_social', ['v.mp4'], dict(mode='mb10')), ('v_crop', ['v.mp4'], dict(mode='1:1')),
          ('v_crop', ['hdr.mov'], dict(mode='9:16')), ('v_rotate', ['v.mp4'], dict(op='cw')), ('v_rotate', ['v.mp4'], dict(op='ccw', fast=True)),
          ('v_speed', ['v.mp4'], dict(speed=2)), ('v_wm_text', ['v.mp4'], dict(text='© 測試 100% test:1')), ('v_wm_img', ['v.mp4'], dict(logo=S('logo.png'))),
          ('v_delogo', ['v.mp4'], dict(rect='1000,40,200,80')), ('v_subs', ['v.mp4'], dict(sub=S('sub.srt'), mode='burn')), ('v_subs', ['v.mp4'], dict(sub=S('sub.srt'), mode='soft')),
          ('v_audio', ['v.mp4'], dict(music=S('song.mp3'))), ('v_mute', ['v.mp4'], {}), ('v_split', ['v.mp4'], dict(mode='every', sec=3)),
          ('v_stab', ['v.mp4'], {}), ('v_enhance', ['v.mp4'], dict(bright=10, denoise='1')), ('v_fade', ['v.mp4'], {}), ('v_reverse', ['v.mp4'], {}),
          ('v_frames', ['v.mp4'], dict(mode='sheet')), ('v_grid', ['v.mp4', 'vert.mp4'], dict(layout='h', size='480')),
          ('a_volume', ['song.mp3'], dict(gain=3, fout=2)), ('a_pitch', ['song.mp3'], dict(semi=2)), ('a_vocal', ['song.mp3'], {}), ('a_denoise', ['song.mp3'], {}),
          ('a_silence', ['song.mp3'], {}), ('a_mix', ['song.mp3', 'a.wav'], {}), ('a_ringtone', ['song.mp3'], dict(len=5)), ('a_tags', ['song.mp3'], dict(title='測試', cover=S('img0.jpg'))),
          ('i_resize', ['img1.jpg'], dict(val=800)), ('i_rotate', ['img1.jpg'], dict(op='cw', crop='1:1')), ('i_watermark', ['img1.jpg'], dict(pos='tile')),
          ('i_collage', ['img0.jpg', 'img1.jpg', 'img2.jpg'], {}), ('i_slideshow', ['img0.jpg', 'img1.jpg', 'img2.jpg'], dict(sec=2, size='1280x720')), ('i_gif', ['img0.jpg', 'img1.jpg'], {}),
          ('p_split', ['doc6.pdf'], {}), ('p_pages', ['doc6.pdf'], dict(pages='5,1-2')), ('p_rotate', ['doc6.pdf'], {}), ('p_encrypt', ['doc6.pdf'], dict(pw='1234')),
          ('x_privacy', ['img0.jpg'], {}), ('x_privacy', ['v.mp4'], {}), ('x_privacy', ['doc6.pdf'], {})]
    for tool, fs, o in tl:
        t = T.TOOL[tool]
        defaults = {f['k']: f['default'] for f in t['fields']}
        ids = eng.submit_tool(tool, [S(f) for f in fs], dict(defaults, **o, out_dir=out), t['name'], together=bool(t.get('together')), heavy=tool in T.HEAVY)
        wait(ids); report(f"{t['name']} {o if o else ''}"[:34], ids)

    if '--ai' in flags:
        log('\n── AI 字幕 ──')
        wav = S('speech.wav')
        ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              "$v=$s.GetInstalledVoices()|?{$_.VoiceInfo.Culture.Name -like 'zh*'}|select -First 1; if($v){$s.SelectVoice($v.VoiceInfo.Name)}; "
              f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('今天天氣很好，我們一起去公園散步。這是四維八德的語音辨識測試。'); $s.Dispose()")
        subprocess.run(['powershell', '-NoProfile', '-Command', ps], creationflags=E.NOWIN)
        if os.path.isfile(wav):
            ids = eng.submit_tool('v_autosub', [wav], dict(lang='zh', model='base', trad=True, out='srt', out_dir=out), 'AI 自動字幕'); wait(ids, 1800); report('AI 自動字幕（base 模型）', ids)
            j = eng.jobs[ids[0]]
            if j.state == 'done': log('辨識結果：\n' + open(j.output, encoding='utf-8-sig').read())
        else: log('SKIP 無法用 Windows 語音產生測試音檔')

    if '--rec' in flags:
        log('\n── 螢幕錄影（3 秒）──')
        r = C.Recorder(eng)
        try:
            jid = r.start(dict(out_dir=out, fps=30, monitor=0, audio=[])); time.sleep(3.5); r.stop()
            report('螢幕錄影', [jid])
        except Exception as e: log(f'FAIL 螢幕錄影  {e}'); results.append(False)

    # cancel test
    def slow_cancel_test(eng, j, o):
        eng._exec(j, [E.FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-re', '-i', j.files[0], '-f', 'null', '-'], 8)
    T.RUN['__cancel_test'] = slow_cancel_test
    ids = eng.submit_tool('__cancel_test', [S('v.mp4')], {}, '取消測試')
    deadline = time.time() + 10
    while eng.jobs[ids[0]].proc is None and time.time() < deadline: time.sleep(.02)
    eng.cancel(ids[0]); wait(ids); T.RUN.pop('__cancel_test', None)
    ok = eng.jobs[ids[0]].state == 'cancelled'; results.append(ok); log(f"\n{'OK  ' if ok else 'FAIL'} 取消工作")
    n = len(results); bad = n - sum(results)
    log(f'\n結果：{n - bad} / {n} 通過' + ('' if not bad else f'，{bad} 項失敗（詳細原因見上方 FAIL 與 logs\\zdgc.log）'))
    logf.close()
    try: os.startfile(root)
    except Exception: pass
    eng.pool.shutdown(wait=True); eng.light.shutdown(wait=True)
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
