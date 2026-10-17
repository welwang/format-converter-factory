"""驗證 C 引擎的「PDF → PDF（重新壓縮）」原生工作，以及分派政策。

檢查四件事：
  1. 分派政策矩陣：哪些 (cat,target,merge,preset) 由 C 引擎接手、哪些刻意留給 Python。
  2. 單檔 balanced 的 PDF→PDF 由 C 引擎完成（encoder = qpdf、state = done）。
  3. 輸出與原始檔的頁數、逐頁文字、逐頁圖片像素完全相同（只比文字會漏掉圖片被丟掉）。
  4. 原檔已經最小時走 Python 的退路：直接複製原檔，encoder 標示對應文字。

用法（需 PYTHONPATH 指向 _build\\vendor）：
    check_pdf_rewrite_job.py <engine-test.exe> <base_dir> <work_dir>
"""
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_pdf_rewrite as LIB          # noqa: E402  （describe：頁數／文字／圖片）

NOWIN = 0x08000000


def call(proc, request, timeout=300):
    proc.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
    proc.stdin.flush()
    try:
        line = proc._q.get(timeout=timeout)
    except queue.Empty:
        raise RuntimeError('引擎沒有回應：' + json.dumps(request, ensure_ascii=False))
    if not line:
        raise RuntimeError('引擎程序已結束：' + json.dumps(request, ensure_ascii=False))
    return json.loads(line)


def wait_job(proc, job_id, timeout=300):
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        for job in call(proc, {'m': 'status'}):
            if job.get('id') == job_id:
                last = job
                if job.get('state') not in ('queued', 'running'):
                    return job
        time.sleep(0.1)
    raise TimeoutError('等待工作逾時：%s / 最後狀態 %s' % (job_id, last))


