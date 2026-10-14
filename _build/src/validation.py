"""Output checks shared by converters and delivery workflows."""
import os
import engine as E

def check(eng, job):
    path = job.output
    if not path or not os.path.exists(path): raise RuntimeError('沒有產生輸出檔案')
    if os.path.isdir(path):
        files = [os.path.join(r, f) for r, _, fs in os.walk(path) for f in fs]
        if not files: raise RuntimeError('輸出資料夾是空的')
        for f in files:
            if job.cancelled: raise InterruptedError
            check_file(eng, job, f, {})
        return f'已檢查 {len(files)} 個輸出檔案'
    return check_file(eng, job, path, job.opt)

def check_file(eng, job, path, opt):
    size = os.path.getsize(path)
    if size <= 0: raise RuntimeError('輸出檔案是空的')
    cap = float(opt.get('target_mb') or 0)
    if cap and size > cap * 1048576:
        raise RuntimeError(f'未達目標大小：實際 {size / 1048576:.3f} MB，目標 {cap:g} MB。請降低解析度或提高容量上限；已保留成品供檢查。')
    cat, ext = E.classify(path)
    detail = '檔案已產生'
    if cat == 'image':
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size; im.verify()
        if opt.get('_expected_size') and [w, h] != list(opt['_expected_size']): raise RuntimeError('圖片尺寸未符合交付規格')
        detail = f'圖片可讀取 · {w}×{h}'
    elif cat in ('video', 'audio'):
        info = E.probe_info(path)
        if not info['streams']: raise RuntimeError('輸出沒有可讀取的影音串流')
        if cat == 'video' and not any(k == 'video' for k, _ in info['streams']): raise RuntimeError('輸出沒有影像軌')
        codec = opt.get('codec', 'auto')
        if ext in ('mp4', 'mov', 'mkv') and codec != 'auto' and ('video', codec) not in info['streams']: raise RuntimeError('影片編碼未符合指定格式')
        if opt.get('verify_full'):
            eng._proc(job, [E.FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-xerror', '-i', path, '-map', '0:v?', '-map', '0:a?', '-f', 'null', '-'], '完整影音解碼檢查')
            detail = '完整解碼檢查通過'
        else: detail = '影音串流可讀取（未做全片解碼）'
    elif cat == 'pdf':
        from pypdf import PdfReader
        with open(path, 'rb') as fh:
            reader = PdfReader(fh)
            if reader.is_encrypted: detail = '加密 PDF 結構可讀取'
            elif len(reader.pages) <= 0: raise RuntimeError('PDF 沒有頁面')
            else: detail = f'PDF 可讀取 · {len(reader.pages)} 頁'
    elif cat == 'archive' and E.SEVENZIP:
        eng._proc(job, [E.SEVENZIP, 't', '-bso0', '-bsp0', path], '壓縮檔完整性檢查')
        detail = '壓縮檔完整性檢查通過'
    if cap: detail += ' · 容量符合上限'
    return detail
