"""驗證新接手的三個頁面方法（drives／open_file／reveal）與 Python 版等價。

比對的是「可觀察的輸出」：drives 的完整清單、以及不存在路徑時的錯誤字串
（橋接層把例外轉成 {"ok":false,"e":...}，所以字串必須一字不差）。

用法（需 PYTHONPATH 指向 _build\\vendor 與 _build\\src）：
    check_shell_actions.py <swbd-cpp-probe.exe> <base_dir> <work_dir>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
NOWIN = 0x08000000


def probe_run(probe, base, work, method, args_file=None, cwd=None):
    cmd = [probe, base, work, method]
    if args_file:
        cmd += ['--args', args_file]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', creationflags=NOWIN, cwd=cwd)
    return result.returncode, (result.stdout or '').strip(), (result.stderr or '').strip()


def write_args(path, payload):
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))


def python_drives(src_dir):
    sys.path.insert(0, src_dir)
    import tools as T
    return T.list_drives()


def python_error(src_dir, func_name, value):
    sys.path.insert(0, src_dir)
    import file_actions as FA
    try:
        getattr(FA, func_name)(value)
    except Exception as exc:                      # noqa: BLE001 - 就是要比對錯誤字串
        return type(exc).__name__, str(exc)
    return None, None


def main(argv):
    probe, base, work = argv[1], argv[2], argv[3]
    src = os.path.join(base, '_build', 'src')
    os.makedirs(work, exist_ok=True)
    # 兩邊必須在同一個工作目錄：測試用的是相對路徑，就是要驗證 os.path.abspath 的正規化，
    # 若 cwd 不同，錯誤字串裡的絕對路徑自然會不一樣。
    os.chdir(work)
    failures = 0

    print('=== 1) drives：光碟機清單 ===')
    code, out, err = probe_run(probe, base, work, 'drives', cwd=work)
    if code == 3:
        print('FAIL：C++ 核心沒有接手 drives（%s）' % err)
        failures += 1
    else:
        reply = json.loads(out)
        native = reply.get('r')
        expected = python_drives(src)
        print('  C++   ：%s' % json.dumps(native, ensure_ascii=False))
        print('  Python：%s' % json.dumps(expected, ensure_ascii=False))
        if native != expected:
            print('FAIL：清單不同')
            failures += 1
        else:
            print('  PASS：完全相同')

    print('=== 2) 不存在路徑的錯誤字串（open_file／reveal）===')
    for method in ('open_file', 'reveal'):
        missing = '  不存在 的檔案 %s.txt  ' % method
        args_file = os.path.join(work, 'args-%s.json' % method)
        write_args(args_file, [missing])          # req.a 是參數陣列，open_file(path) → [path]
        code, out, err = probe_run(probe, base, work, method, args_file, cwd=work)
        if code == 3:
            print('FAIL：C++ 核心沒有接手 %s' % method)
            failures += 1
            continue
        reply = json.loads(out)
        native_msg = reply.get('e', '')
        _, expected_msg = python_error(src, method, missing)
        print('  %s' % method)
        print('    C++   ：%s' % native_msg)
        print('    Python：%s' % expected_msg)
        if native_msg != expected_msg:
            print('    FAIL：錯誤字串不同')
            failures += 1
        else:
            print('    PASS')

    print('=== 3) 非字串參數必須被拒絕（與 Python 相同的驗證）===')
    for method in ('open_file', 'reveal'):
        args_file = os.path.join(work, 'args-bad-%s.json' % method)
        write_args(args_file, [[]])               # 空陣列 → 沒有路徑
        code, out, err = probe_run(probe, base, work, method, args_file, cwd=work)
        reply = json.loads(out) if code != 3 else {}
        native_msg = reply.get('e', '')
        print('  %s → %s' % (method, native_msg))
        if native_msg != '沒有可開啟的檔案路徑':
            print('    FAIL：應該以「沒有可開啟的檔案路徑」拒絕')
            failures += 1
        else:
            print('    PASS')

    print()
    if failures == 0:
        print('PASS：drives／open_file／reveal 與 Python 版等價。')
        return 0
    print('FAIL：%d 項不同' % failures)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
