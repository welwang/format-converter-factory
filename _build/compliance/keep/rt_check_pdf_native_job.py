"""驗證 C 引擎的「PDF → 每頁 PNG」原生工作。

檢查三件事：
  1. 工作由 C 引擎完成（encoder = PDFium、state = done）。
  2. 輸出資料夾與檔名規則與 engine.py `_pdf_pages` 一致（資料夾＝檔名、001.png…）。
  3. 每一頁與 Python（pypdfium2 + Pillow）在相同 dpi 下**逐像素相同**。

用法（需 PYTHONPATH 指向 _build\\vendor）：
    check_pdf_native_job.py <engine-test.exe> <base_dir> <work_dir>
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf_ref as FIXTURE            # noqa: E402  （產生測試 PDF）
import pdf_render_ref as REFERENCE   # noqa: E402  （Python 參考渲染與比對）

NOWIN = 0x08000000
DPI = 150.0          # preset=balanced 對應的 dpi


def call(proc, request, timeout=180):
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
    os.makedirs(data, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        path = os.path.join(out_dir, name)
        if os.path.isfile(path):
            os.remove(path)
        else:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    pdf = os.path.join(work, '原生工作 測試.pdf')
    FIXTURE.make(pdf)
    print('素材：%s' % pdf)

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
    ids = call(proc, {'m': 'start', 'files': [pdf], 'target': 'png',
                      'opt': {'out_dir': out_dir, 'preset': 'balanced', 'resource_mode': 'quiet'},
                      'merge': False})
    job_id = ids[0] if isinstance(ids, list) and ids else None
    if not job_id:
        print('FAIL：start 沒有回傳工作 id：%r' % (ids,))
        return 1
    print('工作 id：%s' % job_id)

    job = wait_job(proc, job_id)
    print('狀態：%s  encoder=%s  progress=%s' % (job.get('state'), job.get('encoder'), job.get('progress')))
    if job.get('state') != 'done':
        print('FAIL：工作沒有完成（msg=%s）' % job.get('msg'))
        failures += 1
    if job.get('encoder') != 'PDFium':
        print('FAIL：encoder 不是 PDFium（%r）' % job.get('encoder'))
        failures += 1

    folder = job.get('output') or ''
    print('輸出資料夾：%s' % folder)
    expected_folder = os.path.join(out_dir, os.path.splitext(os.path.basename(pdf))[0])
    if os.path.normcase(os.path.normpath(folder)) != os.path.normcase(os.path.normpath(expected_folder)):
        print('FAIL：資料夾命名與 Python 版不同（預期 %s）' % expected_folder)
        failures += 1

    names = sorted(os.listdir(folder)) if folder and os.path.isdir(folder) else []
    print('輸出檔案：%s' % names)
    if names != ['001.png', '002.png']:
        print('FAIL：檔名規則不符（預期 001.png、002.png）')
        failures += 1
    else:
        for index, name in enumerate(names, 1):
            reference = os.path.join(work, 'ref-%d.png' % index)
            REFERENCE.render(pdf, index, DPI, reference)
            print('--- 第 %d 頁 ---' % index)
            if REFERENCE.compare(os.path.join(folder, name), reference) != 0:
                failures += 1

    call(proc, {'m': 'quit'})
    proc.stdin.close()
    proc.wait(timeout=15)

    print()
    if failures == 0:
        print('PASS：PDF→PNG 原生工作與 Python 版資料夾、檔名、逐頁像素全部相同。')
        return 0
    print('FAIL：%d 項不同' % failures)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
