"""驗證 C++ 接手的工具箱路由（run_tool → 原生工具工作）與 Python 版等價。

目前涵蓋 p_remove／p_extract／p_organize（含 order／reverse／blank 三種模式）。

比對方式：
  1. 輸出檔名（Python 的 output()：<來源檔名>_<工具名稱>.pdf）必須相同；
  2. 頁數、逐頁文字、逐頁圖片像素必須相同；
  3. 狀態、encoder、validation 字串相同；
  4. 錯誤情況的訊息一字不差。
C++ 這一側走的是正式路由：wiring 探針的 --run-tool → api_request → C++ run_tool →
eng_submit_tool → 引擎的原生工具工作（探針沒有 Python 核心，所以選項用產品預設值）。

用法（需 PYTHONPATH 指向 _build\\vendor 與 _build\\src）：
    check_pdf_tools.py <swbd-cpp-wiring.exe> <base_dir> <work_dir>
"""
import json
import os
import shutil
import subprocess
import sys

# 主控台可能是 cp950；工具訊息含非 Big5 字元時，print 不該讓閘門崩潰。
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_pdf_rewrite as LIB          # noqa: E402  （make_fixture 與 describe）

NOWIN = 0x08000000


def probe_run_tool(wire, base, work, tool, files, out_dir, params):
    args = [tool, list(files), dict(params, out_dir=out_dir, hwaccel=False, resource_mode='quiet', preset='balanced')]
    args_file = os.path.join(work, 'tool-args.json')
    with open(args_file, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(args, ensure_ascii=False))
    extra = ['--fake-py'] if params.pop('fake_py', False) else []
    result = subprocess.run([wire, base, work, '--run-tool', args_file] + extra, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', creationflags=NOWIN, cwd=work, timeout=240)
    lines = (result.stdout or '').splitlines()
    job = None
    handled = None
    for line in lines:
        if line.startswith('run_tool_job='):
            job = json.loads(line[len('run_tool_job='):])
        elif line.startswith('run_tool handled='):
            handled = int(line.split('=')[1])
    return result.returncode, handled, job, lines


def python_run_tool(src, base, tool, files, out_dir, params):
    sys.path.insert(0, src)
    import engine as E
    import tools as T
    E.base_dir = lambda: base
    eng = E.Engine(1, light=1)
    try:
        opt = dict(preset='balanced', hwaccel=False, fastcopy=True, out_dir=out_dir,
                   codec='auto', verify_full=False, resource_mode='quiet')
        opt.update(params or {})
        job = E.Job(list(files), tool, opt, tool=tool)
        job.state = 'running'
        T.run(eng, job)
        # 引擎在工具跑完後才標記終態，validation 也由引擎的 validate() 決定（validation.check）。
        eng.validate(job)
        return {'state': 'done', 'output': job.output, 'encoder': job.encoder,
                'validation': job.validation, 'msg': '完成', 'notes': list(job.notes)}
    except Exception as exc:                       # noqa: BLE001 - 就是要比對訊息
        return {'state': 'error', 'output': '', 'encoder': '', 'validation': '', 'msg': str(exc), 'notes': []}
    finally:
        eng.shutdown()


def compare_folders(cpp_dir, py_dir):
    """資料夾輸出：比對資料夾名稱、檔名清單，以及每個 PNG 的像素（PNG 無損，應該逐像素相同）。"""
    from PIL import Image
    ok = True
    cn, pn = sorted(os.listdir(cpp_dir)), sorted(os.listdir(py_dir))
    if os.path.basename(cpp_dir) != os.path.basename(py_dir):
        print('  FAIL：資料夾名稱不同（%s vs %s）' % (os.path.basename(cpp_dir), os.path.basename(py_dir)))
        ok = False
    else:
        print('  資料夾名稱相同：%s' % os.path.basename(cpp_dir))
    if cn != pn:
        print('  FAIL：檔名清單不同\n    C++   ：%s\n    Python：%s' % (cn[:5], pn[:5]))
        return False
    print('  檔名清單相同：%d 個檔案（%s …）' % (len(cn), cn[0] if cn else ''))
    for name in cn:
        cpp_file, py_file = os.path.join(cpp_dir, name), os.path.join(py_dir, name)
        lower = name.lower()
        if lower.endswith('.json'):
            cpp_data = json.load(open(cpp_file, encoding='utf-8'))
            py_data = json.load(open(py_file, encoding='utf-8'))
            if cpp_data != py_data:
                print('  FAIL：%s 的內容不同\n    C++   ：%s\n    Python：%s' % (name, cpp_data, py_data))
                ok = False
            else:
                print('  報告相同：%s' % name)
        elif lower.endswith('.pdf'):
            cpp_pages, cpp_texts, cpp_images = LIB.describe(cpp_file)
            py_pages, py_texts, py_images = LIB.describe(py_file)
            if (cpp_pages, cpp_texts, cpp_images) != (py_pages, py_texts, py_images):
                print('  FAIL：%s 的頁數／文字／圖片不同（C++ %d 頁 vs Python %d 頁）' % (name, cpp_pages, py_pages))
                ok = False
            else:
                print('  %s：%d 頁、逐頁文字與圖片都相同' % (name, cpp_pages))
        else:
            with Image.open(cpp_file) as cpp_im, Image.open(py_file) as py_im:
                cpp_size, py_size = cpp_im.size, py_im.size
                same = cpp_size == py_size and cpp_im.convert('RGB').tobytes() == py_im.convert('RGB').tobytes()
            if not same:
                print('  FAIL：%s 的尺寸或像素不同（C++ %s vs Python %s）' % (name, cpp_size, py_size))
                ok = False
    if ok and cn:
        print('  PASS：%d 個檔案的內容都相同' % len(cn))
    return ok


def clean_dir(path):
    if os.path.isdir(path):
        for name in os.listdir(path):
            target = os.path.join(path, name)
            if os.path.isfile(target):
                os.remove(target)
    else:
        os.makedirs(path, exist_ok=True)


CASES = [
    ('p_copy', '複製 PDF（須逐位元相同）', {}),
    # 壓平要有意義，素材必須帶註記（見下方 fixtures['d']）。
    ('p_flatten', '壓平註記與表單', {'files': ['d']}),
    # p_pdf_images 目前交回 Python：原生渲染的檔名與尺寸都對，但像素與 PyMuPDF 不同
    # （7.23% 通道差異、最大 255、集中在內容區），釐清前不接手。
    # p_repair 交回 Python：有效檔的第一條路徑（qpdf 復原）兩邊一致，但損壞檔的
    # 第二條路徑（Python 用 MuPDF 逐頁復原）救得回頁面，而 PDFium 連開檔都失敗
    # （截斷的 xref）→ 接手會是功能退步。
    ('p_repair', '修復有效 PDF（交回 Python）', {'files': ['a'], 'relay': True}),
    ('p_repair', '修復損壞 PDF（交回 Python）', {'files': ['e'], 'relay': True}),
    ('p_pdf_images', '每頁轉 PNG（交回 Python）', {'mode': 'pages', 'fmt': 'png', 'dpi': '96', 'relay': True}),
    ('p_pdf_images', '每頁轉 JPG（交回 Python）', {'mode': 'pages', 'fmt': 'jpg', 'dpi': '96', 'relay': True}),
    ('p_compress', '無損壓縮（原生）', {'level': 'lossless'}),
    # 非無損等級要重壓圖片（Pillow），刻意交回 Python：探針沒有 Python 核心，
    # 所以預期是請求層級的錯誤，這正好證明它沒有被原生接手。
    ('p_compress', '重壓圖片（交回 Python）', {'level': 'balanced', 'relay': True}),
    ('p_merge', '合併兩份（順序 A,B）', {'files': ['a', 'b']}),
    ('p_merge', '合併三份（順序 C,A,B）', {'files': ['c', 'a', 'b']}),
    # 這一項的守門在 app.run_tool（檔案數不足就丟錯，不會建立工作），所以比對的是請求層級的錯誤。
    ('p_merge', '只有一份（應拒絕）', {'files': ['a'], 'reject': '加入的檔案數不足'}),
    # 這一項讓探針注入 py_call，走過「反向呼叫 Python 取選項」的橋接路徑。
    ('p_remove', '移除單頁（走反向呼叫 Python）', {'pages': '2', 'fake_py': True}),
    ('p_remove', '移除 2,4-5', {'pages': '2,4-5'}),
    ('p_remove', '移除單頁', {'pages': '3'}),
    ('p_remove', '全部移除（應拒絕）', {'pages': '1-6'}),
    ('p_remove', '頁碼格式錯誤', {'pages': 'abc'}),
    ('p_remove', '頁碼超出範圍', {'pages': '9'}),
    ('p_remove', '空白＝全部（應拒絕）', {'pages': ''}),
    ('p_extract', '提取 3,1-2', {'pages': '3,1-2'}),
    ('p_extract', '提取並重複 2,2,5', {'pages': '2,2,5'}),
    ('p_organize', '整理：依輸入順序', {'mode': 'order', 'pages': '2-4,1'}),
    ('p_organize', '整理：反轉', {'mode': 'reverse', 'pages': ''}),
    ('p_organize', '整理：插入空白頁', {'mode': 'blank', 'pages': '2,4'}),
]


def main(argv):
    wire, base, work = argv[1], argv[2], argv[3]
    src = os.path.join(base, '_build', 'src')
    os.makedirs(work, exist_ok=True)
    os.chdir(work)
    failures = 0

    fixtures = {
        'a': (os.path.join(work, '工具箱 來源.pdf'), 6, 'T '),
        'b': (os.path.join(work, '合併來源 B.pdf'), 3, 'B '),
        'c': (os.path.join(work, '合併來源 C.pdf'), 4, 'C '),
    }
    for key, (path_, pages, tag) in fixtures.items():
        LIB.make_fixture(path_, pages=pages, label=tag)
    print('素材：%s' % ', '.join('%s(%d 頁)' % (os.path.basename(v[0]), v[1]) for v in fixtures.values()))

    # 壓平用的素材：複製一份再加上自由文字與螢光標記。
    import fitz
    annotated = os.path.join(work, '壓平來源 註記.pdf')
    shutil.copyfile(fixtures['a'][0], annotated)
    with fitz.open(annotated) as doc:
        page = doc[0]
        page.add_freetext_annot(fitz.Rect(60, 60, 320, 140), '壓平測試文字', fontsize=12)
        page.add_highlight_annot(fitz.Rect(60, 200, 320, 220))
        doc.save(annotated + '.tmp')
    os.replace(annotated + '.tmp', annotated)
    fixtures['d'] = (annotated, 6, 'D ')

    # 修復用的損壞素材：把結尾（含 %%EOF）截掉，逼 qpdf 走復原路徑。
    broken = os.path.join(work, '修復來源 損壞.pdf')
    raw = open(fixtures['a'][0], 'rb').read()
    open(broken, 'wb').write(raw[:int(len(raw) * 0.97)])
    fixtures['e'] = (broken, 6, 'E ')
    print('  損壞素材：%s（%d → %d bytes）' % (os.path.basename(broken), len(raw), os.path.getsize(broken)))
    print('  壓平素材：%s' % os.path.basename(annotated))

    for tool, label, params in CASES:
        chosen = params.pop('files', ['a'])
        reject = params.pop('reject', None)
        relay = params.pop('relay', False)
        folder_case = params.pop('folder', False)
        files = [fixtures[key][0] for key in chosen]
        cpp_dir = os.path.join(work, 'cpp', tool, label.replace('/', '_'))
        py_dir = os.path.join(work, 'py', tool, label.replace('/', '_'))
        clean_dir(cpp_dir)
        clean_dir(py_dir)

        code, handled, job, lines = probe_run_tool(wire, base, work, tool, files, cpp_dir, params)
        print('--- %s／%s ---' % (tool, label))
        if relay:
            reply_error = None
            for line in lines:
                if line.startswith('run_tool_reply='):
                    reply_error = (json.loads(line[len('run_tool_reply='):]) or {}).get('e')
            mark = 'OK  ' if reply_error and 'Python' in reply_error else 'FAIL'
            print('  %s 交回 Python → %r' % (mark, reply_error))
            if not (reply_error and 'Python' in reply_error):
                failures += 1
            continue
        if reject is not None:
            reply_error = None
            for line in lines:
                if line.startswith('run_tool_reply='):
                    reply_error = (json.loads(line[len('run_tool_reply='):]) or {}).get('e')
            mark = 'OK  ' if reply_error == reject else 'FAIL'
            print('  %s 請求層級拒絕 → %r' % (mark, reply_error))
            if reply_error != reject:
                print('       預期 %r' % reject)
                failures += 1
            continue
        if handled != 1 or not job:
            print('  FAIL：沒有走原生路由（handled=%s job=%s）' % (handled, job))
            print('      %s' % lines[-3:])
            failures += 1
            continue
        reference = python_run_tool(src, base, tool, files, py_dir, params)
        print('  C++   ：state=%s msg=%r encoder=%r validation=%r' %
              (job.get('state'), job.get('msg'), job.get('encoder'), job.get('validation')))
        print('  Python：state=%s msg=%r encoder=%r validation=%r' %
              (reference['state'], reference['msg'], reference['encoder'], reference['validation']))

        if (job.get('notes') or []) != (reference['notes'] or []):
            print('  FAIL：notes 不同（C++=%r Python=%r）' % (job.get('notes'), reference['notes']))
            failures += 1

        for key in ('msg', 'state', 'encoder', 'validation'):
            if (job.get(key) or '') != (reference[key] or ''):
                print('  FAIL：%s 不同（C++=%r Python=%r）' % (key, job.get(key), reference[key]))
                failures += 1

        cpp_out, py_out = job.get('output') or '', reference['output'] or ''
        if folder_case:
            if not (os.path.isdir(cpp_out) and os.path.isdir(py_out)):
                print('  FAIL：資料夾不存在（C++ %s / Python %s）' % (os.path.isdir(cpp_out), os.path.isdir(py_out)))
                failures += 1
            elif not compare_folders(cpp_out, py_out):
                failures += 1
            continue
        if bool(cpp_out) != bool(py_out):
            print('  FAIL：一邊有輸出、一邊沒有（%r vs %r）' % (cpp_out, py_out))
            failures += 1
        if not cpp_out or not py_out:
            continue
        if os.path.basename(cpp_out) != os.path.basename(py_out):
            print('  FAIL：輸出檔名不同（%s vs %s）' % (os.path.basename(cpp_out), os.path.basename(py_out)))
            failures += 1
        else:
            print('  檔名相同：%s' % os.path.basename(cpp_out))
        if not os.path.isfile(cpp_out) or not os.path.isfile(py_out):
            print('  FAIL：輸出檔不存在（%s / %s）' % (os.path.isfile(cpp_out), os.path.isfile(py_out)))
            failures += 1
            continue
        cpp_pages, cpp_texts, cpp_images = LIB.describe(cpp_out)
        py_pages, py_texts, py_images = LIB.describe(py_out)
        print('  頁數：C++ %d／Python %d' % (cpp_pages, py_pages))
        if cpp_pages != py_pages:
            print('  FAIL：頁數不同')
            failures += 1
        if cpp_texts != py_texts:
            print('  FAIL：逐頁文字不同')
            failures += 1
        if cpp_images != py_images:
            print('  FAIL：逐頁圖片不同')
            failures += 1
        if cpp_pages == py_pages and cpp_texts == py_texts and cpp_images == py_images:
            print('  PASS：頁數、逐頁文字、逐頁圖片都相同')
        if tool == 'p_copy':
            same_bytes = open(cpp_out, 'rb').read() == open(py_out, 'rb').read()
            print('  %s 複製內容逐位元相同' % ('PASS：' if same_bytes else 'FAIL：'))
            if not same_bytes:
                failures += 1
        print('  大小：C++ %d／Python %d bytes' % (os.path.getsize(cpp_out), os.path.getsize(py_out)))

    print()
    if failures == 0:
        print('PASS：原生 %d 個工具案例與 Python 版在輸出、訊息與狀態上都等價。' % len(CASES))
        return 0
    print('FAIL：%d 項不同' % failures)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
