"""驗證 C++ 接手的 system_info 與 Python 版（system_tools.hardware_info + CLEANUP）等價。

硬體欄位分成三類：
  1. 決定性欄位（system／supported／arch／emulated／cores／heavy／light／slots／gpu_encoders／
     磁碟的 path、磁碟數量）必須完全相同；
  2. ram 允許 0.1 的差距（Python round(x,1) 與 C++ nearbyint 在極端值可能差一步）；
  3. free／total 是會變動的值，允許 256 MB 誤差。
cleanup 分類必須逐欄相同。

用法（需 PYTHONPATH 指向 _build\\vendor 與 _build\\src）：
    check_system_info.py <swbd-cpp-probe.exe> <base_dir> <work_dir>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
NOWIN = 0x08000000
DISK_TOLERANCE = 256 * 1024 * 1024
EXACT_KEYS = ('system', 'supported', 'arch', 'emulated', 'cores', 'heavy', 'light', 'slots')


def probe(probe_exe, base, work):
    """wiring 探針會走正式的注入路徑（api_cpp_system_facts），並把回覆原文印在 system_info_reply=。"""
    result = subprocess.run([probe_exe, base, work, '--system-info'], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', creationflags=NOWIN, cwd=work)
    text = (result.stdout or '')
    for line in text.splitlines():
        if line.startswith('system_info_reply='):
            return result.returncode, json.loads(line[len('system_info_reply='):])
    return result.returncode, {'ok': False, 'e': '探針沒有輸出 system_info_reply（%s）' % text.strip()[-200:]}


def python_reference(src, base, data):
    """與產品相同的設定：engine.py 啟動時也會設定 base_dir／_DATA／FFMPEG。
    少了 FFMPEG，detect_hw() 不會去探測（回空陣列），那不能代表產品的行為。"""
    sys.path.insert(0, src)
    import engine as E
    E.base_dir = lambda: base
    E._DATA = data
    found = E.find_tool('ffmpeg')
    if found:
        E.FFMPEG = found
    import system_tools as ST
    return {'hardware': ST.hardware_info(), 'cleanup': ST.CLEANUP}


def main(argv):
    probe_exe, base, work = argv[1], argv[2], argv[3]
    src = os.path.join(base, '_build', 'src')
    os.makedirs(work, exist_ok=True)
    os.chdir(work)
    failures = 0

    code, reply = probe(probe_exe, base, work)
    if not reply or not reply.get('ok'):
        print('FAIL：C++ 核心沒有接手 system_info（exit=%s reply=%s）' % (code, reply))
        return 1
    native = reply.get('r') or {}
    expected = python_reference(src, base, work)
    nh, ph = native.get('hardware') or {}, expected['hardware']

    print('=== 1) 決定性欄位 ===')
    for key in EXACT_KEYS:
        mark = 'OK  ' if nh.get(key) == ph.get(key) else 'FAIL'
        print('  %s %-10s C++=%-28r Python=%r' % (mark, key, nh.get(key), ph.get(key)))
        if nh.get(key) != ph.get(key):
            failures += 1
    ram_ok = abs(float(nh.get('ram') or 0) - float(ph.get('ram') or 0)) <= 0.1
    print('  %s %-10s C++=%-28r Python=%r' % ('OK  ' if ram_ok else 'FAIL', 'ram', nh.get('ram'), ph.get('ram')))
    if not ram_ok:
        failures += 1
    # cpu 名稱來自登錄檔，可能有一致的尾端空白差異，所以去空白後比對
    cpu_ok = (nh.get('cpu') or '').strip() == (ph.get('cpu') or '').strip()
    print('  %s %-10s C++=%-28r Python=%r' % ('OK  ' if cpu_ok else 'FAIL', 'cpu', nh.get('cpu'), ph.get('cpu')))
    if not cpu_ok:
        failures += 1

    print('=== 2) 硬體編碼器 ===')
    native_hw, python_hw = sorted(nh.get('gpu_encoders') or []), sorted(ph.get('gpu_encoders') or [])
    mark = 'OK  ' if native_hw == python_hw else 'FAIL'
    print('  %s C++=%s Python=%s' % (mark, native_hw, python_hw))
    if native_hw != python_hw:
        failures += 1

    print('=== 3) 磁碟 ===')
    nd = {d.get('path'): d for d in (nh.get('disks') or [])}
    pd = {d.get('path'): d for d in (ph.get('disks') or [])}
    if sorted(nd) != sorted(pd):
        print('FAIL：磁碟清單不同（%s vs %s）' % (sorted(nd), sorted(pd)))
        failures += 1
    for path in sorted(set(nd) & set(pd)):
        for key in ('total', 'free'):
            a, b = nd[path].get(key), pd[path].get(key)
            ok = a is not None and b is not None and abs(int(a) - int(b)) <= DISK_TOLERANCE
            print('  %s %-6s %-6s C++=%s Python=%s' % ('OK  ' if ok else 'FAIL', path, key, a, b))
            if not ok:
                failures += 1

    print('=== 4) cleanup 分類 ===')
    nc, pc = native.get('cleanup') or [], ph and expected['cleanup']
    if (native.get('cleanup') or []) != expected['cleanup']:
        print('FAIL：cleanup 分類不同')
        print('   C++   ：%s' % json.dumps(nc, ensure_ascii=False))
        print('   Python：%s' % json.dumps(pc, ensure_ascii=False))
        failures += 1
    else:
        print('  OK   %d 個分類逐欄相同' % len(nc))

    print()
    if failures == 0:
        print('PASS：system_info 與 Python 版等價（可變動的磁碟位元組在容許誤差內）。')
        return 0
    print('FAIL：%d 項不同' % failures)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
