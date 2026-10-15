"""PDF 渲染等價閘門的 Python 參考實作 —— 刻意走與 engine.py `_pdf_pages` 完全相同的路徑：
pypdfium2 的 `page.render(scale=dpi/72)` 加上 Pillow 存檔。

用法（需 PYTHONPATH 指向 _build\\vendor）：
    pdf_render_ref.py <pdf> <頁碼> <dpi> <輸出.png>     渲染一頁
    pdf_render_ref.py --compare <a.png> <b.png>          逐像素比對兩張圖
"""
import sys


def render(pdf_path, page, dpi, out_path):
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf_path)
    pg = doc[page - 1]
    bitmap = pg.render(scale=dpi / 72)
    img = bitmap.to_pil().copy()
    bitmap.close()
    pg.close()
    doc.close()
    img.save(out_path)
    print('已寫入 %s  %s  %s' % (out_path, img.size, img.mode))


def compare(a_path, b_path):
    from PIL import Image, ImageChops

    a = Image.open(a_path)
    b = Image.open(b_path)
    print('C++  ：%s %s' % (a.size, a.mode))
    print('Python：%s %s' % (b.size, b.mode))
    if a.size != b.size:
        print('FAIL：尺寸不同')
        return 1
    if a.mode != b.mode:
        a = a.convert('RGBA')
        b = b.convert('RGBA')
        print('（模式不同，已轉成 RGBA 再比對）')
    diff = ImageChops.difference(a, b)
    box = diff.getbbox()
    if box is None:
        print('PASS：逐像素完全相同')
        return 0
    # 統計差異，方便判斷是旗標差異還是系統性偏移
    hist = diff.convert('L').histogram()
    pixels = sum(hist)
    changed = pixels - hist[0]
    print('FAIL：不同像素 %d / %d（%.4f%%），差異範圍 %s' % (changed, pixels, 100.0 * changed / max(1, pixels), box))
    return 1


def main(argv):
    if len(argv) == 4 and argv[1] == '--compare':
        return compare(argv[2], argv[3])
    if len(argv) == 5:
        render(argv[1], int(argv[2]), float(argv[3]), argv[4])
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
