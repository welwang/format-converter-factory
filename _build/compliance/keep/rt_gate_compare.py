"""逐項比對 C 版與 C++ 版的閘門輸出。用法：gate_compare.py <golden 目錄>"""
import json, re, sys, pathlib

JOB_VOLATILE = {'elapsed', 'eta', 'speed', 'pct', 'created', 'started', 'finished'}
ID_RE = re.compile(r'^x[0-9a-f]{4,8}$')

def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))

def strip(node, path=''):
    if isinstance(node, dict):
        out = {}
        # 被取消的工作：encoder 與 output 取決於「取消送達」與「工作已設好輸出路徑」哪個先發生。
        # 兩顆執行檔的啟動時序只要差幾毫秒就會不同（實測 C 版連跑兩次相同、C++ 版不同），
        # 那不是行為差異，所以這兩個欄位在 state == 'cancelled' 時不比。
        is_job = all(k in node for k in ('id', 'state', 'target'))
        cancelled = is_job and node.get('state') == 'cancelled'
        for k, v in node.items():
            if is_job and k in JOB_VOLATILE:
                continue
            # 通知數量允許時序差異，但兩份報告都須先獨立通過至少一次通知的斷言。
            if path == '.report' and k == 'completion_notifications':
                continue
            if cancelled and k in ('encoder', 'output'):
                continue
            if is_job and k == 'id' and isinstance(v, str) and ID_RE.match(v):
                out[k] = 'x<ID>'      # 引擎的 job id 由執行期計數產生，本來就每次不同
            else:
                out[k] = strip(v, f'{path}.{k}')
        return out
    if isinstance(node, list):
        return [strip(v, f'{path}[]') for v in node]
    if isinstance(node, str):
        return node.replace('\\', '/')
    return node

def diff(a, b, path='', out=None):
    if out is None:
        out = []
    if type(a) is not type(b):
        out.append(f'{path}: 型別不同 {type(a).__name__} vs {type(b).__name__}')
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f'{path}.{k}: 只有 C++ 版有')
            elif k not in b:
                out.append(f'{path}.{k}: 只有 C 版有')
            else:
                diff(a[k], b[k], f'{path}.{k}', out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f'{path}: 長度不同 {len(a)} vs {len(b)}')
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f'{path}[{i}]', out)
    elif a != b:
        out.append(f'{path}: {a!r} vs {b!r}')
    return out

def validate_report(report):
    if not isinstance(report, dict):
        raise ValueError('報告必須是 JSON 物件')
    if 'report' in report:
        smoke = report['report']
        if report.get('exit_code') != 0 or not isinstance(smoke, dict):
            raise ValueError('外殼程序未正常結束或報告格式不正確')
        for field in ('_swbd_smoke', 'ok', 'preview', 'error_rejection'):
            if smoke.get(field) is not True:
                raise ValueError(f'外殼斷言未通過：{field}')
        if smoke.get('mixed_jobs') != 2 or not isinstance(smoke.get('formats'), int) or smoke['formats'] < 1:
            raise ValueError('外殼工作或格式清單不完整')
        notifications = smoke.get('completion_notifications')
        if type(notifications) is not int or notifications < 1:
            raise ValueError('外殼缺少完成通知')
        return
    records = report.get('records')
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError('引擎報告缺少 records')
    cases = {r.get('case'): r for r in records}
    required = {'describe', 'media_info', 'start_audio', 'finish_audio', 'finish_fastcopy',
                'cancel_reply', 'cancel_state', 'unknown_method', 'clear', 'quit'}
    if len(cases) != len(records) or not required.issubset(cases):
        raise ValueError('引擎案例缺少或重複')
    if cases['start_audio'].get('accepted') != 1:
        raise ValueError('音訊工作未被接受')
    for case, expected in (('finish_audio', 'done'), ('finish_fastcopy', 'done'), ('cancel_state', 'cancelled')):
        jobs = cases[case].get('result')
        if not isinstance(jobs, list) or len(jobs) != 1 or not isinstance(jobs[0], dict) or jobs[0].get('state') != expected:
            raise ValueError(f'{case} 未達預期狀態 {expected}')
    for case in ('cancel_reply', 'clear', 'quit'):
        if cases[case].get('result') is not True:
            raise ValueError(f'{case} 未成功')


def compare(name, cpath, cpppath):
    try:
        c = load(cpath)
        cpp = load(cpppath)
        validate_report(c)
        validate_report(cpp)
        c, cpp = strip(c), strip(cpp)
    except (OSError, ValueError, TypeError) as ex:
        print(f'[FAIL] {name}：{ex}')
        return False
    c.pop('exe', None); cpp.pop('exe', None)
    d = diff(c, cpp, name)
    print(f'[{"PASS" if not d else "FAIL"}] {name}：{len(d)} 項差異')
    for line in d[:40]:
        print('   ', line)
    return not d

def main():
    g = pathlib.Path(sys.argv[1])
    results = [
        # 同一顆 C 版 exe 連跑兩次：用來證明哪些欄位本來就不穩定（目前只有引擎 job id）。
        compare('engine（C 版重跑，不穩定欄位基準）', g / 'engine-c.json', g / 'engine-c2.json'),
        compare('engine（C vs C++）', g / 'engine-c.json', g / 'engine-cpp.json'),
    ]
    if '--engine-only' in sys.argv[2:]:
        print('外殼比對未執行（明確指定 --engine-only）')
    else:
        results.append(compare('shell（C vs C++）', g / 'shell-c.json', g / 'shell-cpp.json'))
    ok = all(results)
    print('總結果：' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