def main(argv):
    exe, base, work = argv[1], argv[2], argv[3]
    data = os.path.join(work, 'data')
    out_dir = os.path.join(work, 'out')
    for path in (data, out_dir):
        os.makedirs(path, exist_ok=True)
    for name in os.listdir(out_dir):
        target = os.path.join(out_dir, name)
        if os.path.isfile(target):
            os.remove(target)
        else:
            shutil.rmtree(target, ignore_errors=True)

    proc = subprocess.Popen([exe, base, data], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=NOWIN)
    proc._q = queue.Queue()

    def reader():
        for line in proc.stdout:
            proc._q.put(line)
        proc._q.put('')

    threading.Thread(target=reader, daemon=True).start()
    proc.stdin.write(json.dumps({'base': base, 'data': data}, ensure_ascii=False) + '\n')
    proc.stdin.flush()

    failures = 0

    print('=== 1) 分派政策矩陣 ===')
    policy = [
        # (cat, target, merge, opt, 預期接手, 說明)
        ('pdf', 'png', False, {'preset': 'balanced'}, True, 'PDF→PNG：PDFium 逐像素等價且更快'),
        ('pdf', 'pdf', False, {'preset': 'balanced'}, True, 'PDF→PDF：qpdf 重寫，實測小 27 倍'),
        ('pdf', 'pdf', False, {'preset': 'high'}, True, '同上（high 不縮圖）'),
        ('pdf', 'pdf', False, {'preset': 'small'}, False, 'small 需要縮圖（_shrink_pdf_images），留在 Python'),
        ('pdf', 'pdf', True, {'preset': 'balanced'}, True, '合併：PDFium 組頁 + qpdf 重寫'),
        ('pdf', 'pdf', True, {'preset': 'small'}, False, '合併＋small 同樣需要縮圖，留在 Python'),
        ('pdf', 'jpg', False, {'preset': 'balanced'}, False, 'JPEG 編碼器不同，留在 Python'),
    ]
    for cat, target, merge, opt, expected, why in policy:
        got = bool(call(proc, {'m': 'handles', 'cat': cat, 'target': target, 'merge': merge, 'opt': opt}))
        mark = 'OK  ' if got == expected else 'FAIL'
        print('  %s %-4s→%-4s merge=%-5s preset=%-9s 接手=%s（預期 %s）　%s' %
              (mark, cat, target, merge, opt.get('preset', '-'), got, expected, why))
        if got != expected:
            failures += 1

    print('=== 2) 單檔 PDF→PDF 原生工作 ===')
    source = os.path.join(work, '重寫工作 測試.pdf')
    LIB.make_fixture(source)
    source_bytes = os.path.getsize(source)
    print('  素材：%s（%d bytes）' % (source, source_bytes))

    ids = call(proc, {'m': 'start', 'files': [source], 'target': 'pdf',
                      'opt': {'out_dir': out_dir, 'preset': 'balanced', 'resource_mode': 'quiet'},
                      'merge': False})
    job_id = ids[0] if isinstance(ids, list) and ids else None
    if not job_id:
        print('FAIL：start 沒有回傳工作 id：%r' % (ids,))
        return 1
    job = wait_job(proc, job_id)
    output = job.get('output') or ''
    print('  狀態：%s  encoder=%s' % (job.get('state'), job.get('encoder')))
    print('  輸出：%s' % output)
    if job.get('state') != 'done':
        print('FAIL：工作沒有完成（msg=%s）' % job.get('msg'))
        failures += 1
    if not (job.get('encoder') or '').startswith('qpdf'):
        print('FAIL：encoder 不是 qpdf（%r）' % job.get('encoder'))
        failures += 1
    if not output or not os.path.isfile(output):
        print('FAIL：輸出檔不存在')
        failures += 1
    else:
        if os.path.normcase(os.path.normpath(output)) == os.path.normcase(os.path.normpath(source)):
            print('FAIL：輸出覆蓋了來源檔')
            failures += 1
        if not output.lower().endswith('.pdf'):
            print('FAIL：輸出不是 .pdf（%s）' % output)
            failures += 1
        if os.path.dirname(os.path.normpath(output)) != os.path.normpath(out_dir):
            print('FAIL：輸出不在 out_dir 底下（%s）' % output)
            failures += 1

        print('=== 3) 內容等價（頁數／文字／圖片）===')
        src_pages, src_texts, src_images = LIB.describe(source)
        out_pages, out_texts, out_images = LIB.describe(output)
        print('  原始：%d 頁，每頁圖片 %s' % (src_pages, [len(x) for x in src_images]))
        print('  輸出：%d 頁，每頁圖片 %s' % (out_pages, [len(x) for x in out_images]))
        if src_pages != out_pages:
            print('FAIL：頁數不同（%d → %d）' % (src_pages, out_pages))
            failures += 1
        if src_texts != out_texts:
            differing = [i + 1 for i, (a, b) in enumerate(zip(src_texts, out_texts)) if a != b]
            print('FAIL：第 %s 頁文字不同' % differing)
            failures += 1
        if src_images != out_images:
            differing = [i + 1 for i, (a, b) in enumerate(zip(src_images, out_images)) if a != b]
            print('FAIL：第 %s 頁圖片不同' % differing)
            failures += 1
        if src_pages == out_pages and src_texts == out_texts and src_images == out_images:
            print('  PASS：頁數、逐頁文字、逐頁圖片像素全部相同')
        out_bytes = os.path.getsize(output)
        print('  大小：%d → %d（%.0f%%）' % (source_bytes, out_bytes, 100.0 * out_bytes / source_bytes))
        if out_bytes >= source_bytes:
            print('FAIL：重寫後沒有變小（應該走複製原檔的退路）')
            failures += 1

        print('=== 4) 原檔已最小時走複製退路 ===')
        mini = os.path.join(work, '已最小 來源.pdf')
        shutil.copyfile(output, mini)
        mini_bytes = os.path.getsize(mini)
        ids2 = call(proc, {'m': 'start', 'files': [mini], 'target': 'pdf',
                           'opt': {'out_dir': out_dir, 'preset': 'balanced', 'resource_mode': 'quiet'},
                           'merge': False})
        job2 = wait_job(proc, ids2[0] if isinstance(ids2, list) and ids2 else '')
        out2 = job2.get('output') or ''
        print('  狀態：%s  encoder=%s' % (job2.get('state'), job2.get('encoder')))
        if '複製' not in (job2.get('encoder') or ''):
            print('FAIL：encoder 沒有標示直接複製（%r）' % job2.get('encoder'))
            failures += 1
        if not out2 or not os.path.isfile(out2):
            print('FAIL：退路的輸出不存在')
            failures += 1
        else:
            same = open(mini, 'rb').read() == open(out2, 'rb').read()
            print('  與來源位元相同：%s（%d vs %d bytes）' % (same, mini_bytes, os.path.getsize(out2)))
            if not same:
                print('FAIL：退路應該是原檔的複製')
                failures += 1

    print('=== 5) 多檔合併：PDFium 組頁 ＋ qpdf 重寫 ===')
    parts = []
    for label, pages in (('A', 2), ('B', 3), ('C', 4)):
        part = os.path.join(work, '合併來源 %s.pdf' % label)
        LIB.make_fixture(part, pages=pages, label=label + ' ')
        parts.append(part)
    print('  來源：%s' % [os.path.basename(p) for p in parts])

    ids3 = call(proc, {'m': 'start', 'files': parts, 'target': 'pdf',
                       'opt': {'out_dir': out_dir, 'preset': 'balanced', 'resource_mode': 'quiet'},
                       'merge': True})
    job3 = wait_job(proc, ids3[0] if isinstance(ids3, list) and ids3 else '')
    out3 = job3.get('output') or ''
    print('  狀態：%s  encoder=%s' % (job3.get('state'), job3.get('encoder')))
    print('  輸出：%s' % out3)
    if job3.get('state') != 'done':
        print('FAIL：合併工作沒有完成（msg=%s）' % job3.get('msg'))
        failures += 1
    if job3.get('encoder') != 'PDFium+qpdf':
        print('FAIL：encoder 不是 PDFium+qpdf（%r）' % job3.get('encoder'))
        failures += 1
    if not out3 or not os.path.isfile(out3):
        print('FAIL：合併輸出不存在')
        failures += 1
    else:
        # 輸出檔名應該沿用第一個來源檔的名字（Python 的 out_path(j, files[0], 'pdf')）
        first_stem = os.path.splitext(os.path.basename(parts[0]))[0]
        if first_stem not in os.path.basename(out3):
            print('FAIL：輸出檔名沒有沿用第一個來源（%s）' % os.path.basename(out3))
            failures += 1
        # 與 Python 的 pypdf 合併路徑逐頁比對
        pypdf_dir = LIB.ensure_pypdf(work, base)
        py_merge = os.path.join(work, 'py-merge.pdf')
        LIB.pypdf_merge(parts, py_merge, pypdf_dir)
        ref_pages, ref_texts, ref_images = LIB.describe(py_merge)
        got_pages, got_texts, got_images = LIB.describe(out3)
        print('  頁數：Python %d／C++ %d（來源合計 %d）' % (ref_pages, got_pages, 2 + 3 + 4))
        if ref_pages != got_pages or got_pages != 9:
            print('FAIL：頁數不符')
            failures += 1
        if ref_texts != got_texts:
            differing = [i + 1 for i, (a, b) in enumerate(zip(ref_texts, got_texts)) if a != b]
            print('FAIL：第 %s 頁文字與 Python 合併結果不同' % differing)
            failures += 1
        else:
            print('  PASS：逐頁文字與 Python 合併結果完全相同（%d 頁）' % len(got_texts))
        if ref_images != got_images:
            differing = [i + 1 for i, (a, b) in enumerate(zip(ref_images, got_images)) if a != b]
            print('FAIL：第 %s 頁圖片與 Python 合併結果不同' % differing)
            failures += 1
        else:
            print('  PASS：逐頁圖片像素與 Python 合併結果完全相同')
        total_in = sum(os.path.getsize(p) for p in parts)
        print('  大小：來源合計 %d → Python %d（%.0f%%）→ C++ %d（%.0f%%）' %
              (total_in, os.path.getsize(py_merge), 100.0 * os.path.getsize(py_merge) / total_in,
               os.path.getsize(out3), 100.0 * os.path.getsize(out3) / total_in))
        if os.path.getsize(out3) > os.path.getsize(py_merge) * 1.05:
            print('FAIL：合併輸出比 pypdf 大超過 5%')
            failures += 1

    call(proc, {'m': 'quit'})
    proc.stdin.close()
    proc.wait(timeout=15)

    print()
    if failures == 0:
        print('PASS：PDF→PDF 原生工作（含合併）與分派政策都符合預期。')
        return 0
    print('FAIL：%d 項不同' % failures)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
