"""Delivery packs and reusable, ordered pipelines. All operations stay local."""
import os, json, time, shutil, tempfile, zipfile, re
import engine as E
import tools as T

RECIPES = [
    dict(id='share', name='附件分享包', desc='圖片、影音與文件轉成容易開啟的格式，檢查單檔容量並打包'),
    dict(id='product', name='商品上架包', desc='一次產生方形商品圖、網站 WebP 與縮圖，統一命名'),
    dict(id='video', name='客戶影片包', desc='同一支影片產生原比例、直式與方形版本，附縮圖'),
    dict(id='pipeline', name='自訂工具流程', desc='依順序串接工具，可保存為客戶配方並分享給同事'),
]

def clean_settings(value):
    if isinstance(value, dict): return {k: clean_settings(v) for k, v in value.items() if k.lower() not in ('pw', 'password', 'pfx_pw', 'token', 'cookies', 'cookie') and not (k=='data' and value.get('kind')=='signature') and not k.startswith('_')}
    if isinstance(value, list): return [clean_settings(v) for v in value]
    return value

def valid_profile(profile):
    if not isinstance(profile, dict): raise ValueError('配方內容無法辨識')
    name = str(profile.get('name') or '').strip()[:80]
    recipe = profile.get('recipe')
    if not name or recipe not in {r['id'] for r in RECIPES}: raise ValueError('請設定配方名稱與用途')
    options = profile.get('options') or {}
    if not isinstance(options, dict): raise ValueError('配方選項無法辨識')
    steps = options.get('steps') or []
    if not isinstance(steps, list) or len(steps) > 20: raise ValueError('流程最多 20 個步驟')
    for step in steps:
        if not isinstance(step, dict) or step.get('tool') not in T.TOOL: raise ValueError('配方包含不支援的工具')
        t = T.TOOL[step['tool']]
        if t.get('together') or 'disc' in t['accept']: raise ValueError('合成及光碟工具請在工具箱執行')
        if not isinstance(step.get('params', {}), dict): raise ValueError('步驟選項無法辨識')
        allowed = {f['k'] for f in t['fields']}
        if any(k not in allowed for k in step.get('params', {})): raise ValueError('配方包含不支援的參數')
    return dict(name=name, recipe=recipe, options=clean_settings(options))

def _name(prefix, idx, src):
    prefix = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(prefix or '')).strip(' .')[:60]
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', os.path.splitext(os.path.basename(src))[0]).strip(' .')[:80] or '素材'
    return f'{prefix + "_" if prefix else ""}{idx:03d}_{stem}'

def run(eng, job):
    recipe = job.opt.get('recipe', 'share')
    if recipe not in {r['id'] for r in RECIPES}: raise ValueError('找不到交付用途')
    if recipe == 'pipeline': valid_profile(dict(name='流程', recipe=recipe, options={'steps': job.opt.get('steps') or []}))
    root = job.opt.get('out_dir') or os.path.dirname(job.files[0])
    folder = E.unique_path(os.path.join(root, '交付包_' + time.strftime('%Y%m%d_%H%M%S')))
    os.makedirs(folder, exist_ok=False)
    job.output = folder; job.keep_output = True
    records = []
    def add(src, path, detail, state='done'):
        records.append(dict(source=src, output=os.path.relpath(path, folder) if path else '', state=state, check=detail))
    try:
        for idx, src in enumerate(job.files, 1):
            if job.cancelled: raise InterruptedError
            stem = _name(job.opt.get('prefix'), idx, src)
            job._file_base = (idx-1)/len(job.files)*.95; job._file_span = .95/len(job.files)
            job._child_base = job._file_base; job._child_span = job._file_span
            try:
                if recipe == 'product': _product(eng, job, src, stem, folder, add)
                elif recipe == 'video': _video(eng, job, src, stem, folder, add)
                elif recipe == 'share': _share(eng, job, src, stem, folder, add)
                else: _pipeline(eng, job, src, stem, folder, add)
            except InterruptedError: raise
            except Exception as ex:
                add(src, '', str(ex), 'error'); job.warnings.append(os.path.basename(src) + '：' + str(ex)[:120])
            job.progress = idx / len(job.files) * 0.95
        if job.opt.get('zip'):
            zp = os.path.join(folder, '交付檔案.zip')
            completed = [r['output'] for r in records if r['state'] == 'done']
            with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
                for rel in completed:
                    if job.cancelled: raise InterruptedError
                    path = os.path.join(folder, rel)
                    if os.path.isdir(path):
                        for rd, _, fs in os.walk(path):
                            for f in fs: z.write(os.path.join(rd, f), os.path.relpath(os.path.join(rd, f), folder))
                    else: z.write(path, rel)
            with zipfile.ZipFile(zp) as z:
                if z.testzip(): raise RuntimeError('交付 ZIP 完整性檢查失敗')
            total = float(job.opt.get('total_mb') or 0)
            if total and os.path.getsize(zp) > total * 1048576:
                job.warnings.append(f'交付 ZIP 超過整包 {total:g} MB 上限，請減少素材或調整規格')
        if not any(r['state'] == 'done' for r in records): raise RuntimeError('沒有素材完成交付，請查看資料夾中的交付報告')
        job.validation = f'{sum(r["state"] == "done" for r in records)} 個成品通過檢查'
        job.encoder = next(r['name'] for r in RECIPES if r['id'] == recipe)
    finally:
        job.child = None; job.output = folder
        payload = dict(recipe=recipe, version=1, created=time.strftime('%Y-%m-%d %H:%M:%S'), records=records, warnings=job.warnings, cancelled=job.cancelled)
        with open(os.path.join(folder, '交付報告.json'), 'w', encoding='utf-8') as fh: json.dump(payload, fh, ensure_ascii=False, indent=2)
        with open(os.path.join(folder, '交付報告.txt'), 'w', encoding='utf-8-sig') as fh:
            fh.write('四維八德交付報告\n' + '\n'.join(f'{"通過" if r["state"] == "done" else "失敗"} | {os.path.basename(r["source"])} | {r["output"]} | {r["check"]}' for r in records))
            if job.warnings: fh.write('\n提醒：\n' + '\n'.join(job.warnings))
            if job.cancelled: fh.write('\n工作已取消；已完成成品保留。')

