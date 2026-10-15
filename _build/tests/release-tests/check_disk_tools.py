"""驗證 C++ 接手的磁碟工具（disk_info／disk_preview／disk_launch）與 Python 版等價。

比對原則：
  disk_info    — 磁碟順序、代號、檔案系統、磁碟編號必須完全相同；free 會變動，允許小差距。
  disk_preview — 與 disk_tools.plan() 的回傳逐欄相同（token／created 是每次不同的值，不比）；
                 錯誤情況（不支援的操作、格式不對的磁碟、不存在的磁碟）訊息必須一字不差。
  disk_launch  — 只驗證「應該拒絕」的路徑（沒有預覽、token 不對、未確認）。
                 真的啟動會跳出 UAC 並開 chkdsk 視窗，自動測試刻意不做。
另以 WMI（Win32_LogicalDisk）當獨立來源交叉驗證磁碟清單。

用法（需 PYTHONPATH 指向 _build\\vendor 與 _build\\src）：
    check_disk_tools.py <swbd-cpp-probe.exe> <base_dir> <work_dir> [wmi_json]
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
NOWIN = 0x08000000
FREE_TOLERANCE = 256 * 1024 * 1024      # 256 MB：足以吸收測試期間的正常寫入
PLAN_FIELDS = ('mode', 'source', 'destination', 'file_group', 'recovery_mode',
               'description', 'warnings', 'available')


def probe(probe_exe, base, work, method, args=None, calls=None):
    cmd = [probe_exe, base, work]
    if calls:
        cmd += ['--calls', calls]
    else:
        cmd += [method]
        if args is not None:
            args_file = os.path.join(work, 'args-%s.json' % method)
            with open(args_file, 'w', encoding='utf-8', newline='\n') as handle:
                handle.write(json.dumps(args, ensure_ascii=False))
            cmd += ['--args', args_file]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', creationflags=NOWIN, cwd=work)
    text = (result.stdout or '').strip()
    if not text:
        return result.returncode, None
    lines = text.splitlines()
    return result.returncode, json.loads(lines[-1])


def work_module(src):
    sys.path.insert(0, src)
    import disk_tools as DT
    return DT


def plan_or_error(DT, *args):
    """Python 的 plan()：成功回傳 dict，失敗回傳錯誤訊息字串。"""
    try:
        return DT.plan(*args)
    except Exception as exc:                       # noqa: BLE001 - 就是要比對訊息
        return str(exc)


def launch_or_error(DT, preview, token, confirmed):
    try:
        return DT.launch(preview, token, confirmed)
    except Exception as exc:                       # noqa: BLE001
        return str(exc)


def load_wmi(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8-sig') as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        data = [data]
    return sorted(({'drive': str(item.get('DeviceID', '')).upper()} for item in data or []),
                  key=lambda d: d['drive'])


def section_info(base, work, probe_exe, DT, wmi_path, failures):
    print('=== 1) disk_info：磁碟清單 ===')
    code, reply = probe(probe_exe, base, work, 'disk_info')
    if code == 3 or not reply or not reply.get('ok'):
        print('FAIL：C++ 核心沒有接手 disk_info（exit=%s reply=%s）' % (code, reply))
        return failures + 1
    native = (reply.get('r') or {}).get('drives') or []
    expected = DT.inventory().get('drives') or []
    for label, items in (('C++', native), ('Python', expected)):
        print('  %s（%d 部）：%s' % (label, len(items),
                                    ', '.join('%s %s disk=%s free=%s' % (i.get('drive'), i.get('filesystem'),
                                                                         i.get('disk_number'), i.get('free'))
                                              for i in items)))
    if len(native) != len(expected):
        print('FAIL：磁碟數量不同（%d vs %d）' % (len(native), len(expected)))
        failures += 1
    for index, (left, right) in enumerate(zip(native, expected)):
        for key in ('drive', 'filesystem', 'disk_number'):
            if left.get(key) != right.get(key):
                print('FAIL：第 %d 部 %s 不同（%r vs %r）' % (index + 1, key, left.get(key), right.get(key)))
                failures += 1
        a, b = left.get('free'), right.get('free')
        if a is None or b is None or abs(int(a) - int(b)) > FREE_TOLERANCE:
            print('FAIL：第 %d 部 free 差距過大（%r vs %r）' % (index + 1, a, b))
            failures += 1
    if failures == 0:
        print('  PASS：磁碟清單逐欄相同（free 在容許誤差內）')
    wmi = load_wmi(wmi_path)
    if wmi:
        letters_native = sorted(d.get('drive', '').upper() for d in native)
        letters_wmi = sorted(d['drive'] for d in wmi)
        print('=== 獨立交叉驗證（WMI）：%s ===' % ', '.join(letters_wmi))
        if letters_native != letters_wmi:
            print('FAIL：磁碟機清單與 WMI 不同（%s vs %s）' % (letters_native, letters_wmi))
            failures += 1
        else:
            print('  PASS：與 WMI 相同')
    return failures


def section_preview(base, work, probe_exe, DT, failures):
    print('=== 2) disk_preview：預覽內容與錯誤訊息 ===')
    available = [d['drive'] for d in DT.inventory().get('drives') or []]
    usable = available[0] if available else 'C:'
    missing = next((letter + ':' for letter in 'QRSTUVWXYZ' if letter + ':' not in available), 'Q:')
    cases = [
        ('check', usable, '', 'documents', 'regular'),
        ('repair', usable, '', 'documents', 'regular'),
        ('format', usable, '', 'documents', 'regular'),      # 不支援的操作
        ('check', 'ZZ', '', 'documents', 'regular'),         # 格式不對
        ('check', missing, '', 'documents', 'regular'),      # 不存在的磁碟
    ]
    for case in cases:
        code, reply = probe(probe_exe, base, work, 'disk_preview', list(case))
        expected = plan_or_error(DT, *case)
        if isinstance(expected, str):
            got = reply.get('e') if reply else None
            mark = 'OK  ' if got == expected else 'FAIL'
            print('  %s %s → %r' % (mark, case, got))
            if got != expected:
                print('       預期 %r' % expected)
                failures += 1
            continue
        if code == 3 or not reply or not reply.get('ok'):
            print('FAIL：disk_preview 沒有被接手或失敗（%s）' % (reply,))
            failures += 1
            continue
        got = reply.get('r') or {}
        differing = [k for k in PLAN_FIELDS if got.get(k) != expected.get(k)]
        if 'command' in got:
            differing.append('command（不該出現）')
        mark = 'OK  ' if not differing else 'FAIL'
        print('  %s %s → %s' % (mark, case, got.get('description', '')))
        if differing:
            print('       不同欄位：%s' % differing)
            for key in differing:
                print('         %s：C++=%r Python=%r' % (key, got.get(key), expected.get(key)))
            failures += 1
        if not isinstance(got.get('token'), str) or len(got.get('token')) != 32:
            print('FAIL：token 不是 32 個十六進位字元（%r）' % got.get('token'))
            failures += 1
    return failures


def section_launch(base, work, probe_exe, DT, failures):
    print('=== 3) disk_launch：只驗證應該拒絕的路徑 ===')
    available = [d['drive'] for d in DT.inventory().get('drives') or []]
    usable = available[0] if available else 'C:'

    calls = [
        {'m': 'disk_launch', 'a': ['', False]},                                   # 還沒預覽
        {'m': 'disk_preview', 'a': ['check', usable, '', 'documents', 'regular']},
        {'m': 'disk_launch', 'a': ['deadbeef', True]},                            # token 不對
        {'m': 'disk_launch', 'a': ['@token', False]},                             # 未確認
    ]
    calls_file = os.path.join(work, 'calls-launch.json')
    with open(calls_file, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(calls, ensure_ascii=False))
    code, replies = probe(probe_exe, base, work, None, calls=calls_file)
    if code == 3 or not isinstance(replies, list) or len(replies) != len(calls):
        print('FAIL：--calls 模式沒有取得逐一回覆（exit=%s）' % code)
        return failures + 1

    cases = [
        (0, '沒有預覽就啟動', None, '', False),
        (2, 'token 不對', 'deadbeef', 'deadbeef', True),
        (3, '未確認', None, 'PREVIEWED', False),
    ]
    for index, label, token, given, confirmed in cases:
        got = replies[index].get('e')
        if label == '沒有預覽就啟動':
            # 這一項的守門在 app.py 的 disk_launch（disk_tools.launch 本身沒有這個檢查，
            # 直接餵 None 會得到 AttributeError，那不是產品的行為）。
            expected = '請先預覽磁碟操作'
        elif label == 'token 不對':
            # Python 那側要先有一份 plan 才比得到 token 檢查
            plan = plan_or_error(DT, 'check', usable, '', 'documents', 'regular')
            expected = launch_or_error(DT, plan, given, confirmed)
        else:
            plan = plan_or_error(DT, 'check', usable, '', 'documents', 'regular')
            expected = launch_or_error(DT, plan, plan['token'], confirmed)
        mark = 'OK  ' if got == expected else 'FAIL'
        print('  %s %s → %r' % (mark, label, got))
        if got != expected:
            print('       預期 %r' % expected)
            failures += 1
    print('  （成功的啟動會跳出 UAC 並開 chkdsk 視窗，自動測試刻意不執行）')
    return failures


def main(argv):
    probe_exe, base, work = argv[1], argv[2], argv[3]
    wmi_path = argv[4] if len(argv) > 4 else ''
    src = os.path.join(base, '_build', 'src')
    os.makedirs(work, exist_ok=True)
    os.chdir(work)
    DT = work_module(src)
    failures = 0

    failures = section_info(base, work, probe_exe, DT, wmi_path, failures)
    failures = section_preview(base, work, probe_exe, DT, failures)
    failures = section_launch(base, work, probe_exe, DT, failures)

    print()
    if failures == 0:
        print('PASS：disk_info／disk_preview／disk_launch 與 Python 版等價。')
        return 0
    print('FAIL：%d 項不同' % failures)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
