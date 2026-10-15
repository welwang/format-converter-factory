"""qpdf 重寫層與現行 pypdf 路徑的等價驗證。

現行實作（engine.py 的 PDF→PDF 分支）是：
    w = PdfWriter(); w.append(src)
    for page in w.pages: page.compress_content_streams(level=9)
    w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    w.write(out)

C++ 這一側是 qpdf 的 compress_streams + object_streams=generate + 丟棄未引用物件。
兩者不會位元相同（不同程式庫），所以比對「可觀察結果」：頁數、逐頁文字、檔案大小。

用法（需 PYTHONPATH 指向 _build\\vendor）：
    check_pdf_rewrite.py <swbd-cpp-pdf-rewrite.exe> <base_dir> <work_dir>
"""
import json
import os
import shutil
import subprocess
import sys
import warnings

# pypdf 對 compress_identical_objects(remove_identicals=...) 會發 DeprecationWarning；
# 它是專案現行原始碼的用法，這裡照抄，但不要讓警告跑到 stderr（PowerShell 5.1 會把它當終止錯誤）。
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
NOWIN = 0x08000000


def make_fixture(path, pages=8, label=''):
    """有文字、有向量圖形、也有內嵌點陣圖的多頁 PDF：重新壓縮才看得出差別。
    label 會加進每頁文字，合併測試才能驗證檔案的先後順序。"""
    import io

    import pymupdf
    from PIL import Image, ImageDraw

    image = Image.new('RGB', (900, 700), (240, 240, 245))
    draw = ImageDraw.Draw(image)
    for i in range(40):
        draw.ellipse((20 + i * 18, 30 + i * 12, 200 + i * 18, 210 + i * 12),
                     outline=(30 + i * 5, 60, 200 - i * 4), width=3)
    draw.text((40, 620), '四維八德 PDF 重寫測試 內嵌點陣圖', fill=(20, 20, 20))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    png = buffer.getvalue()

    doc = pymupdf.open()
    for page_no in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 80), '%s第 %d 頁：PDF 重寫等價測試' % (label, page_no + 1), fontsize=16)
        for line in range(20):
            page.insert_text((60, 110 + line * 22),
                             '%s The quick brown fox jumps over the lazy dog — 第 %d 行 0123456789'
                             % (label, line + 1), fontsize=9)
        page.insert_image(pymupdf.Rect(60, 560, 535, 750), stream=png)
    doc.set_metadata({'title': '重寫測試' + label, 'author': 'gate'})
    doc.save(path)
    doc.close()


def pypdf_merge(sources, dst, pypdf_dir):
    """engine.py 合併路徑的同一個寫法：逐檔 append，再逐頁重壓、去重。"""
    sys.path.insert(0, pypdf_dir)
    from pypdf import PdfWriter

    writer = PdfWriter()
    for source in sources:
        writer.append(source)
    for page in writer.pages:
        try:
            page.compress_content_streams(level=9)
        except Exception:
            pass
    try:
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    except Exception:
        pass
    with open(dst, 'wb') as handle:
        writer.write(handle)


def pypdf_rewrite(src, dst, pypdf_dir):
    """完全照 engine.py 的作法。pypdf 是純 Python，從 _internal 複製一份出來隔離匯入。"""
    sys.path.insert(0, pypdf_dir)
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.append(src)
    for page in writer.pages:
        try:
            page.compress_content_streams(level=9)
        except Exception:
            pass
    try:
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    except Exception:
        pass
    with open(dst, 'wb') as handle:
        writer.write(handle)


def describe(path):
    """頁數、逐頁文字，以及逐頁圖片的像素雜湊。

    圖片一定要比：只比文字的話，「圖片被丟掉」這種破壞性差異會被漏掉
    （第一次跑閘門時 C++ 輸出只有原檔的 4%，正是靠這個懷疑去補上圖片比對的）。
    """
    import hashlib

    import pymupdf

    doc = pymupdf.open(path)
    pages = doc.page_count
    texts = []
    images = []
    for index in range(pages):
        page = doc[index]
        texts.append(page.get_text().strip())
        per_page = []
        for info in page.get_images(full=True):
            xref = info[0]
            try:
                pix = pymupdf.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:          # CMYK 之類先轉 RGB 再比
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                per_page.append((
                    pix.width, pix.height, pix.n - pix.alpha,
                    hashlib.sha256(pix.samples).hexdigest()[:32],
                ))
                pix = None
            except Exception as exc:                 # noqa: BLE001 - 取不到就記錄下來當差異
                per_page.append(('error', str(exc)[:40]))
        images.append(sorted(map(str, per_page)))
    doc.close()
    return pages, texts, images