def _convert(eng, parent, src, target, opt, dest):
    child = E.Job([src], target, opt); child._nested = True; parent.child = child
    if parent.cancelled: child.cancelled = True; raise InterruptedError
    eng._run(child)
    if parent.cancelled or child.state == 'cancelled': raise InterruptedError
    if child.state != 'done': raise RuntimeError(child.msg)
    ext = os.path.splitext(child.output)[1]
    dest = E.unique_path(dest + ext)
    shutil.move(child.output, dest)
    return dest, child.validation

def _share(eng, parent, src, stem, folder, add):
    cat, ext = E.classify(src)
    target = {'image':'jpg', 'video':'mp4', 'audio':'mp3', 'doc':'pdf', 'sheet':'pdf', 'pdf':'pdf', 'ebook':'epub', 'subtitle':'srt'}.get(cat)
    if not target: raise RuntimeError('附件配方不支援這類素材，請使用一般轉檔')
    out = os.path.join(folder, '附件'); os.makedirs(out, exist_ok=True)
    opt = dict(parent.opt, out_dir=out, preset='small', target_mb=float(parent.opt.get('max_mb') or 20), fastcopy=False)
    if cat == 'video': opt['height'] = min(720, E.probe_info(src)['height'] or 720)
    if cat == 'image': opt['height'] = 1600
    path, detail = _convert(eng, parent, src, target, opt, os.path.join(out, stem))
    add(src, path, detail)

