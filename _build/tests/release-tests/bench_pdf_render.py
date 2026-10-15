"""PDF → 每頁 PNG 的效能基準：C++ 原生工作 vs Python（pypdfium2 + Pillow）。

兩邊都跑「同一份 PDF、同一 dpi、逐頁渲染成 PNG」，量測總時間與每頁平均時間。
Python 這一側刻意只保留單執行緒的渲染＋存檔（engine.py 會用執行緒重疊存檔，
因此另外量一次「Python 多執行緒」當作實務值）。

用法（需 PYTHONPATH 指向 _build\\vendor）：
    bench_pdf_render.py <engine-test.exe> <base_dir> <work_dir> [頁數]
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NOWIN = 0x08000000
DPI = 150.0


def make_fixture(path, pages):
    """有文字也有向量圖形的多頁 PDF，避免量到「空白頁」這種不具代表性的情況。"""
    import pymupdf

    doc = pymupdf.open()
    for index in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 80), '四維八德 PDF 渲染基準第 %d 頁' % (index + 1), fontsize=16)
        for line in range(28):
            page.insert_text((60, 110 + line * 24),
                             'The quick brown fox jumps over the lazy dog 0123456789 — 第 %d 行' % (line + 1),
                             fontsize=9)
        for ring in range(12):
            page.draw_circle((160 + ring * 22, 640 + (ring % 3) * 18), 9 + ring, width=0.7,
                             color=(0.1 + ring / 20, 0.3, 0.7 - ring / 30))
        page.draw_rect(pymupdf.Rect(60, 700, 520, 780), width=1.2, color=(0.8, 0.2, 0.2))
    doc.set_metadata({'title': '渲染基準', 'author': 'bench'})
    doc.save(path)
    doc.close()


def time_python(pdf, out_dir, pages, workers=0):
    import pypdfium2 as pdfium

    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, name))
    doc = pdfium.PdfDocument(pdf)
    counter = {'done': 0}
    # PDFium 不是執行緒安全的：engine.py 用 PDFIUM_LOCK 把渲染序列化，這裡照做，
    # 否則多執行緒渲染同一份文件會直接讓行程崩潰（實測 0xC0000409）。
    pdfium_lock = threading.Lock()

    def render_one(index):
        with pdfium_lock:
            page = doc[index]
            bitmap = page.render(scale=DPI / 72)
            img = bitmap.to_pil().copy()
            bitmap.close()
            page.close()
        return index, img

    start = time.perf_counter()
    if workers <= 0:
        for index in range(pages):
            _, img = render_one(index)
            img.save(os.path.join(out_dir, '%03d.png' % (index + 1)), optimize=False)
            counter['done'] += 1
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = []
            for index in range(pages):
                pending.append(pool.submit(render_one, index))
                # 存檔與下一頁渲染重疊（engine.py 的做法）
                if len(pending) > workers:
                    done_index, img = pending.pop(0).result()
                    img.save(os.path.join(out_dir, '%03d.png' % (done_index + 1)), optimize=False)
            for future in pending:
                done_index, img = future.result()
                img.save(os.path.join(out_dir, '%03d.png' % (done_index + 1)), optimize=False)
    elapsed = time.perf_counter() - start
    doc.close()
    return elapsed


def time_native(exe, base, work, pdf, out_dir, data_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        path = os.path.join(out_dir, name)
        if os.path.isfile(path):
            os.remove(path)
        else:
            import shutil
            shutil.rmtree(path, ignore_errors=True)
    os.makedirs(data_dir, exist_ok=True)
    proc = subprocess.Popen([exe, base, data_dir], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=NOWIN)
    proc._q = queue.Queue()

    def reader():
        for line in proc.stdout:
            proc._q.put(line)
        proc._q.put('')

    threading.Thread(target=reader, daemon=True).start()
    proc.stdin.write(json.dumps({'base': base, 'data': data_dir}, ensure_ascii=False) + '\n')
    proc.stdin.flush()

    def call(request, timeout=900):
        proc.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
        proc.stdin.flush()
        return json.loads(proc._q.get(timeout=timeout))

    start = time.perf_counter()
    ids = call({'m': 'start', 'files': [pdf], 'target': 'png',
                'opt': {'out_dir': out_dir, 'preset': 'balanced', 'resource_mode': 'quiet'}, 'merge': False})
    job_id = ids[0]
    while True:
        job = [j for j in call({'m': 'status'}) if j.get('id') == job_id]
        if job and job[0].get('state') not in ('queued', 'running'):
            break
        time.sleep(0.05)
    elapsed = time.perf_counter() - start
    call({'m': 'quit'})
    proc.stdin.close()
    proc.wait(timeout=15)
    return elapsed, job[0]


def time_python_engine(base, work, pdf, out_dir, pages):
    """目前產品實際走的 Python 引擎工作（engine.py 的 PDF→PNG），與 C++ 工作對等比較：
    一樣含工作排隊、進度、輸出驗證。"""
    import shutil
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        path = os.path.join(out_dir, name)
        if os.path.isfile(path):
            os.remove(path)
        else:
            shutil.rmtree(path, ignore_errors=True)
    sys.path[:0] = [os.path.join(base, '_build', 'src'), os.path.join(base, '_build', 'vendor')]
    import engine as E
    E.base_dir = lambda: base          # 讓 engine 以專案根目錄解析 tools\
    eng = E.Engine(1, 1)
    try:
        start = time.perf_counter()
        ids = eng.submit([pdf], 'png', dict(out_dir=out_dir, preset='balanced', resource_mode='quiet'), merge=False)
        while any(eng.jobs[i].state in ('queued', 'running') for i in ids):
            time.sleep(0.05)
        elapsed = time.perf_counter() - start
        job = eng.jobs[ids[0]]
        return elapsed, job
    finally:
        eng.pool.shutdown(wait=True)
        eng.light.shutdown(wait=True)


def main(argv):
    exe, base, work = argv[1], argv[2], argv[3]
    pages = int(argv[4]) if len(argv) > 4 else 24
    os.makedirs(work, exist_ok=True)
    pdf = os.path.join(work, 'bench %d.pdf' % pages)
    make_fixture(pdf, pages)
    size = os.path.getsize(pdf)
    print('素材：%s（%d 頁，%.1f KB）' % (pdf, pages, size / 1024.0), flush=True)
    print()

    py1 = time_python(pdf, os.path.join(work, 'py1'), pages, 0)
    print('Python 單執行緒（純渲染＋存檔）          %6.2fs  每頁 %5.3fs' % (py1, py1 / pages), flush=True)
    py4 = time_python(pdf, os.path.join(work, 'py4'), pages, 4)
    print('Python 4 執行緒（engine.py 的做法）      %6.2fs  每頁 %5.3fs' % (py4, py4 / pages), flush=True)
    pyj, pyjob = time_python_engine(base, work, pdf, os.path.join(work, 'pyjob'), pages)
    print('Python 引擎工作（產品現況）              %6.2fs  每頁 %5.3fs  encoder=%s' %
          (pyj, pyj / pages, pyjob.encoder), flush=True)
    native, job = time_native(exe, base, work, pdf, os.path.join(work, 'cpp'),
                              os.path.join(work, 'data'))
    print('C++ 引擎工作（原生接手）                 %6.2fs  每頁 %5.3fs  encoder=%s' %
          (native, native / pages, job.get('encoder')), flush=True)
    print()
    print('C++ / Python 引擎工作 = %.2fx（>1 表示 C++ 較快）' % (pyj / native), flush=True)
    print('C++ / Python 純渲染   = %.2fx' % (py1 / native), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