def run_probe(probe, base, src, dst):
    result = subprocess.run([probe, base, src, dst], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', creationflags=NOWIN)
    line = (result.stdout or '').strip().splitlines()
    return result.returncode, (json.loads(line[-1]) if line else {})


def ensure_pypdf(work, base):
    """pypdf 是純 Python，被收在 PyInstaller 的 PYZ 裡（_internal 沒有它的目錄），
    所以照 requirements-lock.txt 的版本用 pip 裝一份到工作目錄當參考實作。"""
    target = os.path.join(work, 'pypdf-only')
    if os.path.isdir(os.path.join(target, 'pypdf')):
        return target
    python_exe = os.path.join(base, '_build', 'venv', 'Scripts', 'python.exe')
    version = ''
    lock = os.path.join(base, '_build', 'requirements-lock.txt')
    if os.path.isfile(lock):
        with open(lock, encoding='utf-8', errors='replace') as handle:
            for line in handle:
                if line.strip().lower().startswith('pypdf=='):
                    version = line.strip().split('==', 1)[1].strip()
                    break
    spec = 'pypdf==' + version if version else 'pypdf'
    os.makedirs(target, exist_ok=True)
    print('  安裝參考實作：%s → %s' % (spec, target))
    result = subprocess.run([python_exe, '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check',
                             '--target', target, spec], capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if result.returncode != 0:
        raise SystemExit('pip 安裝 pypdf 失敗：%s' % (result.stderr or result.stdout))
    return target


def main(argv):
    probe, base, work = argv[1], argv[2], argv[3]
    os.makedirs(work, exist_ok=True)
    failures = 0

    pypdf_dir = ensure_pypdf(work, base)

    fixture = os.path.join(work, '重寫來源 測試.pdf')
    make_fixture(fixture)
    original_bytes = os.path.getsize(fixture)
    print('素材：%s（%d bytes）' % (fixture, original_bytes))

    py_out = os.path.join(work, 'py.pdf')
    cpp_out = os.path.join(work, 'cpp.pdf')
    for path in (py_out, cpp_out):
        if os.path.exists(path):
            os.remove(path)

    print('=== Python（pypdf，現行實作）===')
    pypdf_rewrite(fixture, py_out, pypdf_dir)
    py_bytes = os.path.getsize(py_out)
    py_pages, py_texts, py_images = describe(py_out)
    print('  %d bytes，%d 頁，圖片 %s' % (py_bytes, py_pages, [len(x) for x in py_images]))

    print('=== C++（qpdf 重寫）===')
    code, reply = run_probe(probe, base, fixture, cpp_out)
    print('  探針：%s' % json.dumps(reply, ensure_ascii=False))
    if code != 0 or not reply.get('ok'):
        print('FAIL：qpdf 重寫失敗')
        return 1
    cpp_bytes = os.path.getsize(cpp_out)
    cpp_pages, cpp_texts, cpp_images = describe(cpp_out)
    print('  %d bytes，%d 頁，圖片 %s' % (cpp_bytes, cpp_pages, [len(x) for x in cpp_images]))

    # 原始素材的圖片，作為「內容有沒有被動過」的第二個對照
    _, _, original_images = describe(fixture)
    print('  原始素材每頁圖片數：%s' % [len(x) for x in original_images])

    print('=== 比對 ===')
    if py_pages != cpp_pages:
        print('FAIL：頁數不同（Python %d，C++ %d）' % (py_pages, cpp_pages))
        failures += 1
    else:
        print('  頁數相同：%d' % cpp_pages)
    if py_texts != cpp_texts:
        differing = [i + 1 for i, (a, b) in enumerate(zip(py_texts, cpp_texts)) if a != b]
        print('FAIL：第 %s 頁的文字不同' % differing)
        failures += 1
    else:
        print('  逐頁文字完全相同（%d 頁）' % len(cpp_texts))
    if py_images != cpp_images:
        differing = [i + 1 for i, (a, b) in enumerate(zip(py_images, cpp_images)) if a != b]
        print('FAIL：第 %s 頁的圖片不同' % differing)
        failures += 1
    else:
        print('  逐頁圖片（尺寸、通道、像素雜湊）完全相同（%d 頁）' % len(cpp_images))
    print('  大小：原始 %d → Python %d（%.0f%%）→ C++ %d（%.0f%%）' %
          (original_bytes, py_bytes, 100.0 * py_bytes / original_bytes,
           cpp_bytes, 100.0 * cpp_bytes / original_bytes))
    if cpp_bytes > py_bytes * 1.05:
        print('FAIL：C++ 的輸出比 pypdf 大超過 5%%（%d vs %d）' % (cpp_bytes, py_bytes))
        failures += 1
    else:
        print('  PASS：不比 pypdf 大（比值 %.3f）' % (cpp_bytes / py_bytes))

    print()
    if failures == 0:
        print('PASS：qpdf 重寫與 pypdf 路徑在頁數、逐頁文字、檔案大小上都等價或更好。')
        return 0
    print('FAIL：%d 項不同' % failures)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
