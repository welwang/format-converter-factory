"""等價測試的 Python 側：與 C++ 執行檔做完全相同的事，輸出相同結構的 JSON。
用法：python_ref.py <fixture_root> <data_dir> <temp_dir> <out.json>

注意：C++ 端的 temp_dir 由 TMPDIR/TEMP/TMP 或 GetTempPathW 決定；這裡直接指定
tempfile.tempdir，並把 E._DATA 指向 fixture 的 data 目錄，讓兩邊掃描同一組資料。
"""
import json
import os
import stat
import sys
import tempfile

SRC = r'E:\四維八德\_build\src'


def is_reparse(path):
    return bool(getattr(os.lstat(path), 'st_file_attributes', 0) & 0x400)


def listing(root):
    out = []
    for base, dirs, files in os.walk(root, followlinks=False):
        keep = []
        for name in dirs:
            path = os.path.join(base, name)
            out.append(os.path.relpath(path, root) + '\\')
            if not is_reparse(path):
                keep.append(name)
        dirs[:] = keep
        for name in files:
            out.append(os.path.relpath(os.path.join(base, name), root))
    out.sort()
    return out


def main():
    root, data, temp, out_path = sys.argv[1:5]
    root = os.path.abspath(root)

    # 讓 tempfile.gettempdir() 回傳 C++ 端也會用的同一個目錄
    tempfile.tempdir = temp
    for name in ('TMPDIR', 'TEMP', 'TMP'):
        os.environ[name] = temp

    sys.path.insert(0, SRC)
    import engine as E
    E._DATA = os.path.abspath(data)
    import system_tools as ST

    report = {'before': listing(root)}
    plan = ST.scan_cleanup(['app_temp', 'download_parts', 'logs', 'user_temp'])
    report['preview'] = ST.cleanup_preview(plan)
    report['execute'] = ST.execute_cleanup(plan, plan['token'])
    report['after'] = listing(root)
    report['plan_items'] = plan['items']          # 僅供診斷，不參與比對

    with open(out_path, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
