"""PDF 原生層等價閘門的 Python 參考實作（pymupdf）。

用法（需 PYTHONPATH 指向 _build\\vendor）：
    pdf_ref.py --make <路徑>              產生測試用 PDF
    pdf_ref.py --out <json> <pdf> [...]   以 UTF-8 寫出與原生探針相同形狀的 JSON（每檔一行）

刻意自己寫檔而不是靠 stdout 重導：Windows 上 Python 的 stdout 會用 locale 編碼（cp950），
中文中繼資料會被弄壞；由程式以 encoding='utf-8' 寫檔最穩。
"""
import json
import os
import sys

FIELDS = ('file', 'pages', 'title', 'author', 'producer', 'creator')


def make(path):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), 'SiWeiBaDe PDF probe', fontsize=18)
    second = doc.new_page(width=400, height=600)
    second.insert_text((40, 60), 'second page', fontsize=12)
    doc.set_metadata({'title': '四維八德測試文件', 'author': 'probe',
                      'producer': 'pymupdf', 'creator': 'probe'})
    doc.save(path)
    doc.close()


def describe(path):
    import pymupdf

    doc = pymupdf.open(path)
    meta = doc.metadata or {}
    out = {
        'file': os.path.basename(path),
        'pages': doc.page_count,
        'sizes': [[round(page.rect.width, 2), round(page.rect.height, 2)] for page in doc],
        'title': meta.get('title') or '',
        'author': meta.get('author') or '',
        'producer': meta.get('producer') or '',
        'creator': meta.get('creator') or '',
    }
    doc.close()
    return out


def main(argv):
    if len(argv) >= 3 and argv[1] == '--make':
        make(argv[2])
        print('已產生', argv[2])
        return 0
    if len(argv) >= 4 and argv[1] == '--out':
        target, sources = argv[2], argv[3:]
        with open(target, 'w', encoding='utf-8', newline='\n') as handle:
            for path in sources:
                handle.write(json.dumps(describe(path), ensure_ascii=False) + '\n')
        print('已寫入', target)
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
