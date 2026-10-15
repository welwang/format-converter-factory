"""引擎等價閘門：用同一組 JSON 測項驅動 engine-test.exe，輸出可逐項比對的正規化結果。

用法：python gate_engine.py <engine-test.exe> <輸出 json> [工作暫存目錄] [專案根目錄]
"""
import json, os, queue, subprocess, sys, threading, time, pathlib

BASE = 'E:/四維八德'
SAMPLES = BASE + '/_build/samples'
NOWIN = 0x08000000

def call(p, q, timeout=180):
    p.stdin.write(json.dumps(q, ensure_ascii=False) + '\n')
    p.stdin.flush()
    try:
        line = p._q.get(timeout=timeout)
    except queue.Empty:
        raise RuntimeError(f'引擎 {timeout}s 沒有回應：' + json.dumps(q, ensure_ascii=False))
    if not line:
        raise RuntimeError('引擎沒有回應（程序可能已結束）：' + json.dumps(q, ensure_ascii=False))
    return json.loads(line)

def ids_of(reply):
    """start 回傳的是 job id 陣列（字串），status 回傳的是 job 物件陣列。"""
    if isinstance(reply, list):
        out = [it.get('id') if isinstance(it, dict) else it for it in reply]
        return [i for i in out if i]
    if isinstance(reply, dict) and reply.get('id'):
        return [reply['id']]
    return []

def wait_done(p, ids, timeout=240):
    if not ids or len(set(ids)) != len(ids):
        raise ValueError(f'工作 id 為空或重複：{ids}')
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        jobs = call(p, {'m': 'status'})
        last = [j for j in jobs if j.get('id') in ids]
        if len(last) == len(ids) and all(j.get('state') not in ('queued', 'running') for j in last):
            return last
        time.sleep(0.1)
    raise TimeoutError(f'等待逾時：{ids} / 最後狀態 {last}')


def require_success(case, jobs):
    if len(jobs) != 1 or jobs[0].get('state') != 'done':
        raise RuntimeError(f'{case} 未完成：{jobs}')
    job = jobs[0]
    output = job.get('output', '')
    if not os.path.isfile(output) or os.path.getsize(output) < 1:
        raise RuntimeError(f'{case} 沒有有效輸出：{output}')
    if job.get('out_size') != os.path.getsize(output):
        raise RuntimeError(f'{case} 輸出大小與工作記錄不符')
    return jobs

def norm(value, data_dir):
    """把絕對路徑換成穩定標記，讓 C 版與 C++ 版可以逐項比對。"""
    if isinstance(value, dict):
        return {k: norm(v, data_dir) for k, v in value.items()}
    if isinstance(value, list):
        return [norm(v, data_dir) for v in value]
    if isinstance(value, str):
        return value.replace('\\', '/').replace(data_dir.replace('\\', '/'), '<DATA>').replace(BASE, '<BASE>')
    return value

def main():
    global BASE, SAMPLES
    exe, out_path = sys.argv[1], sys.argv[2]
    data = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(out_path), 'work')
    if len(sys.argv) > 4:
        BASE = sys.argv[4].replace('\\', '/')
        SAMPLES = BASE + '/_build/samples'
    os.makedirs(data, exist_ok=True)
    for name in os.listdir(data):
        p = os.path.join(data, name)
        if os.path.isfile(p):
            os.remove(p)

    audio = SAMPLES + '/a.mp3'
    video = SAMPLES + '/v.mp4'
    for fixture in (audio, video):
        if not os.path.isfile(fixture):
            raise FileNotFoundError(f'缺少閘門素材：{fixture}')
    records = []
    p = subprocess.Popen([exe, BASE, data], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=NOWIN)
    p._q = queue.Queue()
    def _reader():
        for line in p.stdout:
            p._q.put(line)
        p._q.put('')
    threading.Thread(target=_reader, daemon=True).start()
    # 驅動程式第一行 stdin 是 setup（base/data），不是請求。
    p.stdin.write(json.dumps({'base': BASE, 'data': data}, ensure_ascii=False) + '\n')
    p.stdin.flush()

    # 1) 描述與媒體資訊（純查詢，必須逐位元組穩定）
    records.append({'case': 'describe', 'result': norm(call(p, {'m': 'describe', 'files': [audio]}), data)})
    records.append({'case': 'media_info', 'result': norm(call(p, {'m': 'media_info', 'files': [audio]}), data)})

    # 2) 音訊轉檔（單檔）
    jobs = call(p, {'m': 'start', 'files': [audio], 'target': 'm4a',
                    'opt': {'out_dir': data, 'preset': 'balanced', 'hwaccel': False,
                            'fastcopy': False, 'resource_mode': 'quiet'}, 'merge': False})
    ids = ids_of(jobs)
    if len(ids) != 1:
        raise RuntimeError(f'音訊工作應接受一個檔案：{jobs}')
    records.append({'case': 'start_audio', 'accepted': len(ids)})
    records.append({'case': 'finish_audio', 'result': norm(require_success('audio', wait_done(p, ids)), data)})

    # 3) 快速容器複製（fastcopy，走不同引擎分支）
    jobs = call(p, {'m': 'start', 'files': [video], 'target': 'mkv',
                    'opt': {'out_dir': data, 'preset': 'balanced', 'fastcopy': True, 'hwaccel': False,
                            'resource_mode': 'quiet'}, 'merge': False})
    ids = ids_of(jobs)
    if len(ids) != 1:
        raise RuntimeError(f'免重編碼工作應接受一個檔案：{jobs}')
    records.append({'case': 'finish_fastcopy', 'result': norm(require_success('fastcopy', wait_done(p, ids)), data)})

    # 4) 取消：送出後立刻取消，確認狀態機行為一致
    jobs = call(p, {'m': 'start', 'files': [audio], 'target': 'flac',
                    'opt': {'out_dir': data, 'preset': 'high', 'resource_mode': 'quiet'}, 'merge': False})
    cancel_ids = ids_of(jobs)
    if len(cancel_ids) != 1:
        raise RuntimeError(f'取消測試未接受工作：{jobs}')
    jid = cancel_ids[0]
    cancelled = call(p, {'m': 'cancel', 'id': jid})
    if cancelled is not True:
        raise RuntimeError(f'取消要求被拒絕：{cancelled}')
    records.append({'case': 'cancel_reply', 'result': norm(cancelled, data)})
    cancel_jobs = wait_done(p, [jid])
    if cancel_jobs[0].get('state') != 'cancelled':
        raise RuntimeError(f'取消工作未進入 cancelled：{cancel_jobs}')
    records.append({'case': 'cancel_state', 'result': norm(cancel_jobs, data)})

    # 5) 未知指令與 clear
    records.append({'case': 'unknown_method', 'result': norm(call(p, {'m': 'no_such_method'}), data)})
    records.append({'case': 'clear', 'result': norm(call(p, {'m': 'clear'}), data)})

    reply = call(p, {'m': 'quit'})
    records.append({'case': 'quit', 'result': norm(reply, data)})
    p.stdin.close()
    p.wait(timeout=15)
    if p.returncode != 0:
        raise RuntimeError(f'引擎程序失敗：{p.returncode}')

    result = {'exe': os.path.basename(exe), 'records': records}
    pathlib.Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    print('已寫入', out_path)
    return 0

if __name__ == '__main__':
    sys.exit(main())