def _product(eng, parent, src, stem, folder, add):
    if E.classify(src)[0] != 'image': raise RuntimeError('商品上架包只接受圖片')
    from PIL import Image, ImageOps, ImageDraw, ImageFont
    im = ImageOps.exif_transpose(T.open_img(src)); im = E.flatten(im)
    try:
        size = max(100, min(4000, int(parent.opt.get('size') or 1200)))
        for sub, ext, side in [('上架方形', 'jpg', size), ('網站圖片', 'webp', size), ('預覽縮圖', 'jpg', min(320, size))]:
            if parent.cancelled: raise InterruptedError
            contained = im.copy(); contained.thumbnail((side, side), Image.Resampling.LANCZOS)
            pic = Image.new('RGB', (side, side), 'white'); pic.paste(contained, ((side-contained.width)//2, (side-contained.height)//2)); contained.close()
            text = str(parent.opt.get('watermark') or '').strip()[:200]
            if text:
                font = ImageFont.truetype(T.find_font(), max(12, side // 28))
                ImageDraw.Draw(pic).text((side - 12, side - 12), text, font=font, anchor='rs', fill='white', stroke_width=2, stroke_fill='#333333')
            if parent.opt.get('logo'):
                with Image.open(parent.opt['logo']) as mark:
                    mark = mark.convert('RGBA'); mark.thumbnail((max(20, side // 5), max(20, side // 5)))
                    pic.paste(mark, (side - mark.width - 12, side - mark.height - 12), mark)
            d = os.path.join(folder, sub); os.makedirs(d, exist_ok=True)
            p = os.path.join(d, stem + '.' + ext)
            T.save_img(pic, p, parent.opt, im.info.get('icc_profile'))
            child = E.Job([src], ext, dict(_expected_size=[side, side])); child.output = p
            add(src, p, eng.validate(child) or child.validation)
            pic.close()
    finally: im.close()

def _video(eng, parent, src, stem, folder, add):
    if E.classify(src)[0] != 'video': raise RuntimeError('客戶影片包只接受影片')
    info = E.probe_info(src)
    tmp = tempfile.mkdtemp(prefix='zdgc_delivery_')
    try:
        sub = parent.opt.get('sub_file')
        if parent.opt.get('autosub'):
            opt = dict(parent.opt, out_dir=folder, out='srt', lang=parent.opt.get('lang', 'zh'), model=parent.opt.get('model', 'base'), trad=True)
            child = E.Job([src], 'v_autosub', opt, tool='v_autosub'); child._nested = True; parent.child = child; eng._run(child)
            if parent.cancelled or child.state == 'cancelled': raise InterruptedError
            if child.state != 'done': raise RuntimeError('AI 字幕：' + child.msg)
            sub = child.output; add(src, sub, child.validation)
        elif sub:
            sp = os.path.join(folder, stem + os.path.splitext(sub)[1]); shutil.copyfile(sub, sp)
            add(src, sp, '已複製使用者提供的字幕（未校對語意）')
        subtitle_filters = []
        if sub:
            normalized = os.path.join(tmp, 'captions' + os.path.splitext(sub)[1])
            with open(normalized, 'w', encoding='utf-8') as fh: fh.write(T.read_text_any(sub))
            subtitle_filters = [f"subtitles='{T.ffesc(normalized)}'"]
        text = str(parent.opt.get('watermark') or '').strip()[:200]
        watermark = []
        if text:
            tf = os.path.join(tmp, 'watermark.txt')
            with open(tf, 'w', encoding='utf-8') as fh: fh.write(text)
            font = T.find_font()
            if not font: raise RuntimeError('找不到中文字型')
            watermark = [f"drawtext=fontfile='{T.ffesc(font)}':textfile='{T.ffesc(tf)}':expansion=none:fontsize=h/28:fontcolor=white:box=1:boxcolor=black@0.4:x=w-tw-20:y=h-th-20"]
        side = int(parent.opt.get('video_size') or (480 if E.mem_gb() <= 4.5 else 720))
        if side not in (480, 720, 1080): raise ValueError('影片尺寸請選 480、720 或 1080')
        vertical = (round(side * 16 / 9) // 2) * 2
        variants = [('原比例', 0, 0), ('直式分享', side, vertical), ('方形分享', side, side)]
        for vi, (sub, w, h) in enumerate(variants):
            parent._child_base = parent._file_base + vi/4*parent._file_span; parent._child_span = parent._file_span/4
            parent.msg = '正在產生' + sub
            d = os.path.join(folder, sub); os.makedirs(d, exist_ok=True)
            vf = [f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1'] if w else []
            vf += watermark + subtitle_filters
            opt = dict(parent.opt, out_dir=d, target_mb=0, _vf=vf, _logo=parent.opt.get('logo'), fastcopy=not vf)
            path, detail = _convert(eng, parent, src, 'mp4', opt, os.path.join(d, stem))
            add(src, path, detail)
            parent.progress = parent._child_base + parent._child_span
        thumb = os.path.join(folder, stem + '_縮圖.jpg')
        child = E.Job([src], 'jpg', parent.opt); parent.child = child
        eng._proc(child, [E.FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-y', '-ss', str(max(0, info['dur'] * .2)), '-i', src,
                          '-frames:v', '1', '-vf', ','.join(E.hdr_filters(src) + ['scale=640:-2']), thumb], '縮圖')
        child.output = thumb; eng.validate(child); add(src, thumb, child.validation)
    finally: shutil.rmtree(tmp, ignore_errors=True)

def _pipeline(eng, parent, src, stem, folder, add):
    steps = parent.opt.get('steps') or []
    if not steps: raise RuntimeError('請加入至少一個處理步驟')
    tmp = tempfile.mkdtemp(prefix='zdgc_pipeline_'); current = src
    try:
        for si, step in enumerate(steps):
            if parent.cancelled: raise InterruptedError
            t = T.TOOL[step['tool']]
            parent._child_base = parent._file_base + si/len(steps)*parent._file_span; parent._child_span=parent._file_span/len(steps)
            parent.msg = '正在處理' + t['name']
            if E.classify(current)[0] not in t['accept']: raise RuntimeError(t['name'] + '不支援上一個步驟的輸出類型')
            defaults = {f['k']: f['default'] for f in t['fields']}
            opt = dict(parent.opt, **dict(defaults, **step.get('params', {}))); opt['out_dir'] = tmp
            child = E.Job([current], step['tool'], opt, tool=step['tool'], label=t['name']); child._nested = True; parent.child = child
            eng._run(child)
            if parent.cancelled or child.state == 'cancelled': raise InterruptedError
            if child.state != 'done': raise RuntimeError(t['name'] + '：' + child.msg)
            if not os.path.isfile(child.output): raise RuntimeError('產生多檔案的工具請放在工具箱執行')
            current = child.output
            parent.progress=parent._child_base+parent._child_span
        dest = E.unique_path(os.path.join(folder, stem + os.path.splitext(current)[1])); shutil.move(current, dest)
        add(src, dest, child.validation)
        if E.classify(src)[0] in ('video', 'audio') and len(steps) > 1: parent.warnings.append('工具流程按步驟處理，部分影音工具會重新編碼；交付包的縮放與文字浮水印已合併編碼。')
    finally: shutil.rmtree(tmp, ignore_errors=True)
